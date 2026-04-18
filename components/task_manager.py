#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Task Manager Component
"""

import os
import sys
import time
import uuid
import bisect
import logging
import threading
import traceback
from typing import Dict, Any, List, Optional, Union, Callable

# Configure logging
logger = logging.getLogger('kingdom_ai.task_manager')

class TaskManager:
    """Task management system for concurrent operations while maintaining conversation abilities.
    
    This class enables multi-tasking capabilities within the Kingdom AI system
    while maintaining conversation flow and context. It handles task prioritization,
    status tracking, and resource management.
    """
    
    def __init__(self, event_bus, config=None):
        """Initialize the task management system.
        
        Args:
            event_bus: System event bus for communication
            config: Configuration dictionary
        """
        self.event_bus = event_bus
        self.config = config or {}
        self.running = False
        
        # Task storage
        self.tasks = {}  # Dictionary of tasks: {task_id: task_dict}
        self.task_queue = []  # Prioritized task queue
        self.completed_tasks = {}  # Store completed task results
        
        # Thread management
        self.task_threads = {}  # Dictionary of running threads
        self.max_concurrent_tasks = self.config.get("max_concurrent_tasks", 5)
        
        # For thread-safe operations
        self.task_lock = threading.RLock()
        
        # Register event handlers
        self._register_events()
        
        # Intent pattern registry for task commands
        self.intent_patterns = {
            "list_tasks": [
                r"show( all|) tasks",
                r"list( all|) tasks",
                r"what tasks are running",
                r"task status"
            ],
            "cancel_task": [
                r"cancel task (\d+)",
                r"stop task (\d+)",
                r"abort task (\d+)",
                r"terminate task (\d+)"
            ]
        }
        
        logger.info("Task Manager initialized successfully")
        self.running = True
    
    def _register_events(self):
        """Register event handlers for task-related events."""
        try:
            if self.event_bus:
                # FIXED: EventBus methods are now sync
                self.event_bus.subscribe("task.created", self._handle_task_created)
                self.event_bus.subscribe("task.completed", self._handle_task_completed)
                self.event_bus.subscribe("task.failed", self._handle_task_failed)
                logger.debug("Task Manager event handlers registered")
        except Exception as e:
            logger.error(f"Failed to register Task Manager event handlers: {str(e)}")
    
    def add_task(self, task_func, task_name, priority=5, args=None, kwargs=None):
        """Add a new task to the task queue.
        
        Args:
            task_func: Function to execute
            task_name: Human-readable task name
            priority: Task priority (1-10, 10 being highest)
            args: Positional arguments for task_func
            kwargs: Keyword arguments for task_func
            
        Returns:
            task_id: Unique identifier for the task
        """
        with self.task_lock:
            # Generate secure task ID using uuid
            task_id = str(uuid.uuid4())
            
            # Create task dictionary
            task = {
                "id": task_id,
                "name": task_name,
                "function": task_func,
                "args": args or (),
                "kwargs": kwargs or {},
                "priority": max(1, min(10, priority)),  # Constrain priority between 1-10
                "status": "pending",
                "added_time": time.time(),
                "start_time": None,
                "completion_time": None,
                "result": None,
                "error": None
            }
            
            # Add to task storage
            self.tasks[task_id] = task
            
            # Add to queue based on priority
            bisect.insort(self.task_queue, (11 - task["priority"], task["added_time"], task_id))
            
            # Publish task created event
            if self.event_bus:
                self.event_bus.publish("task.created", {
                    "task_id": task_id,
                    "task_name": task_name,
                    "priority": task["priority"]
                })
            
            logger.info(f"Task '{task_name}' added with ID {task_id} and priority {task['priority']}")
            return task_id
    
    def process_pending_tasks(self):
        """Process pending tasks from the queue based on available threads."""
        with self.task_lock:
            # Check if we can start more tasks
            running_count = len(self.task_threads)
            if running_count >= self.max_concurrent_tasks or not self.task_queue:
                return
            
            # Clean up completed threads
            self._cleanup_finished_threads()
            
            # Calculate available slots
            available_slots = self.max_concurrent_tasks - len(self.task_threads)
            
            # Process tasks up to available slots
            for _ in range(min(available_slots, len(self.task_queue))):
                if not self.task_queue:
                    break
                    
                # Get highest priority task
                _, _, task_id = self.task_queue.pop(0)
                if task_id not in self.tasks:
                    continue  # Task may have been canceled
                    
                # Start the task in a new thread
                self._start_task_thread(task_id)
    
    def _start_task_thread(self, task_id):
        """Start a task in a separate thread."""
        task = self.tasks.get(task_id)
        if not task or task["status"] != "pending":
            return
            
        # Update task status
        task["status"] = "running"
        task["start_time"] = time.time()
        
        # Create and start thread
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id,),
            name=f"Task-{task_id}"
        )
        thread.daemon = True  # Make thread daemon so it doesn't block program exit
        
        self.task_threads[task_id] = {
            "thread": thread,
            "start_time": time.time()
        }
        
        thread.start()
        logger.debug(f"Started task '{task['name']}' in thread {thread.name}")
    
    def _run_task(self, task_id):
        """Execute a task and handle its result or exception."""
        task = self.tasks.get(task_id)
        if not task:
            return
            
        try:
            # Execute the task
            result = task["function"](*task["args"], **task["kwargs"])
            
            # Store result and update status
            with self.task_lock:
                if task_id in self.tasks:  # Check if task wasn't canceled
                    task["status"] = "completed"
                    task["result"] = result
                    task["completion_time"] = time.time()
                    
                    # Store in completed tasks
                    self.completed_tasks[task_id] = task
                    
                    # Publish completion event
                    if self.event_bus:
                        self.event_bus.publish("task.completed", {
                            "task_id": task_id,
                            "task_name": task["name"],
                            "execution_time": task["completion_time"] - task["start_time"]
                        })
                
                logger.info(f"Task '{task['name']}' completed successfully")
                
        except Exception as e:
            logger.error(f"Task '{task['name']}' failed with error: {str(e)}")
            traceback.print_exc()
            
            # Update task with error information
            with self.task_lock:
                if task_id in self.tasks:  # Check if task wasn't canceled
                    task["status"] = "failed"
                    task["error"] = str(e)
                    task["completion_time"] = time.time()
                    
                    # Store in completed tasks
                    self.completed_tasks[task_id] = task
                    
                    # Publish failure event
                    if self.event_bus:
                        self.event_bus.publish("task.failed", {
                            "task_id": task_id,
                            "task_name": task["name"],
                            "error": str(e)
                        })
    
    def _cleanup_finished_threads(self):
        """Clean up completed task threads."""
        finished_tasks = []
        
        for task_id, thread_info in self.task_threads.items():
            if not thread_info["thread"].is_alive():
                finished_tasks.append(task_id)
                
        for task_id in finished_tasks:
            if task_id in self.task_threads:
                del self.task_threads[task_id]
    
    def cancel_task(self, task_id):
        """Cancel a pending task or try to stop a running task.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if task was canceled, False otherwise
        """
        with self.task_lock:
            if task_id not in self.tasks:
                return False
                
            task = self.tasks[task_id]
            
            # Remove from queue if pending
            if task["status"] == "pending":
                # Find and remove from task queue
                for i, (_, _, queue_task_id) in enumerate(self.task_queue):
                    if queue_task_id == task_id:
                        self.task_queue.pop(i)
                        break
                        
                task["status"] = "canceled"
                logger.info(f"Canceled pending task '{task['name']}'")
                return True
                
            # Mark running task as canceled
            elif task["status"] == "running":
                task["status"] = "canceling"
                logger.info(f"Attempting to cancel running task '{task['name']}'")
                # Note: Actual cancellation depends on task implementation checking for cancellation
                return True
                
            return False
    
    def get_task_status(self, task_id):
        """Get the current status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            dict: Task status dictionary or None if task not found
        """
        with self.task_lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                return {
                    "id": task["id"],
                    "name": task["name"],
                    "status": task["status"],
                    "added_time": task["added_time"],
                    "start_time": task["start_time"],
                    "completion_time": task["completion_time"],
                    "result": task["result"] if task["status"] == "completed" else None,
                    "error": task["error"] if task["status"] == "failed" else None
                }
            return None
    
    def list_tasks(self, include_completed=False):
        """List all tasks and their statuses.
        
        Args:
            include_completed: Whether to include completed tasks
            
        Returns:
            list: List of task status dictionaries
        """
        with self.task_lock:
            active_tasks = [self.get_task_status(task_id) for task_id in self.tasks.keys()]
            
            if include_completed:
                completed = [self.get_task_status(task_id) for task_id in self.completed_tasks.keys()
                           if task_id not in self.tasks]
                return active_tasks + completed
            
            return active_tasks
    
    def _handle_task_created(self, event):
        """Handle task.created events."""
        try:
            task_id = event.get("task_id")
            task_name = event.get("task_name", "Unknown")
            logger.debug(f"Received task.created event for '{task_name}' (ID: {task_id})")
        except Exception as e:
            logger.error(f"Error handling task.created event: {str(e)}")
    
    def _handle_task_completed(self, event):
        """Handle task.completed events."""
        try:
            task_id = event.get("task_id")
            task_name = event.get("task_name", "Unknown")
            execution_time = event.get("execution_time", 0)
            logger.debug(f"Received task.completed event for '{task_name}' (ID: {task_id}) - " +
                       f"Execution time: {execution_time:.2f}s")
        except Exception as e:
            logger.error(f"Error handling task.completed event: {str(e)}")
    
    def _handle_task_failed(self, event):
        """Handle task.failed events."""
        try:
            task_id = event.get("task_id")
            task_name = event.get("task_name", "Unknown")
            error = event.get("error", "Unknown error")
            logger.debug(f"Received task.failed event for '{task_name}' (ID: {task_id}) - Error: {error}")
        except Exception as e:
            logger.error(f"Error handling task.failed event: {str(e)}")
    
    def shutdown(self):
        """Shut down the task manager cleanly."""
        logger.info("Shutting down Task Manager")
        self.running = False
        
        # Cancel all pending tasks
        with self.task_lock:
            for task_id in list(self.tasks.keys()):
                self.cancel_task(task_id)
            
            # Wait for running tasks to complete (up to timeout)
            timeout = self.config.get("shutdown_timeout", 5.0)
            shutdown_start = time.time()
            
            while self.task_threads and time.time() - shutdown_start < timeout:
                time.sleep(0.1)
                self._cleanup_finished_threads()
                
            # Log any tasks that didn't finish
            if self.task_threads:
                logger.warning(f"{len(self.task_threads)} tasks did not complete during shutdown")
