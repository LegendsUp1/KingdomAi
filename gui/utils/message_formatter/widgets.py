"""
Message widget implementation for the Thoth AI Qt chat interface.

This module provides the MessageWidget class for displaying formatted messages
in the chat interface with interactive elements and rich styling.
"""

from typing import Optional, Dict, Any, List, Tuple, Union

from PyQt6.QtCore import (
    Qt, QSize, QUrl, QTimer, QPropertyAnimation, QEasingCurve, QRectF,
    pyqtSignal, pyqtSlot, pyqtProperty, QEvent, QPointF, QRect
)
from PyQt6.QtGui import (
    QTextDocument, QTextCursor, QTextCharFormat, QTextBlockFormat,
    QTextFormat, QTextFrameFormat, QTextTableFormat, QTextLength,
    QTextImageFormat, QColor, QFont, QFontMetrics, QPainter, QPixmap,
    QLinearGradient, QBrush, QIcon, QDesktopServices, QTextDocumentFragment,
    QMouseEvent, QResizeEvent, QContextMenuEvent, QKeyEvent, QPainterPath,
    QPen, QPalette, QAction, QClipboard, QGuiApplication
)
from PyQt6.QtWidgets import (
    QTextBrowser, QTextEdit, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QSizePolicy, QFrame, QMenu, QApplication,
    QStyle, QStyleOption, QStylePainter, QToolButton, QSpacerItem,
    QScrollArea, QSizeGrip, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QFileDialog
)

from core.styles import COLORS, FONTS, get_color, get_font


class MessageWidget(QTextBrowser):
    """A widget for displaying formatted chat messages with rich content."""
    
    # Signals
    messageActionTriggered = pyqtSignal(str, dict)  # action_name, action_data
    action_triggered = pyqtSignal(str, dict)  # Alias for backwards compatibility
    linkHovered = pyqtSignal(str)  # URL
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._message_data = {}
        self._is_user = False
        self._is_active = True
        self._highlight_on_hover = False
        self._highlight_color = QColor(COLORS['accent'])
        self._highlight_opacity = 0.1
        self._corner_radius = 8
        self._shadow_enabled = True
        self._shadow_radius = 8
        self._shadow_offset = QPointF(0, 2)
        self._shadow_color = QColor(0, 0, 0, 30)
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Initialize the message widget UI."""
        # Basic properties
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)  # We'll handle link clicks ourselves
        self.setOpenLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.document().setDocumentMargin(8)
        
        # Enable hover events
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        
        # Set up document styles
        self.document().setDefaultStyleSheet(self._get_stylesheet())
        
        # Set up context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.anchorClicked.connect(self._handle_link_clicked)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect action_triggered to messageActionTriggered for backwards compatibility
        self.messageActionTriggered.connect(lambda action, data: self.action_triggered.emit(action, data))
    
    def set_message_data(self, data: Dict[str, Any]):
        """Set the message data to display.
        
        Args:
            data: Dictionary containing message data including 'text', 'sender', 'timestamp', etc.
        """
        self._message_data = data
        self._is_user = data.get('is_user', False)
        
        # Update content
        self._update_content()
    
    def message_data(self) -> Dict[str, Any]:
        """Get the current message data.
        
        Returns:
            Dictionary containing the message data.
        """
        return self._message_data
    
    def set_highlight_on_hover(self, enable: bool):
        """Set whether to highlight the message on hover.
        
        Args:
            enable: Whether to enable hover highlighting.
        """
        self._highlight_on_hover = enable
        self.update()
    
    def highlight_on_hover(self) -> bool:
        """Get whether hover highlighting is enabled.
        
        Returns:
            bool: True if hover highlighting is enabled, False otherwise.
        """
        return self._highlight_on_hover
    
    def set_highlight_color(self, color: QColor):
        """Set the highlight color.
        
        Args:
            color: The color to use for highlighting.
        """
        self._highlight_color = color
        self.update()
    
    def highlight_color(self) -> QColor:
        """Get the highlight color.
        
        Returns:
            QColor: The current highlight color.
        """
        return self._highlight_color
    
    def set_highlight_opacity(self, opacity: float):
        """Set the highlight opacity.
        
        Args:
            opacity: The opacity value (0.0 to 1.0).
        """
        self._highlight_opacity = max(0.0, min(1.0, opacity))
        self.update()
    
    def highlight_opacity(self) -> float:
        """Get the highlight opacity.
        
        Returns:
            float: The current highlight opacity.
        """
        return self._highlight_opacity
    
    def set_corner_radius(self, radius: int):
        """Set the corner radius of the message bubble.
        
        Args:
            radius: The corner radius in pixels.
        """
        self._corner_radius = max(0, radius)
        self.update()
    
    def corner_radius(self) -> int:
        """Get the corner radius of the message bubble.
        
        Returns:
            int: The current corner radius in pixels.
        """
        return self._corner_radius
    
    def set_shadow_enabled(self, enabled: bool):
        """Set whether to enable the drop shadow.
        
        Args:
            enabled: Whether to enable the drop shadow.
        """
        self._shadow_enabled = enabled
        self.update()
    
    def is_shadow_enabled(self) -> bool:
        """Get whether the drop shadow is enabled.
        
        Returns:
            bool: True if the drop shadow is enabled, False otherwise.
        """
        return self._shadow_enabled
    
    def set_shadow_radius(self, radius: int):
        """Set the shadow radius.
        
        Args:
            radius: The shadow radius in pixels.
        """
        self._shadow_radius = max(0, radius)
        self.update()
    
    def shadow_radius(self) -> int:
        """Get the shadow radius.
        
        Returns:
            int: The current shadow radius in pixels.
        """
        return self._shadow_radius
    
    def set_shadow_offset(self, offset: QPointF):
        """Set the shadow offset.
        
        Args:
            offset: The shadow offset as a QPointF.
        """
        self._shadow_offset = offset
        self.update()
    
    def shadow_offset(self) -> QPointF:
        """Get the shadow offset.
        
        Returns:
            QPointF: The current shadow offset.
        """
        return self._shadow_offset
    
    def set_shadow_color(self, color: QColor):
        """Set the shadow color.
        
        Args:
            color: The shadow color.
        """
        self._shadow_color = color
        self.update()
    
    def shadow_color(self) -> QColor:
        """Get the shadow color.
        
        Returns:
            QColor: The current shadow color.
        """
        return self._shadow_color
    
    def sizeHint(self) -> QSize:
        """Get the recommended size for the widget.
        
        Returns:
            QSize: The recommended size.
        """
        # Calculate the ideal width based on the document
        doc = self.document().clone()
        doc.setTextWidth(self.viewport().width())
        
        # Add some padding
        margin = self.document().documentMargin()
        width = doc.idealWidth() + margin * 2
        height = doc.size().height() + margin * 2
        
        # Add some extra space for the shadow
        if self._shadow_enabled:
            width += self._shadow_radius * 2
            height += self._shadow_radius * 2
        
        return QSize(int(width), int(height))
    
    def minimumSizeHint(self) -> QSize:
        """Get the minimum size for the widget.
        
        Returns:
            QSize: The minimum size.
        """
        return QSize(100, 40)
    
    def event(self, event: QEvent) -> bool:
        """Handle events for the widget.
        
        Args:
            event: The event to handle.
            
        Returns:
            bool: True if the event was handled, False otherwise.
        """
        # Handle hover events for highlighting
        if event.type() == QEvent.Enter:
            self._handle_hover_enter()
        elif event.type() == QEvent.Leave:
            self._handle_hover_leave()
        
        return super().event(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events.
        
        Args:
            event: The mouse event.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if we clicked on a link
            anchor = self.anchorAt(event.pos())
            if anchor:
                self._handle_link_clicked(QUrl(anchor))
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events.
        
        Args:
            event: The mouse event.
        """
        # Update cursor if over a link
        anchor = self.anchorAt(event.pos())
        if anchor:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            self.linkHovered.emit(anchor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        
        super().mouseMoveEvent(event)
    
    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events.
        
        Args:
            event: The resize event.
        """
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())
    
    def contextMenuEvent(self, event: QContextMenuEvent):
        """Handle context menu events.
        
        Args:
            event: The context menu event.
        """
        self._show_context_menu(event.globalPos())
    
    def _update_content(self):
        """Update the widget's content based on the current message data."""
        if not self._message_data:
            self.clear()
            return
        
        # Get the formatted HTML for the message
        from .formatter import MessageFormatter
        
        message_type = self._message_data.get('type', 'text')
        text = self._message_data.get('text', '')
        sender = self._message_data.get('sender', '')
        timestamp = self._message_data.get('timestamp')
        metadata = self._message_data.get('metadata', {})
        
        # Set the HTML content
        html = MessageFormatter.format_message(
            text=text,
            message_type=message_type,
            sender=sender,
            timestamp=timestamp,
            metadata=metadata
        )
        
        self.setHtml(html)
        self.document().setDefaultStyleSheet(self._get_stylesheet())
        
        # Update the document's text width to ensure proper sizing
        self.document().setTextWidth(self.viewport().width())
        
        # Update the widget's size hint
        self.updateGeometry()
    
    def _get_stylesheet(self) -> str:
        """Get the stylesheet for the message widget.
        
        Returns:
            str: The CSS stylesheet.
        """
        bg_color = COLORS['accent'] if self._is_user else COLORS['bg_secondary']
        text_color = COLORS['text_primary'] if self._is_user else COLORS['text_primary']
        border_color = COLORS['accent'] if self._is_user else COLORS['border']
        
        return f"""
        body {{
            font-family: {FONTS['default']};
            font-size: {FONTS['sizes']['normal']}px;
            color: {text_color};
            margin: 0;
            padding: 0;
        }}
        .message {{
            background-color: {bg_color};
            color: {text_color};
            border: 1px solid {border_color};
            border-radius: {self._corner_radius}px;
            padding: 8px 12px;
            margin: 4px 0;
            max-width: 80%;
            display: inline-block;
            word-wrap: break-word;
        }}
        .message-header {{
            font-size: 0.9em;
            margin-bottom: 4px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .message-sender {{
            font-weight: bold;
            margin-right: 8px;
        }}
        .message-time {{
            opacity: 0.7;
            font-size: 0.8em;
        }}
        .message-content {{
            margin: 4px 0;
        }}
        .message-footer {{
            display: flex;
            justify-content: flex-end;
            align-items: center;
            margin-top: 4px;
            font-size: 0.8em;
        }}
        .message-actions {{
            display: flex;
            gap: 4px;
            opacity: 0;
            transition: opacity 0.2s;
        }}
        .message:hover .message-actions {{
            opacity: 1;
        }}
        .message-action {{
            background: none;
            border: none;
            color: inherit;
            opacity: 0.7;
            cursor: pointer;
            padding: 2px 4px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .message-action:hover {{
            opacity: 1;
            background-color: rgba(0, 0, 0, 0.1);
        }}
        .message-status {{
            margin-left: 8px;
            font-size: 0.8em;
            opacity: 0.7;
        }}
        .code-block {{
            background-color: rgba(0, 0, 0, 0.1);
            border-radius: 4px;
            padding: 8px;
            margin: 4px 0;
            overflow-x: auto;
            font-family: {FONTS['monospace']};
        }}
        .inline-code {{
            font-family: {FONTS['monospace']};
            background-color: rgba(0, 0, 0, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .mention {{
            font-weight: 500;
            color: {COLORS['accent']};
            background-color: rgba(0, 122, 255, 0.1);
            padding: 0 4px;
            border-radius: 3px;
        }}
        a {{
            color: {COLORS['accent']};
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        """
    
    def _handle_link_clicked(self, url: QUrl):
        """Handle when a link is clicked in the message.
        
        Args:
            url: The URL that was clicked.
        """
        url_str = url.toString()
        
        # Check if this is an internal action link (starts with 'action:')
        if url_str.startswith('action:'):
            action = url_str[7:]  # Remove 'action:' prefix
            self.messageActionTriggered.emit(action, self._message_data)
        else:
            # Default behavior: open in external browser
            QDesktopServices.openUrl(url)
    
    def _show_context_menu(self, pos):
        """Show the context menu at the given position.
        
        Args:
            pos: The position to show the menu at.
        """
        menu = QMenu(self)
        
        # Add standard actions
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)
        
        # Add reply action if this is not the user's own message
        if not self._is_user:
            reply_action = QAction("Reply", self)
            reply_action.triggered.connect(lambda: self.messageActionTriggered.emit('reply', self._message_data))
            menu.addAction(reply_action)
        
        # Add reaction action
        react_action = QAction("Add Reaction", self)
        react_action.triggered.connect(lambda: self.messageActionTriggered.emit('add_reaction', self._message_data))
        menu.addAction(react_action)
        
        # Show the menu
        menu.exec_(pos)
    
    def _copy_to_clipboard(self):
        """Copy the message text to the clipboard."""
        clipboard = QApplication.clipboard()
        text = self._message_data.get('text', '')
        
        if text:
            clipboard.setText(text)
    
    def _handle_hover_enter(self):
        """Handle when the mouse enters the widget."""
        if self._highlight_on_hover:
            self._update_highlight(True)
    
    def _handle_hover_leave(self):
        """Handle when the mouse leaves the widget."""
        if self._highlight_on_hover:
            self._update_highlight(False)
    
    def _update_highlight(self, highlight: bool):
        """Update the highlight state of the widget.
        
        Args:
            highlight: Whether to highlight the widget.
        """
        if highlight:
            color = self._highlight_color
            color.setAlphaF(self._highlight_opacity)
            self.setStyleSheet(f"background-color: {color.name(QColor.HexArgb)};")
        else:
            self.setStyleSheet("")
    
    def paintEvent(self, event):
        """Handle paint events.
        
        Args:
            event: The paint event.
        """
        # Set up the painter
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate the content rect (accounting for margins)
        margin = self.document().documentMargin()
        content_rect = self.contentsRect().adjusted(
            margin, margin, -margin, -margin
        )
        
        # Draw the background if needed
        if self._highlight_on_hover and self.underMouse():
            color = self._highlight_color
            color.setAlphaF(self._highlight_opacity * 255)
            painter.fillRect(content_rect, color)
        
        # Let the base class handle the rest
        super().paintEvent(event)
        
        # Draw the drop shadow if enabled
        if self._shadow_enabled and self._shadow_radius > 0:
            self._draw_drop_shadow(painter, content_rect)
    
    def _draw_drop_shadow(self, painter: QPainter, rect: QRect):
        """Draw a drop shadow around the widget.
        
        Args:
            painter: The painter to use for drawing.
            rect: The rectangle to draw the shadow around.
        """
        # Save the painter state
        painter.save()
        
        # Set up the shadow color
        shadow_color = self._shadow_color
        
        # Draw the shadow
        path = QPainterPath()
        path.addRoundedRect(
            rect.adjusted(
                self._shadow_radius,
                self._shadow_radius,
                -self._shadow_radius,
                -self._shadow_radius
            ),
            self._corner_radius,
            self._corner_radius
        )
        
        # Apply the shadow effect
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(self._shadow_radius)
        shadow_effect.setColor(shadow_color)
        shadow_effect.setOffset(self._shadow_offset)
        
        # Apply the effect to the painter
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Draw the shadow
        painter.fillPath(path, shadow_color)
        
        # Restore the painter state
        painter.restore()


class MessageWidgetFactory:
    """Factory for creating message widgets with different styles."""
    
    @staticmethod
    def create_message_widget(
        message_data: Dict[str, Any],
        parent: Optional[QWidget] = None
    ) -> MessageWidget:
        """Create a message widget with the given data.
        
        Args:
            message_data: Dictionary containing message data.
            parent: The parent widget.
            
        Returns:
            MessageWidget: The created message widget.
        """
        widget = MessageWidget(parent)
        widget.set_message_data(message_data)
        
        # Apply additional styling based on message type
        message_type = message_data.get('type', 'text')
        is_user = message_data.get('is_user', False)
        
        if is_user:
            widget.set_highlight_color(QColor(COLORS['accent']))
            widget.set_highlight_opacity(0.1)
            widget.set_highlight_on_hover(True)
        else:
            widget.set_highlight_color(QColor(COLORS['bg_tertiary']))
            widget.set_highlight_opacity(0.1)
            widget.set_highlight_on_hover(True)
        
        # Special styling for system messages
        if message_type == 'system':
            widget.set_highlight_on_hover(False)
        
        return widget
