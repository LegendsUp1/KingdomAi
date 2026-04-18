
#!/usr/bin/env python3
# ContinuousResponseGenerator Component for Kingdom AI
# Provides continuous streaming AI responses with asynchronous support

import asyncio
import logging
import time
import uuid
from typing import Dict, Any

from core.base_component import BaseComponent

logger = logging.getLogger('ContinuousResponseGenerator')

class ContinuousResponseGenerator(BaseComponent):
    """Component that generates continuous responses for streaming AI outputs"""
    
    def __init__(self, event_bus=None, config=None):
        super().__init__(name="ContinuousResponseGenerator", event_bus=event_bus, config=config)
        self.active_tasks = {}
        self.task_start_times = {}  # Track when each task was started
        self.failed_tasks = set()   # Track tasks that failed to cancel properly
        self.is_running = False
        self.emergency_stop = False  # Emergency stop flag for critical situations
        
        # Load custom responses from config if available
        self.responses = self.config.get('responses', {
            "thinking": [
                "Processing...",
                "Analyzing data...",
                "Running calculations...",
                "Computing results...",
                "Evaluating options...",
                "Searching database...",
                "Examining patterns...",
                "Synthesizing information...",
            ],
            "loading": [
                "Loading...",
                "Initializing...",
                "Preparing...",
                "Starting up...",
                "Setting up...",
                "Connecting...",
                "Establishing connections...",
                "Configuring system...",
            ]
        })
        
        # Get configuration options
        self.default_interval = self.config.get('default_interval', 2.0)
        self.enable_auto_stop = self.config.get('enable_auto_stop', True)
        
        # Task management
        self.task_lock = asyncio.Lock()
    
    async def initialize(self) -> bool:
        """Initialize the component
        
        Returns:
            bool: Success status
        """
        logger.info(f"Initializing {self.name}...")
        
        # Call base component initialize
        await super().initialize()
        
        # Reset state in case of re-initialization
        self.active_tasks = {}
        self.task_start_times = {}
        self.failed_tasks = set()
        self.emergency_stop = False
        
        # Configure task watchdog if enabled
        self.enable_watchdog = self.config.get('enable_watchdog', True)
        self.watchdog_interval = self.config.get('watchdog_interval', 30.0)  # Default 30 seconds
        self.watchdog_task = None
        
        # Get common timeouts from config
        self.task_timeout = self.config.get('task_timeout', 300.0)  # 5 minutes default maximum task lifetime
        
        # Subscribe to events
        if self.event_bus is not None:
            try:
                # Try to use the async subscribe method first
                if hasattr(self.event_bus, 'subscribe') and asyncio.iscoroutinefunction(self.event_bus.subscribe):
                    await self.event_bus.subscribe("ai.thinking.start", self._handle_thinking)
                    await self.event_bus.subscribe("ai.thinking.stop", self._handle_stop)
                    await self.event_bus.subscribe("ai.loading.start", self._handle_loading)
                    await self.event_bus.subscribe("ai.loading.stop", self._handle_stop)
                    await self.event_bus.subscribe("system.shutdown", self._handle_system_shutdown)
                    await self.event_bus.subscribe("user.input", self._handle_user_input)
                    await self.event_bus.subscribe("system.emergency_stop", self._handle_emergency_stop)
                    logger.info("Subscribed to events using async method")
                # Check for subscribe_sync method
                elif hasattr(self.event_bus, 'subscribe_sync'):
                    self.event_bus.subscribe_sync("ai.thinking.start", self._handle_thinking)
                    self.event_bus.subscribe_sync("ai.thinking.stop", self._handle_stop)
                    self.event_bus.subscribe_sync("ai.loading.start", self._handle_loading)
                    self.event_bus.subscribe_sync("ai.loading.stop", self._handle_stop)
                    self.event_bus.subscribe_sync("system.shutdown", self._handle_system_shutdown)
                    self.event_bus.subscribe_sync("user.input", self._handle_user_input)
                    self.event_bus.subscribe_sync("system.emergency_stop", self._handle_emergency_stop)
                    logger.info("Subscribed to events using sync method")
                else:
                    logger.warning("Event bus doesn't have subscribe or subscribe_sync methods")
            except Exception as e:
                logger.error(f"Error subscribing to events: {e}")
            
            # Start watchdog if enabled
            if self.enable_watchdog:
                self.watchdog_task = asyncio.create_task(self._run_watchdog())
                logger.info(f"Started task watchdog (interval: {self.watchdog_interval}s)")
        
        self.is_running = True
        logger.info(f"{self.name} initialized successfully")
        
        # Publish component status with additional success flag
        await self.safe_publish("system.component.status", {
            "component": self.name,
            "status": "initialized",
            "timestamp": time.time(),
            "success": True  # Explicitly set success flag to True
        })
        
        # Log explicit return value for debugging
        logger.info(f"{self.name} initialize method returning True")
        
        # Return success
        return True
    
    async def safe_publish(self, event_name, event_data=None):
        """Safely publish an event with error handling"""
        if self.event_bus is None:
            return False
            
        try:
            if hasattr(self.event_bus, 'publish') and asyncio.iscoroutinefunction(self.event_bus.publish):
                await self.event_bus.publish(event_name, event_data)
                return True
            elif hasattr(self.event_bus, 'publish_sync'):
                self.event_bus.publish_sync(event_name, event_data)
                return True
            else:
                logger.warning("Event bus doesn't have publish or publish_sync methods")
                return False
        except Exception as e:
            logger.error(f"Error publishing event {event_name}: {e}")
            return False
    
    async def _handle_thinking(self, data: Dict[str, Any]) -> bool:
        """Handle AI thinking event
        
        Args:
            data: Thinking event data
        """
        logger.debug(f"Handling thinking event: {data}")
        
        task_id = data.get("task_id", f"thinking_{int(time.time())}")
        interval = self.config.get("thinking_interval", 3.0)
        await self._handle_start({
            "task_id": task_id,
            "response_type": "thinking",
            "interval": interval
        })
        return True
    
    async def _handle_loading(self, data: Dict[str, Any]) -> bool:
        """Handle loading event
        
        Args:
            data: Loading event data
        """
        logger.debug(f"Handling loading event: {data}")
        
        task_id = data.get("task_id", f"loading_{int(time.time())}")
        interval = self.config.get("loading_interval", 1.0)
        await self._handle_start({
            "task_id": task_id,
            "response_type": "loading",
            "interval": interval
        })
        return True
    
    async def _handle_start(self, data):
        """Start continuous response"""
        if data is None:
            data = {}
        
        # If emergency stop is active, don't start new tasks
        if self.emergency_stop:
            logger.warning("Emergency stop active, not starting new task")
            return
            
        task_id = data.get("task_id", f"task_{uuid.uuid4()}")
        response_type = data.get("response_type", "thinking")
        interval = data.get("interval", self.default_interval)
        
        # Get task-specific timeout (or use default)
        timeout = data.get("timeout", self.task_timeout)
        
        logger.info(f"Starting continuous response task {task_id} of type {response_type}")
        
        # Create and store the task
        async with self.task_lock:
            # Cancel existing task with same ID if it exists
            if task_id in self.active_tasks:
                try:
                    logger.info(f"Cancelling existing task with same ID: {task_id}")
                    self.active_tasks[task_id].cancel()
                    if task_id in self.task_start_times:
                        del self.task_start_times[task_id]
                except Exception as e:
                    logger.error(f"Error cancelling existing task {task_id}: {e}")
                
            # Create new task
            try:
                task = asyncio.create_task(
                    self._generate_responses(task_id, response_type, interval)
                )
                self.active_tasks[task_id] = task
                self.task_start_times[task_id] = time.time()
                
                # Add done callback to clean up task when it finishes
                task.add_done_callback(lambda t: asyncio.create_task(self._on_task_done(task_id, t)))
                
                logger.info(f"Started continuous response task {task_id}")
            except Exception as e:
                logger.error(f"Failed to start task {task_id}: {e}")
    
    async def _handle_stop(self, data: Dict[str, Any]) -> bool:
        """Stop continuous response
        
        Args:
            data: Stop event data
            
        Returns:
            bool: Success status
        """
        logger.debug(f"Handling stop event: {data}")
        
        task_id = data.get("task_id", None)
        
        if task_id is None:
            # Stop all tasks if no specific task ID
            logger.info("No task ID provided, stopping all tasks")
            await self._stop_all_tasks()
            return True
            
        # Stop specific task
        async with self.task_lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                
                if not task.done():
                    logger.info(f"Cancelling task {task_id}")
                    task.cancel()
                    
                    try:
                        # Wait for task to be cancelled
                        await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"Task {task_id} did not cancel within timeout")
                    except asyncio.CancelledError:
                        logger.info(f"Task {task_id} cancelled successfully")
                    except Exception as e:
                        logger.error(f"Error cancelling task {task_id}: {e}")
        
        return True
    
    async def _handle_user_input(self, data: Dict[str, Any]) -> bool:
        """Handle user input events by stopping continuous responses
        
        Args:
            data: User input event data
            
        Returns:
            bool: Success status
        """
        if not self.enable_auto_stop:
            return True
            
        # Automatically stop all responses when user inputs something
        logger.debug("User input detected, stopping continuous responses")
        await self._stop_all_tasks()
        return True
    
    async def _handle_system_shutdown(self, event_data: Dict[str, Any]):
        """Handle system shutdown events by stopping all ongoing tasks
        
        Args:
            event_data: Shutdown event data
        """
        logger.info("Received system shutdown event")
        
        # Stop all tasks
        await self._stop_all_tasks(force=True)
        
        # Set emergency stop flag to prevent new tasks
        self.emergency_stop = True
        
        # Stop the component
        if self.is_running:
            await self.stop()
            
    async def _stop_all_tasks(self, force=False):
        """Stop all active tasks
        
        Args:
            force: If True, use more aggressive measures to stop tasks
        """
        async with self.task_lock:
            active_task_count = len(self.active_tasks)
            if active_task_count == 0:
                logger.info("No active tasks to stop")
                return
                
            logger.info(f"Stopping all {active_task_count} active continuous response tasks (force={force})")
            stopped_count = 0
            failed_count = 0
            
            for task_id, task in list(self.active_tasks.items()):
                try:
                    logger.info(f"Cancelling task {task_id}")
                    task.cancel()
                    
                    # If force is True, don't wait for clean cancellation
                    if not force:
                        # Give the task a short time to clean up
                        try:
                            await asyncio.wait_for(asyncio.shield(task), 0.5)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            # This is expected - task was cancelled
                            pass
                    
                    # Remove from tracking
                    del self.active_tasks[task_id]
                    if task_id in self.task_start_times:
                        del self.task_start_times[task_id]
                    
                    stopped_count += 1
                except Exception as e:
                    logger.error(f"Error cancelling task {task_id}: {e}")
                    failed_count += 1
                    # Add to failed tasks for the watchdog to handle
                    self.failed_tasks.add(task_id)
            
            logger.info(f"Task cancellation complete: {stopped_count} stopped, {failed_count} failed")
    
    async def _generate_responses(self, task_id, response_type, interval):
        """Generate continuous responses of the specified type"""
        try:
            responses = self.responses.get(response_type, [])
            if not responses:
                logger.warning(f"No responses available for type {response_type}")
                return
            
            # Get max iterations from config (0 or negative means unlimited)
            max_iterations = self.config.get(f"{response_type}_max_iterations", 0)
            max_duration = self.config.get(f"{response_type}_max_duration", 0)  # In seconds
            start_time = time.time()
            
            logger.info(f"Starting {response_type} response generation for task {task_id}")
            logger.info(f"  Max iterations: {max_iterations if max_iterations > 0 else 'unlimited'}")
            logger.info(f"  Max duration: {max_duration if max_duration > 0 else 'unlimited'} seconds")
            logger.info(f"  Interval: {interval} seconds")
                
            index = 0
            while True:
                # Check if we've reached max iterations (if configured)
                if max_iterations > 0 and index >= max_iterations:
                    logger.info(f"Reached max iterations ({max_iterations}) for {response_type} task {task_id}")
                    break
                
                # Check if we've exceeded max duration (if configured)
                if max_duration > 0 and (time.time() - start_time) > max_duration:
                    logger.info(f"Reached max duration ({max_duration}s) for {response_type} task {task_id}")
                    break
                
                # Get the current response
                response = responses[index % len(responses)]
                
                # Check if task has been cancelled
                try:
                    # Publish the response
                    await self.safe_publish(f"ai.{response_type}.update", {
                        "task_id": task_id,
                        "response": response,
                        "timestamp": time.time()
                    })
                    
                    # Increment index and wait
                    index += 1
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    logger.info(f"Task {task_id} was cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Error in response generation for task {task_id}: {e}")
                    await asyncio.sleep(interval)  # Still wait to avoid rapid errors
        except asyncio.CancelledError:
            # Task was cancelled, clean exit
            pass
        except Exception as e:
            logger.error(f"Error in continuous response generation: {str(e)}")
            # Publish error
            await self.safe_publish("component.error", {
                "component": self.name,
                "error": str(e),
                "timestamp": time.time()
            })
    
    async def _handle_emergency_stop(self, data: Dict[str, Any]):
        """Handle emergency stop events
        
        Args:
            data: Emergency stop event data
        """
        logger.warning(f"EMERGENCY STOP triggered: {data}")
        
        # Set emergency stop flag
        self.emergency_stop = True
        
        # Stop all tasks
        await self._stop_all_tasks(force=True)
        
    async def handle_request(self, data: Dict[str, Any]) -> bool:
        """Handle system request events
        
        This method processes incoming system.request events and generates appropriate responses.
        It is registered as a handler for the "system.request" event.
        
        Args:
            data: Request event data which may contain:
                - request_type: Type of request (e.g., "status", "help", "info")
                - source: Source of the request (e.g., "user", "system", "component")
                - details: Additional request details
                - response_channel: Optional channel to send response to
                
        Returns:
            bool: Success status
        """
        logger.info(f"Handling system request: {data}")
        
        request_type = data.get("request_type", "unknown")
        source = data.get("source", "unknown")
        details = data.get("details", {})
        response_channel = data.get("response_channel", "system.response")
        
        # Process different request types
        if request_type == "status":
            # Generate status response
            response = {
                "status": "active" if self.is_running else "inactive",
                "active_tasks": len(self.active_tasks),
                "emergency_stop": self.emergency_stop,
                "timestamp": time.time()
            }
        elif request_type == "help":
            # Generate help response
            response = {
                "available_commands": ["status", "help", "stop", "emergency_stop"],
                "usage": "Send requests to system.request with request_type and optional details"
            }
        else:
            # Generic response for other request types
            response = {
                "received": request_type,
                "processed": True,
                "timestamp": time.time()
            }
        
        # Add request metadata to response
        response["request_id"] = data.get("request_id", f"req_{int(time.time())}")
        response["source"] = source
        
        # Publish response
        try:
            await self.safe_publish(response_channel, {
                "response": response,
                "original_request": data,
                "timestamp": time.time()
            })
            logger.info(f"Published response to {response_channel}")
            return True
        except Exception as e:
            logger.error(f"Error publishing response: {e}")
            return False
            
    async def handle_response(self, data: Dict[str, Any]) -> bool:
        """Handle system response events
        
        This method processes incoming system.response events and generates appropriate follow-up actions.
        It is registered as a handler for the "system.response" event.
        
        Args:
            data: Response event data which may contain:
                - response: The response data
                - original_request: The original request that generated this response
                - timestamp: When the response was generated
                
        Returns:
            bool: Success status
        """
        logger.info(f"Handling system response: {data}")
        
        response = data.get("response", {})
        original_request = data.get("original_request", {})
        timestamp = data.get("timestamp", time.time())
        
        # Extract response metadata
        request_id = response.get("request_id", "unknown")
        source = response.get("source", "unknown")
        
        # Log received response
        logger.debug(f"Received response for request {request_id} from {source}")
        
        # Handle different response types based on the original request
        if original_request.get("request_type") == "status":
            # Status response handling
            if "status" in response:
                logger.info(f"Status report: {response['status']}")
                
                # Optionally publish a status display event
                await self.safe_publish("display.status", {
                    "status": response["status"],
                    "details": response,
                    "timestamp": time.time()
                })
        
        # Process any follow-up actions based on the response
        follow_up = original_request.get("follow_up", False)
        if follow_up:
            logger.debug(f"Processing follow-up for request {request_id}")
            # Handle any follow-up actions here
            
        return True
    
    async def _on_task_done(self, task_id, task):
        """Clean up task when it completes"""
        try:
            # Remove the task from tracking
            async with self.task_lock:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                if task_id in self.task_start_times:
                    del self.task_start_times[task_id]
                if task_id in self.failed_tasks:
                    self.failed_tasks.remove(task_id)
            
            # Check if task ended with an exception (other than cancellation)
            if not task.cancelled():
                try:
                    # This will re-raise any exception
                    task.result()
                    logger.info(f"Task {task_id} completed successfully")
                except asyncio.CancelledError:
                    # Task was cancelled - this is normal
                    logger.info(f"Task {task_id} was cancelled")
                except Exception as e:
                    logger.error(f"Task {task_id} failed with error: {e}")
        except Exception as e:
            logger.error(f"Error in _on_task_done for {task_id}: {e}")
    
    async def _run_watchdog(self):
        """Watchdog task to detect and clean up hanging tasks"""
        logger.info(f"Watchdog started with interval {self.watchdog_interval}s")
        try:
            while self.is_running:
                await asyncio.sleep(self.watchdog_interval)
                await self._check_tasks()
        except asyncio.CancelledError:
            logger.info("Watchdog task cancelled")
        except Exception as e:
            logger.error(f"Error in watchdog task: {e}")
    
    async def _check_tasks(self):
        """Check all tasks and clean up any that have been running too long"""
        current_time = time.time()
        async with self.task_lock:
            # Check for tasks that have been running too long
            for task_id, start_time in list(self.task_start_times.items()):
                task_age = current_time - start_time
                if task_id in self.active_tasks and task_age > self.task_timeout:
                    logger.warning(f"Task {task_id} has been running for {task_age:.1f}s, exceeding timeout of {self.task_timeout}s")
                    try:
                        self.active_tasks[task_id].cancel()
                        logger.info(f"Cancelled overdue task {task_id}")
                    except Exception as e:
                        logger.error(f"Error cancelling overdue task {task_id}: {e}")
            
            # Clean up any tasks in failed_tasks that are still in active_tasks
            for task_id in list(self.failed_tasks):
                if task_id in self.active_tasks:
                    logger.warning(f"Cleaning up previously failed task {task_id}")
                    try:
                        self.active_tasks[task_id].cancel()
                        del self.active_tasks[task_id]
                        if task_id in self.task_start_times:
                            del self.task_start_times[task_id]
                        self.failed_tasks.remove(task_id)
                    except Exception as e:
                        logger.error(f"Error cleaning up failed task {task_id}: {e}")
            
            # Log status
            active_count = len(self.active_tasks)
            if active_count > 0:
                logger.info(f"Watchdog: {active_count} active tasks, {len(self.failed_tasks)} failed tasks")
                
    async def start(self) -> bool:
        """Start the continuous response generator.
        
        This method starts the continuous response generator and allows it to
        generate responses. It sets the is_running flag to True and starts
        the watchdog task if enabled.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        logger.info(f"Starting {self.name}")
        
        if self.is_running:
            logger.warning(f"{self.name} is already running")
            return True
            
        self.is_running = True
        self.emergency_stop = False
        
        # Start watchdog if enabled
        if self.enable_watchdog and not self.watchdog_task:
            self.watchdog_task = asyncio.create_task(self._run_watchdog())
            logger.info(f"Started task watchdog (interval: {self.watchdog_interval}s)")
        
        # Publish started status
        await self.safe_publish("system.component.status", {
            "component": self.name,
            "status": "started",
            "timestamp": time.time()
        })
        
        logger.info(f"{self.name} started successfully")
        return True
    
    async def stop(self):
        """Stop the continuous response generator.
        
        This method stops the continuous response generator by cancelling all active
        tasks and stopping the watchdog task. It sets the is_running flag to False.
        
        Returns:
            bool: True if stopped successfully, False otherwise
        """
        logger.info(f"Stopping {self.name}")
        
        if not self.is_running:
            logger.warning(f"{self.name} is not running")
            return True
            
        # Set emergency stop to prevent new tasks
        self.emergency_stop = True
        
        # Stop all active tasks
        await self._stop_all_tasks(force=True)
        
        # Stop watchdog if running
        if self.watchdog_task and not self.watchdog_task.done():
            try:
                self.watchdog_task.cancel()
                logger.info("Watchdog task cancelled")
            except Exception as e:
                logger.error(f"Error cancelling watchdog task: {e}")
        
        self.is_running = False
        
        # Publish stopped status
        await self.safe_publish("system.component.status", {
            "component": self.name,
            "status": "stopped",
            "timestamp": time.time()
        })
        
        logger.info(f"{self.name} stopped successfully")
        return True
    
    async def generate_response(self, response_type="thinking", task_id=None, interval=None, max_iterations=None, max_duration=None):
        """Generate a continuous response.
        
        This method starts a new continuous response task with the specified parameters.
        It creates a new task ID if one is not provided.
        
        Args:
            response_type (str): Type of response to generate (e.g., 'thinking', 'loading')
            task_id (str, optional): Task ID for the response. If None, one will be generated.
            interval (float, optional): Interval between responses in seconds.
            max_iterations (int, optional): Maximum number of responses to generate.
            max_duration (float, optional): Maximum duration in seconds to generate responses.
            
        Returns:
            str: The task ID for the generated response
        """
        if not self.is_running:
            logger.warning(f"{self.name} is not running, starting it first")
            await self.start()
            
        # If emergency stop is active, don't start new tasks
        if self.emergency_stop:
            logger.warning("Emergency stop active, not starting new response generation")
            return None
            
        # Generate task ID if not provided
        if task_id is None:
            task_id = f"response_{uuid.uuid4()}"
            
        # Use default interval if not provided
        if interval is None:
            interval = self.config.get(f"{response_type}_interval", self.default_interval)
            
        # Get task-specific timeout (or use default)
        timeout = self.task_timeout
        
        logger.info(f"Generating {response_type} response for task {task_id} with interval {interval}s")
        
        # Create data dictionary for task
        data = {
            "task_id": task_id,
            "response_type": response_type,
            "interval": interval
        }
        
        # Add optional parameters if provided
        if max_iterations is not None:
            data[f"{response_type}_max_iterations"] = max_iterations
            
        if max_duration is not None:
            data[f"{response_type}_max_duration"] = max_duration
            
        # Start the continuous response task
        await self._handle_start(data)
        
        return task_id
