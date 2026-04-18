#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Dummy RGB Border Manager for Kingdom AI.

This module provides a fallback implementation of the RGB Border Manager protocol
when the actual implementation is not available.
"""

import logging
from typing import Any, List, Tuple

class DummyRGBBorderManager:
    """Dummy implementation of RGB border manager with synchronous methods.
    Used as a fallback when the actual implementation is not available.
    """
    def __init__(self):
        self.logger = logging.getLogger("DummyRGBBorderManager")
        self.logger.warning("Using DummyRGBBorderManager - limited functionality")
        self._registered_elements = []
        self._frames = []
        self._running = False
        self._border_width = 2

    def add_frame(self, frame: Any) -> Any:
        """Add a frame to the border manager.
        
        Args:
            frame: The frame to add a border to
        """
        self.logger.debug(f"Dummy add_frame called with {frame}")
        self._frames.append(frame)
        return frame

    def register_element(self, element: Any, *args: Any, **kwargs: Any) -> None:
        """Register an element with the border manager.
        
        Args:
            element: The element to register
        """
        self.logger.debug(f"Dummy register_element called with {element}")
        if element not in self._registered_elements:
            self._registered_elements.append(element)

    def unregister_element(self, element: Any, *args: Any, **kwargs: Any) -> None:
        """Unregister an element from the border manager.
        
        Args:
            element: The element to unregister
        """
        self.logger.debug(f"Dummy unregister_element called with {element}")
        if element in self._registered_elements:
            self._registered_elements.remove(element)

    def start(self, *args: Any, **kwargs: Any) -> None:
        """Start the border manager.
        
        This is a dummy implementation that just logs the call.
        """
        self.logger.debug("Dummy start called")
        self._running = True

    def stop(self, *args: Any, **kwargs: Any) -> None:
        """Stop the border manager.
        
        This is a dummy implementation that just logs the call.
        """
        self.logger.debug("Dummy stop called")
        self._running = False

    def set_border_width(self, width: int) -> None:
        """Set the border width for all registered elements.
        
        Args:
            width (int): The width of the border in pixels.
        """
        try:
            self.logger.debug(f"Setting border width to {width}px")
            self._border_width = width
        except Exception as e:
            self.logger.error(f"Failed to set border width: {e}")

    def add_element(self, element: Any, color=(0, 0, 0), width=2) -> None:
        """Add an element to the border manager.
        
        This is a convenience method that is equivalent to register_element.
        
        Args:
            element: The element to add a border to
            color: RGB color tuple (r, g, b)
            width: Border width in pixels
        """
        try:
            self.logger.debug(f"Dummy add_element called with {element}, color={color}, width={width}")
            self.register_element(element)
        except Exception as e:
            self.logger.error(f"Error in add_element: {e}")

    def set_color(self, element: Any, color: tuple, *args: Any, **kwargs: Any) -> None:
        """Set the color for an element's border.
        
        Args:
            element: The element to set the color for
            color: RGB color tuple (r, g, b)
        """
        self.logger.debug(f"Dummy set_color called with {element}, color={color}")

    def set_element_border_width(self, element: Any, width: int) -> None:
        """Set the border width for a specific element.
        
        Args:
            element: The element to set the border width for
            width: Border width in pixels
        """
        self.logger.debug(f"Dummy set_element_border_width called with {element}, width={width}")

    def is_running(self) -> bool:
        """Check if the border manager is running.
        
        Returns:
            bool: True if running, False otherwise
        """
        return self._running
