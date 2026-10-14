"""
Breadcrumb navigation module for Shadows File Explorer.

This module provides the FixedBreadcrumbBar class which displays the current path
as clickable breadcrumb components for easy navigation.
"""
import os
import platform
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QScrollArea, QPushButton,
                            QLabel, QToolButton, QLineEdit, QCompleter)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QDir
from PyQt6.QtGui import QFileSystemModel


class FixedBreadcrumbBar(QWidget):
    """A breadcrumb-style path navigation bar with stable positioning.
    
    This component provides:
    - Path display as clickable segments
    - Horizontal scrolling for long paths
    - Path parsing and navigation
    
    Signals:
        path_changed: Emitted when a path component is clicked (path)
    """
    
    path_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the breadcrumb bar.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setFixedHeight(32)
        # Needed for the themed border and background on a QWidget subclass
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(4, 0, 4, 0)
        self.main_layout.setSpacing(0)
        
        # Create a scrollable area for breadcrumbs
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QLabel.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container widget for breadcrumbs
        self.container = QWidget()
        self.layout = QHBoxLayout(self.container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)
        
        self.buttons = []
        self.separators = []
        
        # Add left and right scroll buttons
        self.left_scroll = QToolButton()
        self.left_scroll.setText("‹")
        self.left_scroll.setToolTip("Scroll left")
        self.left_scroll.clicked.connect(self.scroll_left)
        self.left_scroll.setVisible(False)
        
        self.right_scroll = QToolButton()
        self.right_scroll.setText("›")
        self.right_scroll.setToolTip("Scroll right")
        self.right_scroll.clicked.connect(self.scroll_right)
        self.right_scroll.setVisible(False)
        
        self.main_layout.insertWidget(0, self.left_scroll)
        self.main_layout.addWidget(self.right_scroll)
        
        # Tracking last path to prevent resetting scroll on each set_path
        self.last_path = ""

        # Text field for typing or pasting a path, shown instead of the crumbs
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet("QLineEdit { border: none; background: transparent; padding: 0 4px; }")
        self.path_edit.setVisible(False)
        self.path_edit.returnPressed.connect(self._commit_edit)
        self.path_edit.editingFinished.connect(self.stop_editing)
        completion_model = QFileSystemModel(self)
        completion_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        completion_model.setRootPath("")
        completer = QCompleter(completion_model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.path_edit.setCompleter(completer)
        self.main_layout.addWidget(self.path_edit)
        self.setToolTip("Click an empty spot to type a path (Ctrl+L)")
        
        # Connect scrollbar signals to update scroll buttons
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self.update_scroll_buttons)
    
    def is_editing(self):
        return self.path_edit.isVisible()

    def start_editing(self):
        """Replace the crumbs with a text field holding the full path, selected."""
        if self.is_editing():
            return
        self.path_edit.setText(self.last_path)
        for widget in (self.scroll_area, self.left_scroll, self.right_scroll):
            widget.setVisible(False)
        self.path_edit.setVisible(True)
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def stop_editing(self):
        """Show the crumbs again without navigating."""
        if not self.is_editing():
            return
        self.path_edit.setVisible(False)
        self.scroll_area.setVisible(True)
        self.update_scroll_buttons()

    def _commit_edit(self):
        """Navigate to the typed path (~ and environment variables are expanded)."""
        text = self.path_edit.text().strip().strip('"')
        self.stop_editing()
        if not text:
            return
        if text.lower() in ("this pc", "pc"):
            self.path_changed.emit("pc")
            return
        path = os.path.expandvars(os.path.expanduser(text))
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self.path_changed.emit(path)

    def mousePressEvent(self, event):
        # Clicks on empty space (not on a crumb) switch to typing a path
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_editing()
        super().mousePressEvent(event)

    def scroll_left(self):
        """Scroll to the left."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() - 100)
    
    def scroll_right(self):
        """Scroll to the right."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        scrollbar.setValue(scrollbar.value() + 100)
    
    def update_scroll_buttons(self):
        """Update visibility of scroll buttons based on scrollbar position."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        self.left_scroll.setVisible(scrollbar.value() > 0)
        self.right_scroll.setVisible(scrollbar.value() < scrollbar.maximum())
    
    def resizeEvent(self, event):
        """Handle resize events to update scroll buttons.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        self.update_scroll_buttons()
        
    def set_path(self, path):
        """Set the path to display in the breadcrumb bar.
        
        Args:
            path: File path to display
        """
        # Check if this is the same path - no need to rebuild
        if path == self.last_path:
            return
            
        self.last_path = path
        
        # Block signals to prevent scroll position updates during rebuilding
        self.scroll_area.horizontalScrollBar().blockSignals(True)
        
        # Clear existing buttons and separators
        self._clear_breadcrumbs()
        
        # Create button for each path component
        parts = self._split_path(path)
        for i, (part_text, part_path) in enumerate(parts):
            if i > 0:
                separator = QLabel("›")
                separator.setObjectName("crumb_separator")
                self.layout.addWidget(separator)
                self.separators.append(separator)

            button = QPushButton(part_text)
            # The current folder is shown in bold (styled by the theme)
            button.setObjectName("crumb_current" if i == len(parts) - 1 else "crumb")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("path", part_path)
            button.clicked.connect(self._on_path_button_clicked)
            
            self.buttons.append(button)
            self.layout.addWidget(button)
        
        # Re-enable scrollbar signals
        self.scroll_area.horizontalScrollBar().blockSignals(False)
        
        # Force layout update
        self.container.adjustSize()
        
        # Scroll to the end to show the current path part
        QTimer.singleShot(0, self._scroll_to_end)
    
    def _clear_breadcrumbs(self):
        """Clear all breadcrumb buttons and separators."""
        # Clear existing buttons and separators
        for button in self.buttons:
            self.layout.removeWidget(button)
            button.deleteLater()
        self.buttons.clear()
        
        for separator in self.separators:
            self.layout.removeWidget(separator)
            separator.deleteLater()
        self.separators.clear()
        
        # Remove any stretch items
        for i in reversed(range(self.layout.count())):
            item = self.layout.itemAt(i)
            if item and item.widget() is None:  # It's a spacer
                self.layout.removeItem(item)
        
    def _scroll_to_end(self):
        """Scroll to the end of the breadcrumb bar to show the current folder."""
        scrollbar = self.scroll_area.horizontalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.update_scroll_buttons()
    
    def _split_path(self, path):
        """Split a path into clickable components.
        
        Args:
            path: Path to split
            
        Returns:
            list: Tuples of (display_name, full_path) for each component
        """
        parts = []
        
        # Handle special paths
        if path == "This PC":
            return [("This PC", "pc")]
            
        # Handle root directory specially
        if os.path.ismount(path):
            return [(path, path)]
        
        # Windows drive paths need special handling
        if platform.system() == "Windows" and len(path) <= 3 and path.endswith("\\"):
            return [(path, path)]
            
        # Split the path into components
        while True:
            path, folder = os.path.split(path)
            
            if folder:
                parts.append((folder, os.path.join(path, folder)))
            else:
                if path:
                    parts.append((path, path))
                break
                
        return list(reversed(parts))
    
    def _on_path_button_clicked(self):
        """Handle clicks on path buttons."""
        button = self.sender()
        path = button.property("path")
        self.path_changed.emit(path)
