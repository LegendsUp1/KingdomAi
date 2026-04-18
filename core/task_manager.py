#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kingdom AI - Task Manager Module

This module provides multi-tasking capabilities while maintaining 
conversational abilities. It manages task prioritization, status tracking,
and concurrent execution.
"""

import time
import uuid
import logging
import threading
import queue
from typing import Dict, List, Callable, Tuple
import secrets

# Set up logging
logger = logging.getLogger('KingdomAI.TaskManager')

class Task:
    """Represents a task in the system with status tracking."""
    
    def __init__(self, 
                 task_id: str,
                 name: str, 
                 function: Callable, 
                 args: Tuple = None, 
                 kwargs: Dict = None,
                 priority: int = 5):
        """
        Initialize a new task.
        
        Args:
            task_id: Unique identifier for the task
            name: Human-readable name for the task
            function: Function to execute for this task
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            priority: Task priority (1-10, higher is more important)
        """
        self.task_id = task_id
        self.name = name
        self.function = function
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.priority = priority
        
        # Task state
        self.status = "pending"  # pending, running, completed, failed, cancelled
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.progress = 0.0  # 0.0 to 1.0
        
    def execute(self):
        """Execute the task and handle its result or error."""
        self.status = "running"
        self.start_time = time.time()
        
        try:
            # Pass the task object to the function if it accepts a 'task' parameter
            if 'task' in self.function.__code__.co_varnames:
                self.kwargs['task'] = self
                
            # Execute the function
            self.result = self.function(*self.args, **self.kwargs)
            self.status = "completed"
            
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            logger.error(f"Task {self.task_id} ({self.name}) failed: {e}")
            
        finally:
            self.end_time = time.time()
            
        return self.result
        
    def update_progress(self, progress: float):
        """
        Update the progress of this task.
        
        Args:
            progress: Value between 0.0 and 1.0 indicating task progress
        """
        self.progress = max(0.0, min(1.0, progress))
        
    def cancel(self):
        """Cancel this task if it's not already completed or failed."""
        if self.status in ("pending", "running"):
            self.status = "cancelled"
            self.end_time = time.time()
            return True
        return False
        
    def to_dict(self) -> Dict:
        """Convert task to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status,
            "priority": self.priority,
            "progress": self.progress,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time) if self.end_time and self.start_time else None,
            "error": self.error
        }


class TaskManager:
    """
    Manages concurrent task execution with priority queuing and status tracking.
    Enables multi-tasking while maintaining conversational abilities.
    """
    
    def __init__(self, event_bus=None, max_concurrent_tasks: int = 5):
        """
        Initialize the Task Manager.
        
        Args:
            event_bus: Event bus for publishing task events
            max_concurrent_tasks: Maximum number of concurrent tasks
        """
        self.event_bus = event_bus
        self.tasks = {}  # task_id -> Task
        self.task_queue = queue.PriorityQueue()
        self.max_concurrent_tasks = max_concurrent_tasks
        self.running_tasks = 0
        self.lock = threading.RLock()
        self.worker_threads = []
        self.running = False
        self.intent_patterns = self._register_intent_patterns()
        
    def initialize(self) -> bool:
        """
        Initialize the Task Manager.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        logger.info("Initializing Task Manager")
        
        try:
            self.running = True
            
            # Start worker threads
            for i in range(self.max_concurrent_tasks):
                thread = threading.Thread(
                    target=self._worker_thread,
                    name=f"TaskWorker-{i}",
                    daemon=True
                )
                thread.start()
                self.worker_threads.append(thread)
                
            # Register event handlers
            if self.event_bus:
                self.event_bus.subscribe_sync('task.create', self._handle_task_create_event)
                self.event_bus.subscribe_sync('task.cancel', self._handle_task_cancel_event)
                
            logger.info(f"Task Manager initialized with {self.max_concurrent_tasks} workers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Task Manager: {e}")
            return False
            
    def shutdown(self):
        """Shutdown the Task Manager and cancel all tasks."""
        logger.info("Shutting down Task Manager")
        self.running = False
        
        # Cancel all pending and running tasks
        with self.lock:
            for task_id, task in self.tasks.items():
                if task.status in ("pending", "running"):
                    task.cancel()
                    
            # Clear the queue
            while not self.task_queue.empty():
                try:
                    self.task_queue.get_nowait()
                    self.task_queue.task_done()
                except:
                    pass
        
        # Wait for worker threads to complete
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
                
        logger.info("Task Manager shutdown complete")
    
    def create_task(self, name: str, function: Callable, 
                   args: Tuple = None, kwargs: Dict = None,
                   priority: int = 5) -> str:
        """
        Create and queue a new task.
        
        Args:
            name: Human-readable name for the task
            function: Function to execute for this task
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            priority: Task priority (1-10, higher is more important)
            
        Returns:
            str: Task ID
        """
        # Use cryptographically secure random for task_id generation
        task_id = str(uuid.UUID(int=int.from_bytes(secrets.token_bytes(16), byteorder="big")))
        
        task = Task(
            task_id=task_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs,
            priority=priority
        )
        
        with self.lock:
            self.tasks[task_id] = task
            # Use negative priority so higher values are processed first
            self.task_queue.put((-priority, task_id, task))
            
        # Publish task created event
        if self.event_bus:
            self.event_bus.publish('task.created', {
                'task_id': task_id,
                'name': name,
                'priority': priority
            })
            
        logger.info(f"Created task {task_id} ({name}) with priority {priority}")
        return task_id
        
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task by its ID.
        
        Args:
            task_id: ID of the task to cancel
            
        Returns:
            bool: True if the task was cancelled, False otherwise
        """
        with self.lock:
            if task_id not in self.tasks:
                logger.warning(f"Attempt to cancel non-existent task {task_id}")
                return False
                
            task = self.tasks[task_id]
            cancelled = task.cancel()
            
            if cancelled and self.event_bus:
                self.event_bus.publish('task.cancelled', {
                    'task_id': task_id,
                    'name': task.name
                })
                
            return cancelled
    
    def get_task_status(self, task_id: str) -> Dict:
        """
        Get the status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Dict: Task status information or None if not found
        """
        with self.lock:
            if task_id not in self.tasks:
                return None
                
            return self.tasks[task_id].to_dict()
            
    def list_tasks(self, status_filter: str = None) -> List[Dict]:
        """
        List all tasks, optionally filtered by status.
        
        Args:
            status_filter: Filter tasks by status (pending, running, etc.)
            
        Returns:
            List[Dict]: List of task dictionaries
        """
        with self.lock:
            if status_filter:
                return [task.to_dict() for task in self.tasks.values() 
                        if task.status == status_filter]
            else:
                return [task.to_dict() for task in self.tasks.values()]
                
    def process_pending_tasks(self):
        """
        Process any pending tasks in the queue.
        This is called periodically by the continuous operation monitor.
        """
        # This method doesn't need to do anything active since worker threads
        # are continuously processing the queue. It can be used for health checks.
        with self.lock:
            pending_count = len([t for t in self.tasks.values() if t.status == "pending"])
            running_count = len([t for t in self.tasks.values() if t.status == "running"])
            
        logger.debug(f"Task status: {pending_count} pending, {running_count} running")
        
    def _worker_thread(self):
        """Worker thread that processes tasks from the queue."""
        logger.debug(f"Task worker thread started: {threading.current_thread().name}")
        
        while self.running:
            try:
                # Get the next task with the highest priority
                # Use a timeout to periodically check if we're still running
                try:
                    priority, _, task = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                    
                # Check if the task was cancelled while in the queue
                with self.lock:
                    if task.status == "cancelled":
                        self.task_queue.task_done()
                        continue
                        
                    self.running_tasks += 1
                
                # Execute the task
                try:
                    task.execute()
                finally:
                    with self.lock:
                        self.running_tasks -= 1
                    self.task_queue.task_done()
                    
                # Publish task completed event
                if self.event_bus:
                    self.event_bus.publish('task.completed', {
                        'task_id': task.task_id,
                        'name': task.name,
                        'status': task.status,
                        'duration': task.end_time - task.start_time if task.end_time else None,
                        'error': task.error
                    })
                    
            except Exception as e:
                logger.error(f"Error in task worker thread: {e}")
                
        logger.debug(f"Task worker thread ending: {threading.current_thread().name}")
    
    def _handle_task_create_event(self, event_data):
        """Handle task creation events from the event bus."""
        name = event_data.get('name', 'Unnamed Task')
        function = event_data.get('function')
        args = event_data.get('args', ())
        kwargs = event_data.get('kwargs', {})
        priority = event_data.get('priority', 5)
        
        if not function:
            logger.error("Task create event missing required 'function' parameter")
            return
            
        self.create_task(name, function, args, kwargs, priority)
    
    def _handle_task_cancel_event(self, event_data):
        """Handle task cancellation events from the event bus."""
        task_id = event_data.get('task_id')
        
        if not task_id:
            logger.error("Task cancel event missing required 'task_id' parameter")
            return
            
        self.cancel_task(task_id)
    
    def _register_intent_patterns(self) -> Dict:
        """
        Register intent patterns for task-related commands.
        
        Returns:
            Dict: Dictionary of intent patterns and their handlers
        """
        return {
            "create_task": [
                "create a task to {task_name}",
                "start a task that {task_name}",
                "run a task for {task_name}"
            ],
            "cancel_task": [
                "cancel task {task_id}",
                "stop the task {task_id}",
                "abort task {task_id}"
            ],
            "list_tasks": [
                "list all tasks",
                "show me the tasks",
                "what tasks are running"
            ],
            "task_status": [
                "what's the status of task {task_id}",
                "show me task {task_id}",
                "give me an update on task {task_id}"
            ]
        }
