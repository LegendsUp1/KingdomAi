#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kingdom AI System Event Handlers Module
Contains implementation of dashboard and system event handlers for TabManager
"""

import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger("KingdomAI.EventHandlers")

# System status event handler methods
async def update_system_status(self, event_type: str, event_data: Dict[str, Any]):
    """Update system status display when system.status events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing system status information
    """
    try:
        self.logger.debug(f"Received {event_type} event with data: {event_data}")
        
        if not event_data:
            self.logger.warning("Received empty system status data")
            return
            
        # Update dashboard status
        if 'status' in event_data:
            self.dashboard_status = event_data['status']
            
        # Update system status displays if dashboard tab is present
        if 'dashboard' in self.tab_frames:
            dashboard_frame = self.tab_frames['dashboard']
            
            # Update status labels if they exist
            if hasattr(dashboard_frame, 'status_label') and dashboard_frame.status_label:
                if self.using_pyqt:
                    dashboard_frame.status_label.setText(f"System Status: {self.dashboard_status}")
                elif self.using_tkinter:
                    dashboard_frame.status_label.config(text=f"System Status: {self.dashboard_status}")
                    
            # Update status in data dictionary
            self.dashboard_data['system_status'] = self.dashboard_status
            
            # Trigger additional status-based actions if needed
            if self.dashboard_status == "connected":
                self._schedule_async_task(self.request_dashboard_updates())
                
        self.logger.debug(f"System status updated: {self.dashboard_status}")
    except Exception as e:
        self.logger.error(f"Error updating system status: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_performance_metrics(self, event_type: str, event_data: Dict[str, Any]):
    """Update performance metrics display when system.performance events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing performance metrics
    """
    try:
        self.logger.debug(f"Received {event_type} event with data keys: {list(event_data.keys()) if event_data else 'None'}")
        
        if not event_data:
            self.logger.warning("Received empty performance metrics data")
            return
            
        # Store metrics in dashboard data
        if 'metrics' in event_data:
            self.dashboard_data['performance_metrics'] = event_data['metrics']
            
        # Update CPU/Memory/Disk charts if they exist
        if 'dashboard' in self.tab_frames:
            dashboard_frame = self.tab_frames['dashboard']
            
            # Update CPU usage
            if 'cpu_usage' in event_data and hasattr(dashboard_frame, 'cpu_label'):
                cpu_usage = event_data['cpu_usage']
                if self.using_pyqt:
                    dashboard_frame.cpu_label.setText(f"CPU: {cpu_usage:.1f}%")
                elif self.using_tkinter:
                    dashboard_frame.cpu_label.config(text=f"CPU: {cpu_usage:.1f}%")
                    
            # Update Memory usage
            if 'memory_usage' in event_data and hasattr(dashboard_frame, 'memory_label'):
                memory_usage = event_data['memory_usage']
                if self.using_pyqt:
                    dashboard_frame.memory_label.setText(f"Memory: {memory_usage:.1f}%")
                elif self.using_tkinter:
                    dashboard_frame.memory_label.config(text=f"Memory: {memory_usage:.1f}%")
                    
            # Update disk usage
            if 'disk_usage' in event_data and hasattr(dashboard_frame, 'disk_label'):
                disk_usage = event_data['disk_usage']
                if self.using_pyqt:
                    dashboard_frame.disk_label.setText(f"Disk: {disk_usage:.1f}%")
                elif self.using_tkinter:
                    dashboard_frame.disk_label.config(text=f"Disk: {disk_usage:.1f}%")
                    
        self.logger.debug("Performance metrics updated")
    except Exception as e:
        self.logger.error(f"Error updating performance metrics: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_recent_activity(self, event_type: str, event_data: Dict[str, Any]):
    """Update recent activity display when system.activity events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing recent activity information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty activity data")
            return
            
        # Store activity in dashboard data
        if 'activities' in event_data:
            self.dashboard_data['recent_activities'] = event_data['activities']
            
        # Update activity display if dashboard tab is present
        if 'dashboard' in self.tab_frames:
            dashboard_frame = self.tab_frames['dashboard']
            
            # Update activity list if it exists
            if hasattr(dashboard_frame, 'activity_list') and dashboard_frame.activity_list:
                activities = event_data.get('activities', [])
                
                if self.using_pyqt:
                    # Clear and update the list widget
                    dashboard_frame.activity_list.clear()
                    for activity in activities:
                        dashboard_frame.activity_list.addItem(f"{activity['time']} - {activity['description']}")
                elif self.using_tkinter:
                    # Clear and update the listbox
                    dashboard_frame.activity_list.delete(0, 'end')
                    for activity in activities:
                        dashboard_frame.activity_list.insert('end', f"{activity['time']} - {activity['description']}")
                        
        self.logger.debug("Recent activity updated")
    except Exception as e:
        self.logger.error(f"Error updating recent activity: {e}")
        import traceback
        self.logger.error(traceback.format_exc())

async def update_resource_metrics(self, event_type: str, event_data: Dict[str, Any]):
    """Update resource metrics display when system.resources events are received.
    
    Args:
        event_type: The type of event that triggered this handler
        event_data: Data payload containing resource usage information
    """
    try:
        self.logger.debug(f"Received {event_type} event")
        
        if not event_data:
            self.logger.warning("Received empty resource metrics data")
            return
            
        # Store resource metrics in dashboard data
        if 'resources' in event_data:
            self.dashboard_data['resource_metrics'] = event_data['resources']
            
        # Update resource displays if dashboard tab is present
        if 'dashboard' in self.tab_frames:
            dashboard_frame = self.tab_frames['dashboard']
            
            # Update network usage
            if 'network' in event_data and hasattr(dashboard_frame, 'network_label'):
                network_usage = event_data['network']
                if self.using_pyqt:
                    dashboard_frame.network_label.setText(f"Network: {network_usage} KB/s")
                elif self.using_tkinter:
                    dashboard_frame.network_label.config(text=f"Network: {network_usage} KB/s")
                    
            # Update GPU usage if available
            if 'gpu_usage' in event_data and hasattr(dashboard_frame, 'gpu_label'):
                gpu_usage = event_data['gpu_usage']
                if self.using_pyqt:
                    dashboard_frame.gpu_label.setText(f"GPU: {gpu_usage:.1f}%")
                elif self.using_tkinter:
                    dashboard_frame.gpu_label.config(text=f"GPU: {gpu_usage:.1f}%")
                    
        self.logger.debug("Resource metrics updated")
    except Exception as e:
        self.logger.error(f"Error updating resource metrics: {e}")
        import traceback
        self.logger.error(traceback.format_exc())
