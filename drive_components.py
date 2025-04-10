"""
Drive components module for Shadows File Explorer.

This module provides the DriveInfo class for storing drive information,
the DriveItemWidget class for displaying individual drives, and the DrivesView
class for displaying a grid of drives.
"""
import os
import platform
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStyle,
                            QProgressBar, QApplication, QScrollArea, 
                            QGridLayout, QSizePolicy)
from PyQt6.QtCore import pyqtSignal, Qt, QStorageInfo


class DriveInfo:
    """Class to store and format drive information.
    
    Attributes:
        path: Drive path
        storage: QStorageInfo object
        custom_name: Optional custom name for the drive
    """
    
    def __init__(self, path, name=None):
        """Initialize drive information.
        
        Args:
            path: Drive path
            name: Optional custom name
        """
        self.path = path
        self.storage = QStorageInfo(path)
        self.storage.refresh()  # Make sure we have current data
        self.custom_name = name
        
    @property
    def name(self):
        """Get the display name for the drive.
        
        Returns:
            str: Display name
        """
        if self.custom_name:
            return self.custom_name
            
        # Try to get label if available
        if self.storage.name():
            return self.storage.name()
            
        # Fall back to path
        return self.storage.rootPath()
        
    @property
    def total_bytes(self):
        """Get total capacity in bytes.
        
        Returns:
            int: Total bytes
        """
        return self.storage.bytesTotal()
        
    @property
    def free_bytes(self):
        """Get free space in bytes.
        
        Returns:
            int: Free bytes
        """
        return self.storage.bytesFree()
        
    @property
    def used_bytes(self):
        """Get used space in bytes.
        
        Returns:
            int: Used bytes
        """
        return self.total_bytes - self.free_bytes
        
    @property
    def is_ready(self):
        """Check if the drive is ready.
        
        Returns:
            bool: True if drive is ready
        """
        return self.storage.isReady()
        
    @property
    def is_valid(self):
        """Check if the drive is valid.
        
        Returns:
            bool: True if drive is valid
        """
        return self.is_ready and self.total_bytes > 0
        
    def format_size(self, size_bytes):
        """Format byte size to human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
            
    @property
    def storage_info(self):
        """Get formatted storage information.
        
        Returns:
            str: Formatted storage string
        """
        free = self.format_size(self.free_bytes)
        total = self.format_size(self.total_bytes)
        return f"{free} free of {total}"
        
    @property
    def usage_percent(self):
        """Get the percentage of used space.
        
        Returns:
            float: Percentage used (0-100)
        """
        if self.total_bytes <= 0:
            return 0
        return (self.used_bytes / self.total_bytes) * 100


class DriveItemWidget(QWidget):
    """Widget to display drive item with progress bar.
    
    This widget provides:
    - Visual representation of a drive
    - Storage usage information
    - Progress bar for capacity visualization
    
    Signals:
        clicked: Emitted when the drive is clicked (path)
    """
    
    clicked = pyqtSignal(str)
    
    def __init__(self, drive_info, parent=None):
        """Initialize the drive item widget.
        
        Args:
            drive_info: DriveInfo object
            parent: Parent widget
        """
        super().__init__(parent)
        self.drive_info = drive_info
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface."""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(10)
        
        # Drive icon and name layout
        drive_header = QHBoxLayout()
        
        # Drive icon
        self.icon_label = QLabel()
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        self.icon_label.setPixmap(icon.pixmap(48, 48))
        drive_header.addWidget(self.icon_label)
        
        # Drive name and path
        name_layout = QVBoxLayout()
        
        # Improved name label with Windows detection
        if platform.system() == "Windows":
            drive_path = self.drive_info.path
            if not drive_path.endswith("\\"):
                drive_path += "\\"
            
            windows_path = os.path.join(drive_path, "Windows")
            if os.path.exists(windows_path) and os.path.isdir(windows_path):
                drive_name = f"{drive_path[0].upper()}: Windows"
            elif self.drive_info.name:
                drive_name = f"{drive_path[0].upper()}: {self.drive_info.name}"
            else:
                drive_name = f"{drive_path[0].upper()}: Local Disk"
                
            self.name_label = QLabel(drive_name)
        else:
            self.name_label = QLabel(self.drive_info.name)
        
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.path_label = QLabel(self.drive_info.path)
        self.path_label.setStyleSheet("font-size: 11px; opacity: 0.7;")
        
        name_layout.addWidget(self.name_label)
        name_layout.addWidget(self.path_label)
        drive_header.addLayout(name_layout)
        
        # Add spacer to push rest to right
        drive_header.addStretch()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(self.drive_info.usage_percent))
        self.progress_bar.setFormat(f"{int(self.drive_info.usage_percent)}% used")
        
        # Free space info
        self.info_label = QLabel(self.drive_info.storage_info)
        self.info_label.setStyleSheet("font-size: 12px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add all components to layout
        self.layout.addLayout(drive_header)
        self.layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.info_label)
        
        # Make the widget clickable
        self.setAutoFillBackground(True)
        
        # Set fixed size
        self.setMinimumWidth(250)
        self.setMinimumHeight(150)
        
    def mousePressEvent(self, event):
        """Handle mouse press events to make the widget clickable.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.drive_info.path)
        super().mousePressEvent(event)


class DrivesView(QScrollArea):
    """Widget to display drives in a grid layout that adapts to window width.
    
    This component provides:
    - Grid layout of drive items
    - Responsive layout that adjusts to window size
    - Dynamic drive loading and arrangement
    
    Signals:
        drive_clicked: Emitted when a drive is clicked (path)
    """
    
    drive_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the drives view.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setup_ui()
        self.drive_widgets = []
        
    def setup_ui(self):
        """Set up the user interface."""
        # Create a container widget for the scroll area
        self.container = QWidget()
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        
        # Use a grid layout for the drives
        self.layout = QGridLayout(self.container)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
    def add_drive(self, drive_info):
        """Add a drive to the view.
        
        Args:
            drive_info: DriveInfo object
        """
        if not drive_info.is_valid:
            return
            
        drive_widget = DriveItemWidget(drive_info)
        drive_widget.clicked.connect(self.drive_clicked.emit)
        self.drive_widgets.append(drive_widget)
        
        # We'll position the widgets in load_drives
        # Don't add to layout here
    
    def clear_drives(self):
        """Remove all drives from the view."""
        for widget in self.drive_widgets:
            self.layout.removeWidget(widget)
            widget.deleteLater()
        self.drive_widgets.clear()
                
    def load_drives(self):
        """Load all available drives and arrange them in a grid."""
        self.clear_drives()
        
        # Get all drives using QStorageInfo
        storage_drives = QStorageInfo.mountedVolumes()
        
        for drive in storage_drives:
            path = drive.rootPath()
            drive_info = DriveInfo(path)
            
            # Only add valid drives with size information
            if drive_info.is_valid:
                self.add_drive(drive_info)
        
        # Now layout the widgets in a grid based on the current width
        self.arrange_drives()
    
    def arrange_drives(self):
        """Arrange the drive widgets in a grid based on container width."""
        # First, remove all widgets from the layout
        for i in reversed(range(self.layout.count())):
            item = self.layout.itemAt(i)
            if item and item.widget():
                self.layout.removeWidget(item.widget())
        
        if not self.drive_widgets:
            return
            
        # Get the width of the container
        container_width = self.container.width() - self.layout.contentsMargins().left() - self.layout.contentsMargins().right()
        
        # Get the width of a drive widget plus spacing
        widget_width = self.drive_widgets[0].minimumWidth() + self.layout.spacing()
        
        # Calculate how many columns we can fit
        cols = max(1, container_width // widget_width)
        
        # Place widgets in the grid
        for i, widget in enumerate(self.drive_widgets):
            row = i // cols
            col = i % cols
            self.layout.addWidget(widget, row, col)
    
    def resizeEvent(self, event):
        """Handle resize events to rearrange the drives.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Rearrange drives when the container is resized
        self.arrange_drives()