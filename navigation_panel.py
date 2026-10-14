"""
Navigation panel module for Shadows File Explorer.

This module provides the NavigationPanel class which displays the sidebar with
shortcuts to common locations and drives.
"""
import os
import platform
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                            QLabel, QStyle)
from PyQt6.QtCore import pyqtSignal, QStorageInfo

from utils import normalize_path


def drive_item_id(path):
    """Navigation item id for a drive root path."""
    return f"drive_{os.path.normcase(normalize_path(path))}"


class NavigationPanel(QWidget):
    """Modern navigation panel with icons and labels.
    
    This panel provides:
    - Shortcuts to common locations (Home, Desktop, Documents, etc.)
    - List of drives with expandable/collapsible functionality
    - Selection indicators for active location
    
    Signals:
        item_clicked: Emitted when a navigation item is clicked (id, path)
    """
    
    item_clicked = pyqtSignal(str, str)  # id, path
    
    # Semi-transparent so they work on both light and dark themes
    ACTIVE_COLOR = "rgba(0, 120, 215, 0.35)"
    PARENT_ACTIVE_COLOR = "rgba(128, 128, 128, 0.2)"
    
    def __init__(self, parent=None):
        """Initialize the navigation panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 20, 10, 20)
        self.layout.setSpacing(6)
        
        self.active_item = None
        self.items = {}
        self.drive_items = {}
        self._drive_paths = None
        self.pc_expanded = True  # Start with drives visible
        
        # Add header
        self.header = QLabel("LOCATIONS")
        self.header.setStyleSheet("font-weight: bold; color: #888888; font-size: 12px; padding-left: 12px;")
        self.layout.addWidget(self.header)
        
        # Add standard locations
        self._add_standard_locations()
        
        self.layout.addSpacing(20)
        
        # Add devices section
        self.devices_header = QLabel("DEVICES")
        self.devices_header.setStyleSheet("font-weight: bold; color: #888888; font-size: 12px; padding-left: 12px;")
        self.layout.addWidget(self.devices_header)
        
        # Add "This PC" with expandable/collapsible functionality
        self._add_this_pc_section()
        
        # Container for drives
        self.drives_container = QWidget()
        self.drives_layout = QVBoxLayout(self.drives_container)
        self.drives_layout.setContentsMargins(0, 0, 0, 0)
        self.drives_layout.setSpacing(2)
        
        # Add drives beneath "This PC"
        self.layout.addWidget(self.drives_container)
        
        # Initially populate drives
        self.refresh_drives()
        
        # Add spacer at the bottom
        self.layout.addStretch()
        
        self.items["pc"] = self.pc_button_widget
        
    def _add_standard_locations(self):
        """Add standard locations like Home, Desktop, etc."""
        self.add_navigation_item("home", "Home", os.path.expanduser("~"))
        self.add_navigation_item("desktop", "Desktop", os.path.join(os.path.expanduser("~"), "Desktop"))
        self.add_navigation_item("documents", "Documents", os.path.join(os.path.expanduser("~"), "Documents"))
        self.add_navigation_item("downloads", "Downloads", os.path.join(os.path.expanduser("~"), "Downloads"))
        self.add_navigation_item("pictures", "Pictures", os.path.join(os.path.expanduser("~"), "Pictures"))
        self.add_navigation_item("music", "Music", os.path.join(os.path.expanduser("~"), "Music"))
    
    def _add_this_pc_section(self):
        """Add the 'This PC' section with expandable/collapsible functionality."""
        self.pc_button = QPushButton()
        self.pc_button.setProperty("item_id", "pc")
        self.pc_button.setProperty("path", "pc")
        self.pc_button.setStyleSheet("text-align: left; padding-left: 12px;")
        self.pc_button.setProperty("class", "nav-button")
        
        # Create a horizontal layout for the "This PC" button to add an icon
        pc_layout = QHBoxLayout()
        pc_layout.setContentsMargins(0, 0, 0, 0)
        pc_layout.setSpacing(8)
        
        # Add computer icon
        pc_icon = QLabel()
        pc_icon_pixmap = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon).pixmap(16, 16)
        pc_icon.setPixmap(pc_icon_pixmap)
        pc_layout.addWidget(pc_icon)
        
        # Add label and expand/collapse indicator
        pc_label = QLabel("This PC")
        pc_layout.addWidget(pc_label)
        pc_layout.addStretch()
        
        self.expand_icon = QLabel("▼")  # Down triangle for expanded
        pc_layout.addWidget(self.expand_icon)
        
        # Set the layout as the button's layout
        pc_widget = QWidget()
        pc_widget.setLayout(pc_layout)
        
        # Create a custom layout to add the button
        pc_container = QHBoxLayout()
        pc_container.setContentsMargins(0, 0, 0, 0)
        pc_container.addWidget(pc_widget)
        
        # Add the button to the main layout
        self.pc_button_widget = QWidget()
        self.pc_button_widget.setLayout(pc_container)
        self.pc_button_widget.mousePressEvent = self.pc_clicked
        self.layout.addWidget(self.pc_button_widget)
    
    def pc_clicked(self, event):
        """Handle clicks on the 'This PC' item.
        
        Args:
            event: Mouse event
        """
        # The arrow on the right toggles the drive list; anywhere else navigates
        if event.pos().x() > self.pc_button_widget.width() - 30:
            self.pc_expanded = not self.pc_expanded
            self.expand_icon.setText("▼" if self.pc_expanded else "►")
            self.drives_container.setVisible(self.pc_expanded)
        else:
            self.on_item_clicked("pc", "pc")
    
    def add_navigation_item(self, item_id, label, path):
        """Add a navigation item to the panel.
        
        Args:
            item_id: Unique identifier for the item
            label: Display label for the item
            path: File path for the item
        """
        button = QPushButton()
        button.setProperty("item_id", item_id)
        button.setProperty("path", path)
        button.setStyleSheet("text-align: left; padding-left: 12px;")
        button.setProperty("class", "nav-button")
        
        # Create a layout with an icon and label
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        
        # Add appropriate icon based on item_id
        icon_label = QLabel()
        
        if item_id == "home":
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)
        elif item_id == "desktop":
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        elif item_id in ["documents", "pictures", "music", "downloads"]:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        else:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        
        icon_label.setPixmap(icon.pixmap(16, 16))
        button_layout.addWidget(icon_label)
        
        # Add text label
        text_label = QLabel(label)
        button_layout.addWidget(text_label)
        button_layout.addStretch()
        
        # Set layout to a widget
        button_widget = QWidget()
        button_widget.setLayout(button_layout)
        
        # Create a container for the button
        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(button_widget)
        
        container_widget = QWidget()
        container_widget.setLayout(container)
        container_widget.mousePressEvent = lambda event, i=item_id, p=path: self.on_item_clicked(i, p)
        
        self.layout.addWidget(container_widget)
        self.items[item_id] = container_widget
    
    def add_drive_item(self, drive_info):
        """Add a drive item under 'This PC' with improved Windows drive detection.
        
        Args:
            drive_info: QStorageInfo object with drive information
        """
        path = normalize_path(drive_info.rootPath())
        drive_id = drive_item_id(path)
        
        # Create a widget for the drive
        drive_widget = QWidget()
        drive_layout = QHBoxLayout(drive_widget)
        drive_layout.setContentsMargins(0, 0, 0, 0)
        drive_layout.setSpacing(8)
        
        # Set the appropriate drive icon
        icon_label = QLabel()
        
        # Default icon (always set this to ensure icon is defined)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        
        icon_label.setPixmap(icon.pixmap(16, 16))
        drive_layout.addWidget(icon_label)
        
        # Create a readable label with drive letter and improved naming
        display_name = self._get_drive_display_name(path, drive_info)
            
        name_label = QLabel(display_name)
        drive_layout.addWidget(name_label)
        drive_layout.addStretch()
        
        # Create a container with indentation
        container = QHBoxLayout()
        container.setContentsMargins(24, 0, 0, 0)  # Extra left margin for indentation
        container.addWidget(drive_widget)
        
        container_widget = QWidget()
        container_widget.setLayout(container)
        container_widget.setProperty("item_id", drive_id)
        container_widget.setProperty("path", path)
        container_widget.setProperty("class", "nav-button")
        container_widget.mousePressEvent = lambda event, i=drive_id, p=path: self.on_item_clicked(i, p)
        
        self.drives_layout.addWidget(container_widget)
        self.drive_items[drive_id] = container_widget
    
    def _get_drive_display_name(self, path, drive_info):
        """Get a user-friendly display name for a drive.
        
        Args:
            path: Drive path
            drive_info: QStorageInfo object for the drive
            
        Returns:
            str: User-friendly drive name
        """
        if platform.system() == "Windows" and len(path) <= 4:  # Windows drive letter (C:\, D:\, etc.)
            drive_letter = path[0].upper()
            
            # Check if this is the Windows installation drive
            is_windows_drive = False
            
            # Check common Windows installation paths
            windows_paths = [
                os.path.join(path, "Windows"),
                os.path.join(path, "WINDOWS"),
                os.path.join(path, "winnt")
            ]
            
            for win_path in windows_paths:
                if os.path.exists(win_path) and os.path.isdir(win_path):
                    is_windows_drive = True
                    break
            
            # Start with the drive letter
            display_name = f"{drive_letter}:"
            
            # Add descriptive label
            if is_windows_drive:
                display_name += " Windows (System)"
            elif drive_info.name():
                # Use volume name if available
                volume_name = drive_info.name().strip()
                display_name += f" {volume_name}"
            else:
                # Generic name if no volume name exists
                display_name += " Local Disk"
        else:
            # For non-Windows or network paths
            display_name = drive_info.name() if drive_info.name() else path
            
        return display_name

    def refresh_drives(self):
        """Refresh the drives list, rebuilding it only when the set of drives changed."""
        drives = []
        for drive in QStorageInfo.mountedVolumes():
            if not drive.isReady():
                continue
            # Skip system mounts on macOS/Linux that appear as drives
            path = drive.rootPath()
            if platform.system() != "Windows" and (path == "/" or path.startswith(("/boot", "/sys", "/proc", "/dev", "/run", "/snap"))):
                continue
            drives.append(drive)
        
        paths = [d.rootPath() for d in drives]
        if paths == self._drive_paths:
            return
        self._drive_paths = paths
        
        for widget in self.drive_items.values():
            self.drives_layout.removeWidget(widget)
            widget.deleteLater()
        self.drive_items.clear()
        
        for drive in drives:
            self.add_drive_item(drive)
        
        # Keep the highlight on the active drive after rebuilding
        if self.active_item and self.active_item.startswith("drive_"):
            self._highlight(self.active_item)
    
    def _widget_for(self, item_id):
        """Return the widget for a navigation item id, or None."""
        return self.drive_items.get(item_id) or self.items.get(item_id)
    
    def _highlight(self, item_id):
        """Visually mark item_id as the active item without navigating."""
        previous = self._widget_for(self.active_item) if self.active_item else None
        if previous:
            previous.setStyleSheet("")
        self.pc_button_widget.setStyleSheet("")
        
        self.active_item = item_id
        widget = self._widget_for(item_id) if item_id else None
        if widget:
            widget.setStyleSheet(f"background-color: {self.ACTIVE_COLOR}; border-radius: 4px;")
        if item_id and item_id.startswith("drive_"):
            # Also highlight This PC, but less intensely
            self.pc_button_widget.setStyleSheet(f"background-color: {self.PARENT_ACTIVE_COLOR}; border-radius: 4px;")
    
    def on_item_clicked(self, item_id, path):
        """Handle navigation item click.
        
        Args:
            item_id: ID of the clicked item
            path: Path of the clicked item
        """
        self._highlight(item_id)
        self.item_clicked.emit(item_id, path)
    
    def set_active_item(self, item_id):
        """Highlight the item for the current location without emitting item_clicked.
        
        Args:
            item_id: ID of the item to activate, or None to clear the highlight
        """
        if item_id != self.active_item:
            self._highlight(item_id)
