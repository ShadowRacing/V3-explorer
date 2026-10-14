"""
Navigation panel module for Shadows File Explorer.

This module provides the NavigationPanel class which displays the sidebar with
pinned favorites, shortcuts to common locations, and drives.
"""
import os
import platform

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStyle, QMenu
from PyQt6.QtCore import pyqtSignal, Qt, QStorageInfo, QSettings

from file_views import local_paths_from_mime, should_move
from utils import normalize_path, paths_equal


def drive_item_id(path):
    """Navigation item id for a drive root path."""
    return f"drive_{os.path.normcase(normalize_path(path))}"


def favorite_item_id(path):
    """Navigation item id for a pinned folder."""
    return f"fav_{os.path.normcase(os.path.normpath(path))}"


class NavItem(QWidget):
    """One clickable sidebar entry (icon + label) that accepts dropped files.

    Signals:
        clicked: The item was clicked (item_id, path)
        files_dropped: Files were dropped on the item (paths, path, is_move)
        context_menu_requested: Right-click (item_id, path, global position)
    """

    clicked = pyqtSignal(str, str)
    files_dropped = pyqtSignal(list, str, bool)
    context_menu_requested = pyqtSignal(str, str, object)

    def __init__(self, item_id, label, path, icon, indent=0, parent=None):
        super().__init__(parent)
        self.item_id = item_id
        self.path = path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12 + indent, 4, 8, 4)
        layout.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(16, 16))
        layout.addWidget(icon_label)

        self.text_label = QLabel(label)
        self.text_label.setToolTip(path if os.path.isabs(path) else label)
        layout.addWidget(self.text_label, 1)

        # Needed for stylesheet backgrounds (the active highlight) on QWidget subclasses
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Folders (not "This PC") can receive dropped files
        self.setAcceptDrops(os.path.isabs(path))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_id, self.path)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self.context_menu_requested.emit(self.item_id, self.path, event.globalPos())

    def dragEnterEvent(self, event):
        if local_paths_from_mime(event.mimeData()) and os.path.isdir(self.path):
            event.acceptProposedAction()
            self._previous_style = self.styleSheet()
            self.setStyleSheet(f"background-color: {NavigationPanel.ACTIVE_COLOR}; border-radius: 4px;")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(getattr(self, "_previous_style", ""))

    def dropEvent(self, event):
        self.setStyleSheet(getattr(self, "_previous_style", ""))
        paths = local_paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return
        is_move = should_move(paths, self.path, event.modifiers())
        event.setDropAction(Qt.DropAction.MoveAction if is_move else Qt.DropAction.CopyAction)
        event.accept()
        self.files_dropped.emit(paths, self.path, is_move)


class NavigationPanel(QWidget):
    """Modern navigation panel with icons and labels.

    This panel provides:
    - Pinned favorite folders, saved between sessions
    - Shortcuts to common locations (Home, Desktop, Documents, etc.)
    - List of drives with expandable/collapsible functionality
    - Selection indicators for active location
    - Dropping files on an item copies or moves them there

    Signals:
        item_clicked: Emitted when a navigation item is clicked (id, path)
        files_dropped: Files were dropped on an item (paths, destination, is_move)
        open_in_new_tab: "Open in New Tab" was chosen for an item (path)
    """

    item_clicked = pyqtSignal(str, str)  # id, path
    files_dropped = pyqtSignal(list, str, bool)
    open_in_new_tab = pyqtSignal(str)

    # Semi-transparent so they work on both light and dark themes
    ACTIVE_COLOR = "rgba(0, 120, 215, 0.35)"
    PARENT_ACTIVE_COLOR = "rgba(128, 128, 128, 0.2)"
    HEADER_STYLE = "font-weight: bold; color: #888888; font-size: 12px; padding-left: 12px;"

    def __init__(self, parent=None):
        """Initialize the navigation panel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.settings = QSettings("ShadowsExplorer", "Preferences")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 20, 10, 20)
        self.layout.setSpacing(2)

        self.active_item = None
        self.items = {}
        self.drive_items = {}
        self.favorite_items = {}
        self.favorites = []
        self._drive_paths = None
        self.pc_expanded = True  # Start with drives visible

        # Favorites section, hidden while empty
        self.favorites_header = QLabel("FAVORITES")
        self.favorites_header.setStyleSheet(self.HEADER_STYLE)
        self.favorites_header.setToolTip("Right-click a folder and choose \"Pin to Favorites\"")
        self.layout.addWidget(self.favorites_header)
        self.favorites_container = QWidget()
        self.favorites_layout = QVBoxLayout(self.favorites_container)
        self.favorites_layout.setContentsMargins(0, 0, 0, 0)
        self.favorites_layout.setSpacing(2)
        self.layout.addWidget(self.favorites_container)
        self.favorites_spacing = QWidget()
        self.favorites_spacing.setFixedHeight(14)
        self.layout.addWidget(self.favorites_spacing)

        self.header = QLabel("LOCATIONS")
        self.header.setStyleSheet(self.HEADER_STYLE)
        self.layout.addWidget(self.header)
        self._add_standard_locations()

        self.layout.addSpacing(14)

        self.devices_header = QLabel("DEVICES")
        self.devices_header.setStyleSheet(self.HEADER_STYLE)
        self.layout.addWidget(self.devices_header)
        self._add_this_pc_section()

        # Container for drives beneath "This PC"
        self.drives_container = QWidget()
        self.drives_layout = QVBoxLayout(self.drives_container)
        self.drives_layout.setContentsMargins(0, 0, 0, 0)
        self.drives_layout.setSpacing(2)
        self.layout.addWidget(self.drives_container)

        self.layout.addStretch()

        self.refresh_drives()
        self._load_favorites()

    def _icon(self, pixmap):
        return self.style().standardIcon(pixmap)

    def _make_item(self, item_id, label, path, icon, indent=0):
        """Create a NavItem wired to this panel's signals."""
        item = NavItem(item_id, label, path, icon, indent)
        item.clicked.connect(self.on_item_clicked)
        item.files_dropped.connect(self.files_dropped.emit)
        item.context_menu_requested.connect(self._show_item_menu)
        return item

    def _add_standard_locations(self):
        """Add standard locations like Home, Desktop, etc."""
        home = os.path.expanduser("~")
        locations = [
            ("home", "Home", home, QStyle.StandardPixmap.SP_DirHomeIcon),
            ("desktop", "Desktop", os.path.join(home, "Desktop"), QStyle.StandardPixmap.SP_DesktopIcon),
            ("documents", "Documents", os.path.join(home, "Documents"), QStyle.StandardPixmap.SP_DirIcon),
            ("downloads", "Downloads", os.path.join(home, "Downloads"), QStyle.StandardPixmap.SP_DirIcon),
            ("pictures", "Pictures", os.path.join(home, "Pictures"), QStyle.StandardPixmap.SP_DirIcon),
            ("music", "Music", os.path.join(home, "Music"), QStyle.StandardPixmap.SP_DirIcon),
        ]
        for item_id, label, path, pixmap in locations:
            self.add_navigation_item(item_id, label, path, self._icon(pixmap))

    def standard_locations(self):
        """Map of standard location item ids to their paths."""
        return {item_id: item.path for item_id, item in self.items.items() if item_id != "pc"}

    def add_navigation_item(self, item_id, label, path, icon=None):
        """Add a navigation item to the panel.

        Args:
            item_id: Unique identifier for the item
            label: Display label for the item
            path: File path for the item
            icon: Optional QIcon; defaults to a folder icon
        """
        item = self._make_item(item_id, label, path, icon or self._icon(QStyle.StandardPixmap.SP_DirIcon))
        self.layout.addWidget(item)
        self.items[item_id] = item

    def _add_this_pc_section(self):
        """Add the 'This PC' item with an arrow that expands/collapses the drive list."""
        self.pc_button_widget = self._make_item("pc", "This PC", "pc",
                                                self._icon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.expand_icon = QLabel("▼")
        self.expand_icon.setToolTip("Show or hide drives")
        self.expand_icon.mousePressEvent = lambda event: self.toggle_drives()
        self.pc_button_widget.layout().addWidget(self.expand_icon)
        self.layout.addWidget(self.pc_button_widget)
        self.items["pc"] = self.pc_button_widget

    def toggle_drives(self):
        """Expand or collapse the drive list under This PC."""
        self.pc_expanded = not self.pc_expanded
        self.expand_icon.setText("▼" if self.pc_expanded else "►")
        self.drives_container.setVisible(self.pc_expanded)

    def add_drive_item(self, drive_info):
        """Add a drive item under 'This PC'.

        Args:
            drive_info: QStorageInfo object with drive information
        """
        path = normalize_path(drive_info.rootPath())
        drive_id = drive_item_id(path)
        item = self._make_item(drive_id, self._get_drive_display_name(path, drive_info), path,
                               self._icon(QStyle.StandardPixmap.SP_DriveHDIcon), indent=16)
        self.drives_layout.addWidget(item)
        self.drive_items[drive_id] = item

    def _get_drive_display_name(self, path, drive_info):
        """Get a user-friendly display name for a drive.

        Args:
            path: Drive path
            drive_info: QStorageInfo object for the drive

        Returns:
            str: User-friendly drive name
        """
        if platform.system() == "Windows" and len(path) <= 4:  # Windows drive letter (C:\, D:\, etc.)
            display_name = f"{path[0].upper()}:"
            if any(os.path.isdir(os.path.join(path, name)) for name in ("Windows", "winnt")):
                return display_name + " Windows (System)"
            if drive_info.name():
                return display_name + f" {drive_info.name().strip()}"
            return display_name + " Local Disk"
        return drive_info.name() or path

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

    # -------------------------- Favorites --------------------------

    def _load_favorites(self):
        saved = self.settings.value("favorites", [], type=list)
        self.favorites = [path for path in saved if isinstance(path, str)]
        self._rebuild_favorites()

    def _save_favorites(self):
        self.settings.setValue("favorites", self.favorites)

    def _rebuild_favorites(self):
        for widget in self.favorite_items.values():
            self.favorites_layout.removeWidget(widget)
            widget.deleteLater()
        self.favorite_items.clear()

        for path in self.favorites:
            item_id = favorite_item_id(path)
            label = os.path.basename(os.path.normpath(path)) or path
            item = self._make_item(item_id, label, path, self._icon(QStyle.StandardPixmap.SP_DirLinkIcon))
            if not os.path.isdir(path):
                item.text_label.setStyleSheet("color: #888888; text-decoration: line-through;")
                item.text_label.setToolTip(f"{path} (not available)")
            self.favorites_layout.addWidget(item)
            self.favorite_items[item_id] = item

        has_favorites = bool(self.favorites)
        self.favorites_header.setVisible(has_favorites)
        self.favorites_container.setVisible(has_favorites)
        self.favorites_spacing.setVisible(has_favorites)

        if self.active_item and self.active_item.startswith("fav_"):
            self._highlight(self.active_item if self.active_item in self.favorite_items else None)

    def is_favorite(self, path):
        return any(paths_equal(path, favorite) for favorite in self.favorites)

    def add_favorite(self, path):
        """Pin a folder to the Favorites section."""
        if not self.is_favorite(path):
            self.favorites.append(path)
            self._save_favorites()
            self._rebuild_favorites()

    def remove_favorite(self, path):
        """Unpin a folder from the Favorites section."""
        self.favorites = [favorite for favorite in self.favorites if not paths_equal(path, favorite)]
        self._save_favorites()
        self._rebuild_favorites()

    def move_favorite(self, path, offset):
        """Move a favorite up (-1) or down (+1)."""
        index = next((i for i, f in enumerate(self.favorites) if paths_equal(path, f)), None)
        if index is None or not 0 <= index + offset < len(self.favorites):
            return
        self.favorites.insert(index + offset, self.favorites.pop(index))
        self._save_favorites()
        self._rebuild_favorites()

    def _show_item_menu(self, item_id, path, global_pos):
        """Right-click menu for a sidebar item."""
        if item_id == "pc":
            return
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.on_item_clicked(item_id, path))
        menu.addAction("Open in New Tab", lambda: self.open_in_new_tab.emit(path))
        menu.addSeparator()
        if self.is_favorite(path):
            if item_id.startswith("fav_"):
                index = next(i for i, f in enumerate(self.favorites) if paths_equal(path, f))
                up = menu.addAction("Move Up", lambda: self.move_favorite(path, -1))
                up.setEnabled(index > 0)
                down = menu.addAction("Move Down", lambda: self.move_favorite(path, 1))
                down.setEnabled(index < len(self.favorites) - 1)
            menu.addAction("Unpin from Favorites", lambda: self.remove_favorite(path))
        else:
            menu.addAction("Pin to Favorites", lambda: self.add_favorite(path))
        menu.exec(global_pos)

    # -------------------------- Selection --------------------------

    def _widget_for(self, item_id):
        """Return the widget for a navigation item id, or None."""
        if not item_id:
            return None
        return self.drive_items.get(item_id) or self.favorite_items.get(item_id) or self.items.get(item_id)

    def _highlight(self, item_id):
        """Visually mark item_id as the active item without navigating."""
        previous = self._widget_for(self.active_item)
        if previous:
            previous.setStyleSheet("")
        self.pc_button_widget.setStyleSheet("")

        self.active_item = item_id
        widget = self._widget_for(item_id)
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

    def item_id_for_path(self, path):
        """The sidebar item id for a folder, preferring favorites, or None."""
        for favorite in self.favorites:
            if paths_equal(path, favorite):
                return favorite_item_id(favorite)
        for item_id, location in self.standard_locations().items():
            if paths_equal(path, location):
                return item_id
        for item_id, item in self.drive_items.items():
            if paths_equal(path, item.path):
                return item_id
        return None
