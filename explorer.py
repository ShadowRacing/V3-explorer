"""
Explorer module for Shadows File Explorer.

This module provides the ModernExplorer class which is the main window
for the Shadows File Explorer application.
"""
import os
import shutil
import struct
import time
import zipfile

from PyQt6.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QAbstractItemView,
                            QPushButton, QMenu, QMessageBox, QToolButton,
                            QProgressBar, QListView, QTreeView, QComboBox,
                            QInputDialog, QDialog, QTextEdit, QFrame, QDateEdit, QRadioButton, QGroupBox,
                            QSpinBox, QCheckBox, QApplication, QStackedWidget, QProgressDialog,
                            QTabBar, QScrollArea, QFileDialog)
from PyQt6.QtCore import Qt, QSize, QDir, QTimer, QStorageInfo, QMimeData, QUrl, QSettings
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut

from theme_manager import ThemeManager
from file_operation_safety_manager import FileOperationSafetyManager
from navigation_panel import NavigationPanel
from file_views import FileListView, FileTreeView
from icons import FileIconProvider, file_type_icon, ui_icon
from archive_ops import (ArchiveCancelled, archive_stem, archive_top_level_names, create_zip,
                         extract_archive, extract_destination, is_archive, suggest_zip_path)
from background import BackgroundJob
from bulk_rename import execute_renames
from bulk_rename_dialog import BulkRenameDialog
from dual_pane import FolderPane
from thumbnails import ThumbnailFileSystemModel
from breadcrumb_bar import FixedBreadcrumbBar
from drive_components import DrivesView
from preview_pane import PreviewPane
from file_searcher import FileSearcher
from search_results_model import SearchResultsModel, PATH_ROLE
from settings_dialog import SettingsDialog
from properties_dialog import PropertiesDialog
from utils import (IS_WINDOWS, NavigationHistory, format_size, normalize_path, paths_equal,
                   is_within, unique_target_path, is_valid_filename)

# Clipboard format marking a "cut" (move) rather than a copy
CUT_MIME = "application/x-shadows-explorer-cut"
# Windows Explorer's own cut/copy marker, so cut/paste works with Explorer too
WIN_DROP_EFFECT_MIME = 'application/x-qt-windows-mime;value="Preferred DropEffect"'
DROPEFFECT_COPY = 5  # DROPEFFECT_COPY | DROPEFFECT_LINK, as Explorer writes it
DROPEFFECT_MOVE = 2

PROGRESS_DIALOG_THRESHOLD = 5  # show a progress dialog above this many items
MAX_UNDO_HISTORY = 20

VIEW_ICONS, VIEW_LIST, VIEW_DETAILS = range(3)

# Context menu entries that get an icon (see _decorate_menu)
MENU_ICONS = {
    "Open in New Tab": "tab", "Open in New Window": "window", "Open File Location": "folder",
    "Cut": "cut", "Copy": "copy", "Copy as Path": "copy", "Paste": "paste",
    "Delete": "delete", "Rename": "rename", "Properties": "properties", "Refresh": "refresh",
    "New": "new", "Folder": "folder", "Text Document": "documents", "View": "view_icons",
    "Pin to Favorites": "star", "Unpin from Favorites": "star",
    "Pin This Folder to Favorites": "star", "Unpin This Folder": "star",
    "Icons": "view_icons", "List": "view_list", "Details": "view_details", "Hidden files": "hidden",
    "Compress to ZIP": "archive", "Extract": "extract", "Extract to...": "extract",
    "Copy to Other Pane": "copy_to", "Move to Other Pane": "copy_to", "New Folder": "folder",
}


class BrowserTab:
    """State of one tab: its own back/forward history.

    The tab's current location is history.current (a folder path, or "pc").
    """

    def __init__(self, location):
        self.history = NavigationHistory()
        self.history.visit(location)


class ModernExplorer(QMainWindow):
    """Main window for Shadows File Explorer.

    This class provides:
    - Main application window and UI
    - Navigation and file browsing
    - File operations
    - Search functionality
    - Theme management
    """

    def __init__(self, start_path=None):
        """Initialize the main window.

        Args:
            start_path: Folder to open; defaults to the user's home folder
        """
        super().__init__()
        self.setWindowTitle("Shadows File Explorer")
        self.setMinimumSize(1000, 600)

        self.settings = QSettings("ShadowsExplorer", "Preferences")

        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self.apply_theme)

        self.settings_dialog = None
        self.child_windows = []

        # Navigation state (history lives in each tab)
        self._shown_tab = None
        self.restore_tabs = start_path is None
        if not (start_path and os.path.isdir(start_path)):
            start_path = self._get_default_start_path()
        self.current_path = normalize_path(os.path.abspath(start_path))
        self.current_view = "files"  # Options: "files", "drives", "search"
        self._folder_status = ""
        self.show_hidden = False

        # Models
        self.file_model = self._create_file_model()
        self.search_results_model = SearchResultsModel(self)

        # Search state
        self.file_searcher = FileSearcher(self)
        self.is_searching = False
        self.search_options = None
        self.search_start_time = 0
        self.search_scanned = 0
        self.search_scope_all_drives = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_search_status)

        # Safety checks and undo
        self.safety_manager = FileOperationSafetyManager(self)
        self.operation_history = []
        self._jobs = set()  # Background jobs still running

        self.setup_ui()
        self._connect_search_signals()
        self._setup_shortcuts()
        self._restore_settings()

        self.apply_theme(self.theme_manager.current_theme)

        self._open_initial_tabs()

        # Refresh drives periodically to pick up USB sticks etc.
        self.drives_refresh_timer = QTimer(self)
        self.drives_refresh_timer.timeout.connect(self.refresh_drives)
        self.drives_refresh_timer.start(10000)

    # -------------------------- Setup --------------------------

    def _get_default_start_path(self):
        """Get the default starting path based on platform."""
        home = os.path.expanduser("~")
        if os.path.isdir(home):
            return home
        return "C:\\" if IS_WINDOWS else "/"

    def _create_file_model(self):
        """Create and configure the file model.

        Returns:
            QFileSystemModel: Configured file model
        """
        model = ThumbnailFileSystemModel(self)
        # Keep a reference: the model does not take ownership of the provider
        self.icon_provider = FileIconProvider()
        model.setIconProvider(self.icon_provider)
        model.setRootPath("")
        return model

    def _set_show_hidden(self, show):
        """Show or hide hidden and system files."""
        filters = QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs
        if show:
            filters |= QDir.Filter.Hidden | QDir.Filter.System
        self.file_model.setFilter(filters)
        self.folder_pane.set_show_hidden(show)
        self.show_hidden = show
        self.settings.setValue("show_hidden", show)
        self.update_status()

    def apply_theme(self, theme_name):
        """Apply the selected theme to the application.

        Args:
            theme_name: Name of the theme to apply
        """
        self.setStyleSheet(self.theme_manager.get_theme_stylesheet(theme_name))
        palette = self.theme_manager.palette(theme_name)
        self.icon_color = palette["icon"]
        for widget, name in self.themed_icons:
            widget.setIcon(ui_icon(name, self.icon_color))
        self.navigation_panel.set_icon_color(self.icon_color)
        self.preview_pane.set_icon_color(self.icon_color)
        self.folder_pane.set_icon_color(self.icon_color)
        self.preview_pane.set_dark(palette["dark"])
        DrivesView.icon_color = self.icon_color
        if self.current_view == "drives":
            self.drives_view.load_drives()

    def _themed(self, widget, icon_name):
        """Give a button or action an icon that follows the theme's icon color."""
        widget.setIcon(ui_icon(icon_name, self.icon_color))
        self.themed_icons.append((widget, icon_name))
        return widget

    def _decorate_menu(self, menu):
        """Add icons to a context menu's actions, matched by their text."""
        for action in menu.actions():
            # "Rename 3 Items..." matches on its first word
            name = MENU_ICONS.get(action.text()) or MENU_ICONS.get(action.text().split(" ")[0])
            if name:
                action.setIcon(ui_icon(name, self.icon_color))
            if action.menu():
                self._decorate_menu(action.menu())

    def setup_ui(self):
        """Set up the user interface."""
        self.themed_icons = []
        self.icon_color = self.theme_manager.palette()["icon"]
        self.setWindowIcon(file_type_icon("folder"))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self._setup_app_bar()
        self._setup_tab_bar()
        self._setup_content_area()
        self._setup_action_bar()

    def _make_tool_button(self, icon_name, tooltip, slot, checkable=False):
        """Create an icon-only toolbar button."""
        button = QToolButton()
        self._themed(button, icon_name)
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tooltip)
        button.setCheckable(checkable)
        button.clicked.connect(slot)
        button.setFixedSize(32, 32)
        return button

    def _setup_app_bar(self):
        """Set up the application bar at the top."""
        self.app_bar = QWidget()
        self.app_bar.setObjectName("appbar")
        self.app_bar.setFixedHeight(52)
        self.app_bar_layout = QHBoxLayout(self.app_bar)
        self.app_bar_layout.setContentsMargins(12, 8, 12, 8)
        self.app_bar_layout.setSpacing(4)

        # App icon and title
        app_icon = QLabel()
        app_icon.setPixmap(file_type_icon("folder").pixmap(24, 24))
        app_icon.setStyleSheet("background: transparent;")
        self.app_bar_layout.addWidget(app_icon)
        app_title = QLabel("Shadows Explorer")
        app_title.setObjectName("app_title")
        self.app_bar_layout.addWidget(app_title)
        self.app_bar_layout.addSpacing(12)

        # Navigation buttons
        self.back_button = self._make_tool_button("back", "Back (Alt+Left)", self.navigate_back)
        self.forward_button = self._make_tool_button("forward", "Forward (Alt+Right)", self.navigate_forward)
        self.up_button = self._make_tool_button("up", "Up (Alt+Up)", self.navigate_up)
        self.refresh_button = self._make_tool_button("refresh", "Refresh (F5)", self.refresh_view)
        self.undo_button = self._make_tool_button("undo", "Undo (Ctrl+Z)", self.undo_last_operation)
        self.undo_button.setEnabled(False)
        for button in (self.back_button, self.forward_button, self.up_button,
                       self.refresh_button, self.undo_button):
            self.app_bar_layout.addWidget(button)
        self.app_bar_layout.addSpacing(8)

        # Breadcrumb navigation
        self.breadcrumb_bar = FixedBreadcrumbBar()
        self.breadcrumb_bar.path_changed.connect(self.navigate_to)
        self.app_bar_layout.addWidget(self.breadcrumb_bar, 1)
        self.app_bar_layout.addSpacing(8)

        # Search box with a search icon inside it
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search  (Ctrl+F)")
        self.search_box.setToolTip("Search in current location, or use 'AllDrives:' prefix to search all drives")
        self.search_box.setFixedWidth(240)
        self.search_box.returnPressed.connect(self.search_files)
        search_action = self.search_box.addAction(ui_icon("search", self.icon_color),
                                                  QLineEdit.ActionPosition.LeadingPosition)
        self.themed_icons.append((search_action, "search"))
        search_action.setToolTip("Search")
        search_action.triggered.connect(self.search_files)
        self.app_bar_layout.addWidget(self.search_box)

        self.clear_search_button = self._make_tool_button("close", "Clear Search (Esc)", self.clear_search)
        self.clear_search_button.setVisible(False)
        self.app_bar_layout.addWidget(self.clear_search_button)

        self.advanced_search_button = self._make_tool_button("filter", "Advanced Search", self.show_advanced_search)
        self.app_bar_layout.addWidget(self.advanced_search_button)
        self.app_bar_layout.addSpacing(4)

        self.dual_pane_button = self._make_tool_button("dual", "Two Panes (Ctrl+Shift+D)",
                                                       lambda: self.set_dual_pane_visible(
                                                           not self.folder_pane.isVisible()), checkable=True)
        self.app_bar_layout.addWidget(self.dual_pane_button)
        self.toggle_preview_button = self._make_tool_button("preview", "Show Preview Panel",
                                                            self.toggle_preview_panel, checkable=True)
        self.app_bar_layout.addWidget(self.toggle_preview_button)
        self.theme_button = self._make_tool_button("settings", "Settings", self.show_settings)
        self.app_bar_layout.addWidget(self.theme_button)

        self.main_layout.addWidget(self.app_bar)

    def _setup_tab_bar(self):
        """Set up the row of tabs below the app bar."""
        tab_row = QWidget()
        tab_row.setObjectName("tab_row")
        tab_row.setFixedHeight(38)
        tab_layout = QHBoxLayout(tab_row)
        tab_layout.setContentsMargins(8, 4, 8, 0)
        tab_layout.setSpacing(4)

        self.tab_bar = QTabBar()
        self.tab_bar.setMovable(True)
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideMiddle)
        self.tab_bar.setUsesScrollButtons(True)
        self.tab_bar.setIconSize(QSize(16, 16))
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        tab_layout.addWidget(self.tab_bar, 0, Qt.AlignmentFlag.AlignBottom)

        new_tab_button = self._make_tool_button("plus", "New Tab (Ctrl+T)", lambda: self.new_tab())
        new_tab_button.setFixedSize(28, 28)
        tab_layout.addWidget(new_tab_button, 0, Qt.AlignmentFlag.AlignVCenter)
        tab_layout.addStretch()

        self.main_layout.addWidget(tab_row)

    def _add_tab_close_button(self, index):
        """Put a themed close button on a tab."""
        button = QToolButton()
        self._themed(button, "close")
        button.setIconSize(QSize(12, 12))
        button.setFixedSize(18, 18)
        button.setToolTip("Close Tab (Ctrl+W)")
        button.setStyleSheet("QToolButton { padding: 0px; border-radius: 9px; }")
        button.clicked.connect(lambda: self.close_tab(self._tab_index_of_button(button)))
        self.tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)
        button.destroyed.connect(lambda: self.themed_icons.remove((button, "close"))
                                 if (button, "close") in self.themed_icons else None)

    def _tab_index_of_button(self, button):
        for index in range(self.tab_bar.count()):
            if self.tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide) is button:
                return index
        return -1

    def _setup_file_view(self, view):
        """Apply settings shared by the icon/list view and the details view."""
        view.setModel(self.file_model)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.activated.connect(self.file_view_activated)
        view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        view.customContextMenuRequested.connect(self.show_context_menu)
        view.selectionModel().selectionChanged.connect(self.on_file_selection_changed)
        view.files_dropped.connect(self.transfer_files)
        view.open_in_new_tab.connect(self.new_tab)

    def _setup_content_area(self):
        """Set up the main content area."""
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar with navigation panel
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        self.navigation_panel = NavigationPanel()
        self.navigation_panel.item_clicked.connect(self.handle_navigation_item)
        self.navigation_panel.files_dropped.connect(self.transfer_files)
        self.navigation_panel.open_in_new_tab.connect(self.new_tab)

        # Scrollable, so long favorites and drive lists still fit
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setWidget(self.navigation_panel)
        sidebar_layout.addWidget(sidebar_scroll)

        content_layout.addWidget(self.sidebar)

        # Main splitter for content and preview
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(1)

        self.content_frame = QFrame()
        self.content_frame.setObjectName("content")
        content_frame_layout = QVBoxLayout(self.content_frame)
        content_frame_layout.setContentsMargins(0, 0, 0, 0)
        content_frame_layout.setSpacing(0)

        # View controls
        view_controls = QWidget()
        view_controls.setObjectName("view_controls")
        view_layout = QHBoxLayout(view_controls)
        view_layout.setContentsMargins(12, 8, 12, 6)
        view_layout.setSpacing(2)

        # The combo box holds the view mode; the icon buttons are its visible face
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Icons", "List", "Details"])
        self.view_mode_combo.setVisible(False)
        self.view_mode_buttons = []
        for mode, icon_name, tooltip in ((VIEW_ICONS, "view_icons", "Icons"),
                                         (VIEW_LIST, "view_list", "List"),
                                         (VIEW_DETAILS, "view_details", "Details")):
            button = self._make_tool_button(icon_name, tooltip,
                                            lambda checked=False, m=mode: self.view_mode_combo.setCurrentIndex(m),
                                            checkable=True)
            button.setAutoExclusive(True)
            self.view_mode_buttons.append(button)
            view_layout.addWidget(button)
        self.view_mode_buttons[VIEW_ICONS].setChecked(True)
        self.view_mode_combo.currentIndexChanged.connect(self.change_view_mode)
        self.view_mode_combo.currentIndexChanged.connect(
            lambda index: self.view_mode_buttons[index].setChecked(True))
        view_layout.addWidget(self.view_mode_combo)
        view_layout.addSpacing(8)

        self.hidden_files_checkbox = QToolButton()
        self._themed(self.hidden_files_checkbox, "hidden")
        self.hidden_files_checkbox.setText("Hidden files")
        self.hidden_files_checkbox.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.hidden_files_checkbox.setCheckable(True)
        self.hidden_files_checkbox.setToolTip("Show hidden files (Ctrl+H)")
        self.hidden_files_checkbox.toggled.connect(self._set_show_hidden)
        view_layout.addWidget(self.hidden_files_checkbox)

        view_layout.addStretch()

        # Search status
        self.search_status_widget = QWidget()
        self.search_status_widget.setVisible(False)
        search_status_layout = QHBoxLayout(self.search_status_widget)
        search_status_layout.setContentsMargins(0, 0, 0, 0)

        self.search_progress = QProgressBar()
        self.search_progress.setTextVisible(False)
        self.search_progress.setFixedWidth(120)

        self.search_status_label = QLabel("")
        self.search_status_label.setObjectName("status_label")

        self.stop_search_button = QPushButton("Stop")
        self.stop_search_button.clicked.connect(self.stop_search)

        search_status_layout.addWidget(self.search_progress)
        search_status_layout.addWidget(self.search_status_label, 1)
        search_status_layout.addWidget(self.stop_search_button)

        view_layout.addWidget(self.search_status_widget)

        content_frame_layout.addWidget(view_controls)

        self.views_stack = QStackedWidget()

        # Icon / list view
        self.file_view = FileListView()
        self._setup_file_view(self.file_view)
        self.file_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.file_view.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self._apply_list_mode(VIEW_ICONS)

        # Detail view
        self.detail_view = FileTreeView()
        self._setup_file_view(self.detail_view)
        self.detail_view.setSortingEnabled(True)
        self.detail_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.detail_view.setRootIsDecorated(False)
        self.detail_view.setItemsExpandable(False)
        self.detail_view.setUniformRowHeights(True)
        self.detail_view.setIconSize(QSize(18, 18))
        self.detail_view.setColumnWidth(0, 320)

        # Search results view
        self.search_view = QTreeView()
        self.search_view.setModel(self.search_results_model)
        self.search_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.search_view.activated.connect(self.search_result_activated)
        self.search_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_view.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_view.setRootIsDecorated(False)
        self.search_view.setSortingEnabled(True)
        self.search_view.setUniformRowHeights(True)
        self.search_view.setIconSize(QSize(18, 18))
        self.search_view.setColumnWidth(0, 250)
        self.search_view.setColumnWidth(1, 350)
        self.search_view.selectionModel().selectionChanged.connect(self.on_search_selection_changed)

        # Drives view
        self.drives_view = DrivesView()
        self.drives_view.drive_clicked.connect(self.navigate_to)

        self.views_stack.addWidget(self.file_view)
        self.views_stack.addWidget(self.detail_view)
        self.views_stack.addWidget(self.search_view)
        self.views_stack.addWidget(self.drives_view)
        content_frame_layout.addWidget(self.views_stack)

        self.main_splitter.addWidget(self.content_frame)

        # Second folder pane, hidden until toggled on
        self._pane_active = False
        self.folder_pane = FolderPane()
        self.folder_pane.setVisible(False)
        self.folder_pane.open_file.connect(self.open_path)
        self.folder_pane.files_dropped.connect(self.transfer_files)
        self.folder_pane.context_menu_requested.connect(self.show_pane_context_menu)
        self.folder_pane.selection_changed.connect(self._preview_selection)
        self.folder_pane.close_requested.connect(lambda: self.set_dual_pane_visible(False))
        self.main_splitter.addWidget(self.folder_pane)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

        # Preview pane, hidden until toggled on
        self.preview_pane = PreviewPane()
        self.preview_pane.setObjectName("preview_pane")
        self.preview_pane.setMinimumWidth(300)
        self.preview_pane.close_requested.connect(lambda: self.set_preview_visible(False))
        self.main_splitter.addWidget(self.preview_pane)
        self.main_splitter.setStretchFactor(0, 1)
        self.preview_pane.setVisible(False)

        content_layout.addWidget(self.main_splitter)

        # Stretch 1: the content area, not the bars, takes any extra height
        self.main_layout.addWidget(content_container, 1)

    def _setup_action_bar(self):
        """Set up the bottom action bar."""
        self.action_bar = QWidget()
        self.action_bar.setObjectName("action_bar")
        self.action_bar.setFixedHeight(48)
        action_bar_layout = QHBoxLayout(self.action_bar)
        action_bar_layout.setContentsMargins(12, 8, 12, 8)
        action_bar_layout.setSpacing(6)

        # New button with menu
        self.new_button = QPushButton("New")
        self._themed(self.new_button, "new")
        new_menu = QMenu(self)

        self._themed(new_menu.addAction("Folder", self.create_new_folder), "folder")
        self._themed(new_menu.addAction("Text Document", lambda: self.create_new_file(".txt")), "documents")
        new_menu.addSeparator()
        new_menu.addAction("Word Document", lambda: self.create_new_file(".docx"))
        new_menu.addAction("Excel Spreadsheet", lambda: self.create_new_file(".xlsx"))
        new_menu.addSeparator()
        new_menu.addAction("Python Script", lambda: self.create_new_file(".py"))
        new_menu.addAction("Markdown Document", lambda: self.create_new_file(".md"))
        new_menu.addAction("Zip Archive", lambda: self.create_new_file(".zip"))

        self.new_button.setMenu(new_menu)
        action_bar_layout.addWidget(self.new_button)
        action_bar_layout.addSpacing(6)

        # File operation buttons
        for text, icon_name, slot in (("Copy", "copy", self.copy_selected_files),
                                      ("Cut", "cut", self.cut_selected_files),
                                      ("Paste", "paste", self.paste_files),
                                      ("Delete", "delete", self.delete_selected_files)):
            button = QPushButton(text)
            self._themed(button, icon_name)
            button.clicked.connect(lambda checked=False, s=slot: s())
            action_bar_layout.addWidget(button)

        action_bar_layout.addStretch()

        self.status_label = QLabel()
        self.status_label.setObjectName("status_label")
        action_bar_layout.addWidget(self.status_label)

        self.main_layout.addWidget(self.action_bar)

    def _connect_search_signals(self):
        """Connect the searcher's signals once."""
        self.file_searcher.finished.connect(self.search_completed)
        self.file_searcher.progress.connect(self.update_search_progress)
        self.file_searcher.found_item.connect(self.add_search_result)
        self.file_searcher.status_update.connect(self.update_search_message)

    def _setup_shortcuts(self):
        """Register keyboard shortcuts."""
        shortcuts = [
            (QKeySequence.StandardKey.Copy, self.copy_selected_files),
            (QKeySequence.StandardKey.Cut, self.cut_selected_files),
            (QKeySequence.StandardKey.Paste, self.paste_files),
            (QKeySequence.StandardKey.Delete, self.delete_selected_files),
            ("Shift+Delete", lambda: self.delete_selected_files(permanent=True)),
            (QKeySequence.StandardKey.Undo, self.undo_last_operation),
            ("F5", self.refresh_view),
            ("F2", self.rename_selected_file),
            ("Alt+Return", self.show_selected_properties),
            ("Alt+Left", self.navigate_back),
            ("Alt+Right", self.navigate_forward),
            ("Alt+Up", self.navigate_up),
            ("Backspace", self.navigate_back),
            (QKeySequence.StandardKey.Find, self._focus_search),
            ("Ctrl+Shift+N", self.create_new_folder),
            ("Ctrl+H", lambda: self.hidden_files_checkbox.toggle()),
            ("Escape", self.clear_search),
            ("Ctrl+T", lambda: self.new_tab()),
            ("Ctrl+W", lambda: self.close_tab(self.tab_bar.currentIndex())),
            ("Ctrl+Tab", lambda: self._cycle_tab(1)),
            ("Ctrl+Shift+Tab", lambda: self._cycle_tab(-1)),
            ("Ctrl+D", self.toggle_favorite_current),
            ("Ctrl+Shift+D", lambda: self.set_dual_pane_visible(not self.folder_pane.isVisible())),
        ]
        for key, slot in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(slot)

    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _restore_settings(self):
        """Restore window geometry and view preferences."""
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1200, 750)

        view_mode = int(self.settings.value("view_mode", VIEW_ICONS))
        if view_mode in (VIEW_ICONS, VIEW_LIST, VIEW_DETAILS):
            self.view_mode_combo.setCurrentIndex(view_mode)
        # Not covered by currentIndexChanged when the saved mode is the default
        self.file_model.set_thumbnails_enabled(self.view_mode_combo.currentIndex() == VIEW_ICONS)

        show_hidden = self.settings.value("show_hidden", False, type=bool)
        self.hidden_files_checkbox.setChecked(show_hidden)
        self._set_show_hidden(show_hidden)

        if self.settings.value("preview_visible", False, type=bool):
            self.set_preview_visible(True)
        if self.settings.value("dual_pane_visible", False, type=bool):
            self.set_dual_pane_visible(True, self.settings.value("dual_pane_path", None))

    def closeEvent(self, event):
        """Stop background work and save preferences on close."""
        self.file_searcher.stop()
        self.file_model.shutdown()
        for job in list(self._jobs):
            job.cancel.set()
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("view_mode", self.view_mode_combo.currentIndex())
        self.settings.setValue("preview_visible", self.preview_pane.isVisible())
        self.settings.setValue("dual_pane_visible", self.folder_pane.isVisible())
        self.settings.setValue("dual_pane_path", self.folder_pane.current_path)
        self.settings.setValue("tabs", [self._tab(i).history.current for i in range(self.tab_bar.count())])
        self.settings.setValue("current_tab", self.tab_bar.currentIndex())
        super().closeEvent(event)

    # -------------------------- Selection helpers --------------------------

    def _active_file_view(self):
        """The icon/list view or the details view, whichever is showing."""
        return self.detail_view if self.views_stack.currentWidget() is self.detail_view else self.file_view

    @staticmethod
    def _selected_first_column(view):
        """One index per selected row, in column 0.

        selectedRows() only reports rows with every column selected, which a
        QListView (one visible column) never does, so filter the indexes instead.
        """
        seen, indexes = set(), []
        for index in view.selectionModel().selectedIndexes():
            if index.row() not in seen:
                seen.add(index.row())
                indexes.append(index.siblingAtColumn(0))
        return indexes

    def get_selected_file_paths(self):
        """Paths selected in the folder view (one per row)."""
        return [self.file_model.filePath(index) for index in self._selected_first_column(self._active_file_view())]

    def get_selected_search_paths(self):
        """Paths selected in the search results (one per row)."""
        paths = [index.data(PATH_ROLE) for index in self._selected_first_column(self.search_view)]
        return [p for p in paths if p and os.path.exists(p)]

    def selected_paths(self):
        """Paths selected in the active pane (see _pane_active)."""
        if self.pane_is_active():
            return self.folder_pane.selected_paths()
        if self.current_view == "search":
            return self.get_selected_search_paths()
        if self.current_view == "files":
            return self.get_selected_file_paths()
        return []

    # -------------------------- Opening files --------------------------

    def open_path(self, path):
        """Open a folder in the explorer or a file in its default application.

        Args:
            path: File or folder to open
        """
        if os.path.isdir(path):
            self.navigate_to(path)
            return

        is_safe, warning = self.safety_manager.check_file_open_safety(path)
        if not is_safe:
            confirm = QMessageBox.question(
                self,
                "Security Warning",
                f"{warning}\n\nFile: {os.path.basename(path)}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        # QDesktopServices passes the path as an argument, never through a shell
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(self, "Error", f"Could not open file:\n{path}")

    def open_in_new_window(self, path):
        """Open a folder in a new explorer window."""
        window = ModernExplorer(start_path=path)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.destroyed.connect(lambda: self.child_windows.remove(window) if window in self.child_windows else None)
        self.child_windows.append(window)
        window.show()

    def file_view_activated(self, index):
        """Handle double-click or Enter on a file or folder.

        Args:
            index: Model index of the activated item
        """
        self.open_path(self.file_model.filePath(index))

    def search_result_activated(self, index):
        """Handle double-click or Enter on a search result.

        Args:
            index: Model index of the activated item
        """
        file_path = index.siblingAtColumn(0).data(PATH_ROLE)
        if file_path and os.path.exists(file_path):
            self.open_path(file_path)

    # -------------------------- Context menus --------------------------

    def show_search_context_menu(self, position):
        """Context menu for search results."""
        paths = self.get_selected_search_paths()
        if not paths:
            return

        menu = QMenu(self)
        open_action = menu.addAction("Open")
        open_location_action = menu.addAction("Open File Location")
        new_tab_action = menu.addAction("Open in New Tab")
        new_tab_action.setEnabled(os.path.isdir(paths[0]))
        menu.addSeparator()
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        properties_action = menu.addAction("Properties")
        properties_action.setEnabled(len(paths) == 1)

        self._decorate_menu(menu)
        action = menu.exec(self.search_view.viewport().mapToGlobal(position))

        if action == open_action:
            self.open_path(paths[0])
        elif action == open_location_action:
            self.navigate_to(os.path.dirname(paths[0]))
        elif action == new_tab_action:
            self.new_tab(paths[0])
        elif action == copy_action:
            self.copy_selected_files(paths)
        elif action == cut_action:
            self.cut_selected_files(paths)
        elif action == delete_action:
            self.delete_selected_files(paths)
        elif action == properties_action:
            self.show_properties(paths[0])

    def show_context_menu(self, position):
        """Context menu for the folder views."""
        view = self.sender()
        index = view.indexAt(position)
        if not index.isValid():
            view.clearSelection()
        paths = self.get_selected_file_paths()

        menu = QMenu(self)

        if not paths:
            # Background context menu
            view_submenu = menu.addMenu("View")
            for mode, label in ((VIEW_ICONS, "Icons"), (VIEW_LIST, "List"), (VIEW_DETAILS, "Details")):
                action = view_submenu.addAction(label, lambda m=mode: self.view_mode_combo.setCurrentIndex(m))
                action.setCheckable(True)
                action.setChecked(self.view_mode_combo.currentIndex() == mode)
            hidden_action = view_submenu.addAction("Hidden files", self.hidden_files_checkbox.toggle)
            hidden_action.setCheckable(True)
            hidden_action.setChecked(self.show_hidden)

            menu.addSeparator()
            menu.addAction("Refresh", self.refresh_view)
            menu.addSeparator()
            new_menu = menu.addMenu("New")
            new_menu.addAction("Folder", self.create_new_folder)
            new_menu.addAction("Text Document", lambda: self.create_new_file(".txt"))
            paste_action = menu.addAction("Paste", self.paste_files)
            paste_action.setEnabled(bool(self._read_clipboard()[0]))
            menu.addSeparator()
            pinned = self.navigation_panel.is_favorite(self.current_path)
            menu.addAction("Unpin This Folder" if pinned else "Pin This Folder to Favorites",
                           self.toggle_favorite_current)
            menu.addAction("Properties", lambda: self.show_properties(self.current_path))
            self._decorate_menu(menu)
            menu.exec(view.viewport().mapToGlobal(position))
            return

        single = len(paths) == 1
        open_action = menu.addAction("Open")
        new_window_action = None
        new_tab_action = pin_action = None
        if single and os.path.isdir(paths[0]):
            new_tab_action = menu.addAction("Open in New Tab")
            new_window_action = menu.addAction("Open in New Window")
            pinned = self.navigation_panel.is_favorite(paths[0])
            pin_action = menu.addAction("Unpin from Favorites" if pinned else "Pin to Favorites")
        menu.addSeparator()
        to_pane_action = move_to_pane_action = None
        if self.folder_pane.isVisible():
            to_pane_action = menu.addAction("Copy to Other Pane")
            move_to_pane_action = menu.addAction("Move to Other Pane")
            menu.addSeparator()
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        copy_path_action = menu.addAction("Copy as Path")
        menu.addSeparator()
        compress_action = menu.addAction("Compress to ZIP")
        extract_action = extract_to_action = None
        if single and is_archive(paths[0]):
            extract_action = menu.addAction("Extract")
            extract_to_action = menu.addAction("Extract to...")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        rename_action = menu.addAction("Rename" if single else f"Rename {len(paths)} Items...")
        menu.addSeparator()
        properties_action = menu.addAction("Properties")
        properties_action.setEnabled(single)

        self._decorate_menu(menu)
        action = menu.exec(view.viewport().mapToGlobal(position))

        if action == open_action:
            self.open_path(paths[0])
        elif new_window_action is not None and action == new_window_action:
            self.open_in_new_window(paths[0])
        elif new_tab_action is not None and action == new_tab_action:
            self.new_tab(paths[0])
        elif pin_action is not None and action == pin_action:
            self.toggle_favorite(paths[0])
        elif action == copy_action:
            self.copy_selected_files(paths)
        elif action == cut_action:
            self.cut_selected_files(paths)
        elif to_pane_action is not None and action == to_pane_action:
            self.send_to_other_pane(paths, from_pane=False, move=False)
        elif move_to_pane_action is not None and action == move_to_pane_action:
            self.send_to_other_pane(paths, from_pane=False, move=True)
        elif action == compress_action:
            self.compress_files(paths)
        elif extract_action is not None and action == extract_action:
            self.extract_archive_file(paths[0])
        elif extract_to_action is not None and action == extract_to_action:
            self.extract_archive_file(paths[0], choose_folder=True)
        elif action == copy_path_action:
            QApplication.clipboard().setText("\n".join(paths))
            self.status_label.setText(f"Copied {len(paths)} path(s)")
        elif action == delete_action:
            self.delete_selected_files(paths)
        elif action == rename_action:
            if single:
                self.rename_selected_file(paths[0])
            else:
                self.bulk_rename(paths)
        elif action == properties_action:
            self.show_properties(paths[0])

    # -------------------------- Clipboard --------------------------

    def _write_clipboard(self, paths, cut):
        """Put file paths on the system clipboard as file URLs."""
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        mime.setText("\n".join(paths))
        if cut:
            mime.setData(CUT_MIME, b"1")
        if IS_WINDOWS:
            mime.setData(WIN_DROP_EFFECT_MIME, struct.pack("<I", DROPEFFECT_MOVE if cut else DROPEFFECT_COPY))
        QApplication.clipboard().setMimeData(mime)

    def _read_clipboard(self):
        """Read file paths from the system clipboard.

        Returns:
            tuple: (paths, is_cut)
        """
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasUrls():
            return [], False
        paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
        is_cut = mime.hasFormat(CUT_MIME)
        if not is_cut and mime.hasFormat(WIN_DROP_EFFECT_MIME):
            data = bytes(mime.data(WIN_DROP_EFFECT_MIME))
            is_cut = len(data) >= 4 and struct.unpack("<I", data[:4])[0] & DROPEFFECT_MOVE == DROPEFFECT_MOVE
        return paths, is_cut

    def copy_selected_files(self, paths=None):
        """Copy selected files to clipboard."""
        paths = paths or self.selected_paths()
        if not paths:
            return
        self._write_clipboard(paths, cut=False)
        self.status_label.setText(f"Copied {len(paths)} items to clipboard")

    def cut_selected_files(self, paths=None):
        """Cut selected files (mark for move operation)."""
        paths = paths or self.selected_paths()
        if not paths:
            return
        self._write_clipboard(paths, cut=True)
        self.status_label.setText(f"Cut {len(paths)} items to clipboard")

    # -------------------------- File operations --------------------------

    def _can_modify_current_folder(self, action):
        """Check the folder being shown can be written to (see _can_modify_folder)."""
        if self.current_view != "files":
            QMessageBox.information(self, f"Cannot {action.capitalize()}",
                                    f"Please navigate to a folder before you {action}.")
            return False
        return self._can_modify_folder(self.current_path, action)

    def _can_modify_folder(self, folder, action):
        """Check a folder can be written to, asking about protected folders.

        Args:
            folder: Folder that will be modified
            action: Verb for messages, e.g. "paste"

        Returns:
            bool: True if the operation may go ahead
        """
        if self.safety_manager.is_location_protected(folder):
            confirm = QMessageBox.question(
                self,
                "Protected Location",
                f"You're attempting to {action} in a system folder. This could harm your system. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return False

        if self.safety_manager.requires_admin_privileges(folder):
            QMessageBox.warning(self, "Administrator Rights Required",
                                "This location requires administrator rights to modify.")
            return False
        return True

    def delete_selected_files(self, paths=None, permanent=False):
        """Delete selected files with safety checks, using the recycle bin when possible.

        Args:
            paths: Paths to delete; defaults to the current selection
            permanent: Skip the recycle bin (Shift+Delete)
        """
        paths = paths or self.selected_paths()
        if not paths:
            return

        is_safe, warning = self.safety_manager.check_delete_safety(paths)

        target = "permanently delete" if permanent else "move to the Recycle Bin"
        if len(paths) == 1:
            message = f"Are you sure you want to {target} '{os.path.basename(paths[0])}'?"
        else:
            message = f"Are you sure you want to {target} these {len(paths)} items?"
        if not is_safe:
            message = f"{warning}\n\n{message}"

        confirm = QMessageBox.question(
            self, "Delete", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        to_delete = paths
        if not permanent:
            to_delete = self.safety_manager.move_to_recycle_bin(paths)
            if to_delete:
                perm_confirm = QMessageBox.question(
                    self,
                    "Permanent Deletion",
                    f"{len(to_delete)} item(s) cannot be moved to the Recycle Bin. Permanently delete them instead?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if perm_confirm != QMessageBox.StandardButton.Yes:
                    to_delete = []

        errors = []
        for path in to_delete:
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except OSError as e:
                errors.append(f"Could not delete '{os.path.basename(path)}': {e}")

        if errors:
            QMessageBox.warning(self, "Delete Errors", "Errors occurred during deletion:\n\n" + "\n".join(errors))

        deleted = sum(1 for p in paths if not os.path.exists(p))
        self._remove_missing_search_results()
        self.update_status()
        self.status_label.setText(f"Deleted {deleted} of {len(paths)} items")

    def _remove_missing_search_results(self):
        """Drop search result rows whose files no longer exist."""
        model = self.search_results_model
        for row in reversed(range(model.rowCount())):
            path = model.item(row, 0).data(PATH_ROLE)
            if path and not os.path.exists(path):
                model.removeRow(row)

    def _plan_transfer(self, sources, destination, is_cut):
        """Work out where each pasted item goes, asking about conflicts.

        Args:
            sources: Paths being pasted
            destination: Folder being pasted into
            is_cut: True for a move, False for a copy

        Returns:
            tuple: (plan, errors) where plan is a list of (source, target, overwrite),
                or (None, errors) if the user cancelled
        """
        verb = "move" if is_cut else "copy"
        plan, errors = [], []
        replace_all = None  # None = ask, True = replace all, False = skip all

        for source in sources:
            name = os.path.basename(os.path.normpath(source))
            if os.path.isdir(source) and is_within(destination, source):
                errors.append(f"Cannot {verb} '{name}' into itself")
                continue

            target = os.path.join(destination, name)
            overwrite = False
            if paths_equal(source, target):
                if is_cut:
                    continue  # Moving a file onto itself does nothing
                target = unique_target_path(destination, name)
            elif os.path.exists(target):
                replace = replace_all
                if replace is None:
                    answer = QMessageBox.question(
                        self,
                        "Replace or Skip",
                        f"'{name}' already exists in this folder. Do you want to replace it?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.YesToAll |
                        QMessageBox.StandardButton.No | QMessageBox.StandardButton.NoToAll |
                        QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.No
                    )
                    if answer == QMessageBox.StandardButton.Cancel:
                        return None, errors
                    replace = answer in (QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.YesToAll)
                    if answer in (QMessageBox.StandardButton.YesToAll, QMessageBox.StandardButton.NoToAll):
                        replace_all = replace
                if not replace:
                    continue
                overwrite = True
            plan.append((source, target, overwrite))
        return plan, errors

    @staticmethod
    def _transfer(source, target, is_cut, overwrite):
        """Copy or move one item. Existing folders are merged, existing files replaced."""
        source_is_dir = os.path.isdir(source) and not os.path.islink(source)
        if overwrite and os.path.exists(target) and not (source_is_dir and os.path.isdir(target)):
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.remove(target)

        if source_is_dir and os.path.isdir(target):
            # Merge into the existing folder
            shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
            if is_cut:
                shutil.rmtree(source)
        elif is_cut:
            shutil.move(source, target)
        elif source_is_dir:
            shutil.copytree(source, target, symlinks=True)
        else:
            shutil.copy2(source, target, follow_symlinks=False)

    def paste_files(self):
        """Paste files from clipboard to current directory with safety checks."""
        sources, is_cut = self._read_clipboard()
        sources = [p for p in sources if os.path.exists(p)]
        if not sources:
            self.status_label.setText("Nothing to paste")
            return

        destination = self._target_folder("paste")
        if destination is None or not self._can_modify_folder(destination, "paste"):
            return

        if self.transfer_files(sources, destination, is_cut, check_folder=False) and is_cut:
            # A cut can only be pasted once
            QApplication.clipboard().clear()

    def transfer_files(self, sources, destination, is_cut, check_folder=True):
        """Copy or move files into a folder (used by paste and drag and drop).

        Args:
            sources: Paths to copy or move
            destination: Folder to put them in
            is_cut: True to move, False to copy
            check_folder: Run the protected-folder checks on destination

        Returns:
            bool: True if the operation ran (it may still have had errors)
        """
        sources = [p for p in sources if os.path.exists(p)]
        if not sources or not os.path.isdir(destination):
            return False
        if check_folder and not self._can_modify_folder(destination, "move files" if is_cut else "copy files"):
            return False

        plan, errors = self._plan_transfer(sources, destination, is_cut)
        if plan is None:
            return False
        if not plan and not errors:
            return False

        operation = "move" if is_cut else "copy"
        progress = None
        if len(plan) > PROGRESS_DIALOG_THRESHOLD:
            progress = QProgressDialog(f"{'Moving' if is_cut else 'Copying'} {len(plan)} items...",
                                       "Cancel", 0, len(plan), self)
            progress.setWindowTitle(f"{operation.capitalize()} Files")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)

        undo_items = []
        done = 0
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for i, (source, target, overwrite) in enumerate(plan):
                if progress is not None:
                    if progress.wasCanceled():
                        break
                    progress.setLabelText(f"{operation.capitalize()}: {os.path.basename(source)}")
                    progress.setValue(i)
                    QApplication.processEvents()
                try:
                    self._transfer(source, target, is_cut, overwrite)
                    done += 1
                    if not overwrite:  # Overwritten files can't be restored
                        undo_items.append((source, target))
                except (OSError, shutil.Error) as e:
                    errors.append(f"Error processing '{os.path.basename(source)}': {e}")
        finally:
            QApplication.restoreOverrideCursor()
            if progress is not None:
                progress.close()

        if undo_items:
            self.add_operation_to_history(operation, undo_items)

        if errors:
            self._show_errors(f"Errors occurred during {operation}:", errors)

        self.update_status()
        self._remove_missing_search_results()
        self.status_label.setText(f"{operation.capitalize()} completed: {done} items")
        return True

    def _show_errors(self, heading, errors):
        """Show a list of errors in a scrollable dialog."""
        error_dialog = QDialog(self)
        error_dialog.setWindowTitle("Operation Errors")
        error_dialog.setMinimumWidth(400)

        layout = QVBoxLayout(error_dialog)
        layout.addWidget(QLabel(heading))

        error_text = QTextEdit()
        error_text.setPlainText("\n".join(errors))
        error_text.setReadOnly(True)
        layout.addWidget(error_text)

        close_button = QPushButton("Close")
        close_button.clicked.connect(error_dialog.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)

        error_dialog.exec()

    def rename_selected_file(self, path=None):
        """Rename a file or folder.

        Args:
            path: Item to rename; defaults to the single selected item
        """
        if path is None:
            paths = self.selected_paths()
            if len(paths) > 1:
                self.bulk_rename(paths)
                return
            if not paths:
                return
            path = paths[0]

        old_name = os.path.basename(os.path.normpath(path))
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        new_name = new_name.strip()
        if not ok or not new_name or new_name == old_name:
            return
        if not is_valid_filename(new_name):
            QMessageBox.warning(self, "Invalid Name", f"'{new_name}' is not a valid file name.")
            return

        target = os.path.join(os.path.dirname(os.path.normpath(path)), new_name)
        # paths_equal allows case-only renames on case-insensitive file systems
        if os.path.exists(target) and not paths_equal(target, path):
            QMessageBox.warning(self, "Rename", f"'{new_name}' already exists.")
            return

        try:
            os.rename(path, target)
        except OSError as e:
            QMessageBox.warning(self, "Rename Failed", f"Could not rename '{old_name}': {e}")
            return

        self.add_operation_to_history("rename", [(path, target)])
        if self.current_view == "search":
            self._remove_missing_search_results()
        self.status_label.setText(f"Renamed to '{new_name}'")

    def bulk_rename(self, paths):
        """Rename several items at once with a live preview (see BulkRenameDialog)."""
        dialog = BulkRenameDialog(paths, self)
        if not dialog.exec():
            return
        pairs = dialog.rename_pairs()
        try:
            applied = execute_renames(pairs)
        except OSError as e:
            QMessageBox.warning(self, "Rename Failed",
                                f"Nothing was renamed: {e}")
            return
        if applied:
            self.add_operation_to_history("rename", applied)
        if self.current_view == "search":
            self._remove_missing_search_results()
        self.update_status()
        self.status_label.setText(f"Renamed {len(applied)} items")

    def show_properties(self, path):
        """Show the properties dialog for a file or folder."""
        if path and os.path.exists(path):
            PropertiesDialog(path, self).exec()

    def show_selected_properties(self):
        """Show properties for the selection, or the current folder if nothing is selected."""
        paths = self.selected_paths()
        if len(paths) == 1:
            self.show_properties(paths[0])
        elif not paths and self.current_view == "files":
            self.show_properties(self.current_path)

    def update_status(self):
        """Update the status bar with current folder information."""
        if self.current_view != "files":
            return
        try:
            file_count = dir_count = total_size = 0
            with os.scandir(self.current_path) as entries:
                for entry in entries:
                    if not self.show_hidden and entry.name.startswith("."):
                        continue
                    try:
                        if entry.is_dir():
                            dir_count += 1
                        else:
                            file_count += 1
                            total_size += entry.stat().st_size
                    except OSError:
                        continue
            self._folder_status = f"{file_count} files, {dir_count} folders | {format_size(total_size)}"
        except OSError as e:
            self._folder_status = f"Error reading directory: {e}"
        self._update_selection_status()

    def _update_selection_status(self):
        """Show folder info plus the number of selected items."""
        text = self._folder_status
        selected = len(self.get_selected_file_paths()) if self.current_view == "files" else 0
        if selected:
            text += f" | {selected} selected"
        self.status_label.setText(text)

    def create_new_folder(self):
        """Create a new folder in the current directory."""
        folder = self._target_folder("create a new folder")
        if folder is None:
            return

        default_name = os.path.basename(unique_target_path(folder, "New folder"))
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:", text=default_name)
        folder_name = folder_name.strip()
        if not ok or not folder_name:
            return
        if not is_valid_filename(folder_name):
            QMessageBox.warning(self, "Invalid Name", f"'{folder_name}' is not a valid folder name.")
            return

        try:
            os.mkdir(os.path.join(folder, folder_name))
            self.status_label.setText(f"Created folder: {folder_name}")
        except FileExistsError:
            QMessageBox.warning(self, "Error", f"A folder named '{folder_name}' already exists.")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create folder: {e}")

    def create_new_file(self, extension):
        """Create a new file with the given extension.

        Args:
            extension: File extension (e.g., ".txt")
        """
        folder = self._target_folder("create a new file")
        if folder is None:
            return

        default_name = os.path.basename(unique_target_path(folder, f"New File{extension}"))
        file_name, ok = QInputDialog.getText(self, f"New {extension[1:].upper()} File",
                                             "Enter file name:", text=default_name)
        file_name = file_name.strip()
        if not ok or not file_name:
            return

        if not file_name.lower().endswith(extension.lower()):
            file_name += extension
        if not is_valid_filename(file_name):
            QMessageBox.warning(self, "Invalid Name", f"'{file_name}' is not a valid file name.")
            return

        new_file_path = os.path.join(folder, file_name)
        templates = {
            ".html": "<!DOCTYPE html>\n<html>\n<head>\n\t<title>New Page</title>\n</head>\n<body>\n\t<h1>Hello World</h1>\n</body>\n</html>\n",
            ".py": "def main():\n    print('Hello World')\n\n\nif __name__ == '__main__':\n    main()\n",
            ".md": "# New Document\n\nEnter your text here.\n",
        }

        try:
            if extension == ".zip":
                # An empty file is not a valid archive; write an empty zip instead
                with zipfile.ZipFile(new_file_path, "x"):
                    pass
            else:
                with open(new_file_path, "x", encoding="utf-8") as f:
                    f.write(templates.get(extension, ""))
            self.status_label.setText(f"Created new file: {file_name}")
        except FileExistsError:
            QMessageBox.warning(self, "Error", f"A file named '{file_name}' already exists.")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not create file: {e}")

    # -------------------------- Archives --------------------------

    def _run_job(self, title, label, func, on_success):
        """Run func in the background with a cancellable progress dialog.

        Args:
            title: Dialog title
            label: Text shown while working
            func: Called as func(progress=..., cancel=...) in a worker thread
            on_success: Called with func's result in the UI thread
        """
        job = BackgroundJob(func, self)
        dialog = QProgressDialog(label, "Cancel", 0, 100, self)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(400)  # Quick jobs finish without a dialog
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.canceled.connect(job.cancel.set)
        job.progress.connect(lambda done, total: dialog.setValue(int(done * 100 / max(total, 1))))

        def finish():
            dialog.close()
            dialog.deleteLater()
            self._jobs.discard(job)
            job.deleteLater()

        def succeeded(result):
            finish()
            on_success(result)

        def failed(error):
            finish()
            self.update_status()
            if isinstance(error, ArchiveCancelled):
                self.status_label.setText(f"{title} cancelled")
            else:
                QMessageBox.warning(self, title, f"{title} failed:\n\n{error}")

        job.succeeded.connect(succeeded)
        job.failed.connect(failed)
        self._jobs.add(job)
        job.start()
        return job

    def compress_files(self, paths=None):
        """Compress files and folders into a new .zip next to them."""
        paths = paths or self.selected_paths()
        if not paths:
            return
        suggested = suggest_zip_path(paths)
        folder = os.path.dirname(suggested)
        name, ok = QInputDialog.getText(self, "Compress to ZIP", "Archive name:",
                                        text=os.path.basename(suggested))
        name = name.strip()
        if not ok or not name:
            return
        if not name.lower().endswith(".zip"):
            name += ".zip"
        if not is_valid_filename(name):
            QMessageBox.warning(self, "Invalid Name", f"'{name}' is not a valid file name.")
            return
        zip_path = os.path.join(folder, name)
        if os.path.exists(zip_path):
            QMessageBox.warning(self, "Compress to ZIP", f"'{name}' already exists.")
            return
        if not self._can_modify_folder(folder, "create an archive"):
            return

        def done(result):
            self.add_operation_to_history("copy", [(paths[0], zip_path)])
            self.update_status()
            self.status_label.setText(f"Compressed {len(paths)} item(s) into '{name}'")

        self._run_job("Compress", f"Compressing into {name}...",
                      lambda progress, cancel: create_zip(paths, zip_path, progress, cancel), done)

    def extract_archive_file(self, archive_path, choose_folder=False):
        """Extract an archive.

        By default a new folder named after the archive is used (or the
        archive's single top-level folder), so files never spill into the
        current folder. With choose_folder the user picks the destination.
        """
        try:
            if choose_folder:
                destination = QFileDialog.getExistingDirectory(
                    self, "Extract to", os.path.dirname(archive_path))
                if not destination:
                    return
                created = [os.path.join(destination, top) for top in archive_top_level_names(archive_path)
                           if not os.path.exists(os.path.join(destination, top))]
            else:
                destination, created_item = extract_destination(archive_path)
                created = [created_item]
        except Exception as e:
            QMessageBox.warning(self, "Extract", f"Cannot read '{os.path.basename(archive_path)}':\n\n{e}")
            return
        if not self._can_modify_folder(os.path.dirname(created[0]) if created else destination, "extract files"):
            return

        def done(result):
            if created:
                self.add_operation_to_history("copy", [(archive_path, path) for path in created])
            self.update_status()
            self.status_label.setText(f"Extracted '{archive_stem(archive_path)}'")

        self._run_job("Extract", f"Extracting {os.path.basename(archive_path)}...",
                      lambda progress, cancel: extract_archive(archive_path, destination, progress, cancel),
                      done)

    # -------------------------- Undo --------------------------

    def add_operation_to_history(self, op_type, items):
        """Add an operation to the history for potential undo.

        Args:
            op_type: Operation type ('copy', 'move', 'rename')
            items: List of (source, target) path pairs
        """
        self.operation_history.append({'type': op_type, 'items': items, 'timestamp': time.time()})
        del self.operation_history[:-MAX_UNDO_HISTORY]
        self._update_undo_button()

    def _update_undo_button(self):
        if self.operation_history:
            op = self.operation_history[-1]
            count = len(op['items'])
            self.undo_button.setEnabled(True)
            self.undo_button.setToolTip(f"Undo {op['type']} of {count} item{'s' if count != 1 else ''} (Ctrl+Z)")
        else:
            self.undo_button.setEnabled(False)
            self.undo_button.setToolTip("Undo (Ctrl+Z)")

    def undo_last_operation(self):
        """Undo the last copy, move or rename."""
        if not self.operation_history:
            return

        op = self.operation_history.pop()
        self._update_undo_button()

        errors = []
        if op['type'] == 'copy':
            # Send the copies to the recycle bin rather than deleting them outright
            targets = [target for _, target in op['items'] if os.path.exists(target)]
            failed = self.safety_manager.move_to_recycle_bin(targets)
            if failed:
                confirm = QMessageBox.question(
                    self, "Undo Copy",
                    f"{len(failed)} copied item(s) cannot be moved to the Recycle Bin. Delete them permanently?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                for target in failed:
                    if confirm != QMessageBox.StandardButton.Yes:
                        errors.append(f"Kept copy '{os.path.basename(target)}'")
                        continue
                    try:
                        if os.path.isdir(target) and not os.path.islink(target):
                            shutil.rmtree(target)
                        else:
                            os.remove(target)
                    except OSError as e:
                        errors.append(f"Could not remove copy '{os.path.basename(target)}': {e}")
        elif op['type'] == 'rename':
            # Undo the whole rename at once, so swapped names are restored too
            try:
                execute_renames([(target, source) for source, target in op['items']])
            except OSError as e:
                errors.append(f"Nothing was renamed back: {e}")
        else:
            for source, target in reversed(op['items']):
                try:
                    if not os.path.exists(target):
                        errors.append(f"'{os.path.basename(target)}' no longer exists")
                    elif os.path.exists(source) and not paths_equal(source, target):
                        errors.append(f"'{source}' already exists")
                    else:
                        shutil.move(target, source)
                except (OSError, shutil.Error) as e:
                    errors.append(f"'{os.path.basename(target)}': {e}")

        if errors:
            self._show_errors(f"Some items could not be restored while undoing the {op['type']}:", errors)
        self.status_label.setText(f"Undid {op['type']} operation")
        self.update_status()

    # -------------------------- Dual pane --------------------------

    def set_dual_pane_visible(self, visible, path=None):
        """Show or hide the second folder pane beside the main view."""
        self.folder_pane.setVisible(visible)
        self.dual_pane_button.setChecked(visible)
        if visible:
            if path and os.path.isdir(path):
                self.folder_pane.navigate(path)
            elif not self.folder_pane.current_path:
                self.folder_pane.navigate(self.current_path)
            sizes = self.main_splitter.sizes()
            half = max(1, (sizes[0] + sizes[1]) // 2)
            self.main_splitter.setSizes([half, half] + sizes[2:])
            self.folder_pane.view.setFocus()
        else:
            self._set_pane_active(False)
        self._update_active_pane_style()

    def pane_is_active(self):
        """Whether commands apply to the second pane (it was clicked last)."""
        return self._pane_active and self.folder_pane.isVisible()

    def _set_pane_active(self, active):
        if self._pane_active != active:
            self._pane_active = active
            self._update_active_pane_style()
            self._preview_selection()

    def _update_active_pane_style(self):
        """Mark the active pane with an accent line while both panes are shown."""
        both = self.folder_pane.isVisible()
        self.folder_pane.set_active(both and self._pane_active)
        self.content_frame.setProperty("active", both and not self._pane_active)
        self.content_frame.style().unpolish(self.content_frame)
        self.content_frame.style().polish(self.content_frame)

    def _on_focus_changed(self, old, new):
        """Track which pane the user is working in (toolbar clicks don't change it)."""
        if new is None or not self.isAncestorOf(new):
            return
        if self.folder_pane.isAncestorOf(new):
            self._set_pane_active(True)
        elif self.views_stack.isAncestorOf(new):
            self._set_pane_active(False)

    def _target_folder(self, action):
        """The folder new items go into: the active pane's folder, or None with a message."""
        if self.pane_is_active():
            return self.folder_pane.current_path
        if self.current_view != "files":
            QMessageBox.information(self, f"Cannot {action.split()[0].capitalize()}",
                                    f"Please navigate to a folder before you {action}.")
            return None
        return self.current_path

    def other_pane_folder(self, from_pane):
        """The folder shown in the pane opposite to the one items come from."""
        if from_pane:
            return self.current_path if self.current_view == "files" else None
        return self.folder_pane.current_path if self.folder_pane.isVisible() else None

    def send_to_other_pane(self, paths, from_pane, move):
        """Copy or move items into the folder shown in the other pane."""
        destination = self.other_pane_folder(from_pane)
        if destination:
            self.transfer_files(paths, destination, move)

    def show_pane_context_menu(self, paths, global_pos):
        """Right-click menu for the second pane."""
        self._set_pane_active(True)
        menu = QMenu(self)
        if not paths:
            paste_action = menu.addAction("Paste", self.paste_files)
            paste_action.setEnabled(bool(self._read_clipboard()[0]))
            menu.addAction("New Folder", self.create_new_folder)
            menu.addAction("Refresh", self.folder_pane.refresh)
            menu.addSeparator()
            menu.addAction("Properties", lambda: self.show_properties(self.folder_pane.current_path))
        else:
            single = len(paths) == 1
            menu.addAction("Open", lambda: self.folder_pane.navigate(paths[0]) if os.path.isdir(paths[0])
                           else self.open_path(paths[0]))
            if single and os.path.isdir(paths[0]):
                menu.addAction("Open in New Tab", lambda: self.new_tab(paths[0]))
            menu.addSeparator()
            other = self.other_pane_folder(from_pane=True) is not None
            menu.addAction("Copy to Other Pane", lambda: self.send_to_other_pane(paths, True, False)).setEnabled(other)
            menu.addAction("Move to Other Pane", lambda: self.send_to_other_pane(paths, True, True)).setEnabled(other)
            menu.addSeparator()
            menu.addAction("Cut", lambda: self.cut_selected_files(paths))
            menu.addAction("Copy", lambda: self.copy_selected_files(paths))
            menu.addAction("Delete", lambda: self.delete_selected_files(paths))
            menu.addAction("Rename" if single else f"Rename {len(paths)} Items...",
                           lambda: self.rename_selected_file(paths[0]) if single else self.bulk_rename(paths))
            menu.addSeparator()
            menu.addAction("Properties", lambda: self.show_properties(paths[0])).setEnabled(single)
        self._decorate_menu(menu)
        menu.exec(global_pos)

    # -------------------------- Tabs --------------------------

    @property
    def history(self):
        """Back/forward history of the current tab."""
        return self._tab(self.tab_bar.currentIndex()).history

    def _tab(self, index):
        return self.tab_bar.tabData(index)

    def _open_initial_tabs(self):
        """Open the tabs from the last session, or one tab at the start folder."""
        locations = []
        if self.restore_tabs:
            saved = self.settings.value("tabs", [], type=list)
            locations = [loc for loc in saved if loc == "pc" or (isinstance(loc, str) and os.path.isdir(loc))]
        if not locations:
            locations = [self.current_path]
        for location in locations:
            self.new_tab(location, select=False, position=self.tab_bar.count())
        current = int(self.settings.value("current_tab", 0)) if self.restore_tabs else 0
        current = current if 0 <= current < self.tab_bar.count() else 0
        if self.tab_bar.currentIndex() == current:
            self._on_tab_changed(current)
        else:
            self.tab_bar.setCurrentIndex(current)

    def new_tab(self, location=None, select=True, position=None):
        """Open a new tab.

        Args:
            location: Folder path or "pc"; defaults to the current location
            select: Switch to the new tab
            position: Tab index; defaults to just after the current tab, like a browser
        """
        if location is None:
            location = "pc" if self.current_view == "drives" else self.current_path
        elif location != "pc":
            if not os.path.isdir(location):
                return
            location = normalize_path(location)
        tab = BrowserTab(location)
        title = "This PC" if location == "pc" else (os.path.basename(os.path.normpath(location)) or location)
        if position is None:
            position = self.tab_bar.currentIndex() + 1
        index = self.tab_bar.insertTab(position, self._location_icon(location), title)
        self.tab_bar.setTabData(index, tab)
        self._add_tab_close_button(index)
        self.tab_bar.setTabToolTip(index, "This PC" if location == "pc" else location)
        if select:
            self.tab_bar.setCurrentIndex(index)

    def close_tab(self, index):
        """Close a tab; closing the last tab closes the window."""
        if index < 0:
            return
        if self.tab_bar.count() == 1:
            self.close()
            return
        self.tab_bar.removeTab(index)

    def _cycle_tab(self, step):
        count = self.tab_bar.count()
        if count > 1:
            self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() + step) % count)

    def _on_tab_changed(self, index):
        """Show the location of the newly selected tab."""
        tab = self._tab(index) if index >= 0 else None
        # Reordering tabs also changes the index; only react to a real switch
        if tab is None or tab is self._shown_tab:
            return
        self._shown_tab = tab
        if self.is_searching:
            self._exit_search_mode()
        self._go_to_history_entry(self.history.current)

    def _set_tab_title(self, title, tooltip):
        index = self.tab_bar.currentIndex()
        if index >= 0:
            self.tab_bar.setTabText(index, title)
            self.tab_bar.setTabToolTip(index, tooltip)
            self.tab_bar.setTabIcon(index, self._location_icon("pc" if tooltip == "This PC" else tooltip))

    def _location_icon(self, location):
        """Tab icon: a computer for This PC, otherwise a folder."""
        if location == "pc":
            return ui_icon("pc", self.icon_color)
        return file_type_icon("folder")

    # -------------------------- Favorites --------------------------

    def toggle_favorite(self, path):
        """Pin a folder to the sidebar Favorites, or unpin it."""
        if self.navigation_panel.is_favorite(path):
            self.navigation_panel.remove_favorite(path)
            self.status_label.setText(f"Unpinned '{os.path.basename(os.path.normpath(path)) or path}'")
        else:
            self.navigation_panel.add_favorite(path)
            self.status_label.setText(f"Pinned '{os.path.basename(os.path.normpath(path)) or path}' to Favorites")
        if self.current_view == "files":
            self._update_navigation_selection(self.current_path)

    def toggle_favorite_current(self):
        """Pin or unpin the folder being shown."""
        if self.current_view == "files":
            self.toggle_favorite(self.current_path)

    # -------------------------- Navigation --------------------------

    def refresh_drives(self):
        """Refresh drives in both the drives view and navigation panel."""
        if self.current_view == "drives":
            self.drives_view.load_drives()
        self.navigation_panel.refresh_drives()

    def handle_navigation_item(self, item_id, path):
        """Handle navigation panel item selection.

        Args:
            item_id: ID of the clicked item
            path: Path to navigate to
        """
        if item_id == "pc":
            self.show_drives_view()
        elif item_id == "settings":
            self.show_settings()
        else:
            self.navigate_to(path)

    def show_settings(self):
        """Show settings dialog."""
        if not self.settings_dialog:
            self.settings_dialog = SettingsDialog(self.theme_manager, self)
        self.settings_dialog.exec()

    def set_preview_visible(self, visible):
        """Show or hide the preview panel."""
        self.preview_pane.setVisible(visible)
        self.toggle_preview_button.setChecked(visible)
        self.toggle_preview_button.setToolTip("Hide Preview Panel" if visible else "Show Preview Panel")
        if visible:
            width = self.main_splitter.width()
            self.main_splitter.setSizes([max(1, width - 320), 320])
            self._preview_selection()

    def toggle_preview_panel(self):
        """Toggle the visibility of the preview panel."""
        self.set_preview_visible(not self.preview_pane.isVisible())

    def _preview_selection(self):
        """Preview the first selected file, if the preview panel is open."""
        if not self.preview_pane.isVisible():
            return
        paths = self.selected_paths()
        if paths and os.path.exists(paths[0]):
            self.preview_pane.preview_file(paths[0])
        else:
            self.preview_pane.clear_preview()

    def _apply_list_mode(self, index):
        """Configure the QListView for icon or list display."""
        if index == VIEW_ICONS:
            self.file_view.setViewMode(QListView.ViewMode.IconMode)
            self.file_view.setGridSize(QSize(124, 118))
            self.file_view.setIconSize(QSize(72, 72))
            self.file_view.setSpacing(6)
            self.file_view.setWordWrap(True)
        else:
            self.file_view.setViewMode(QListView.ViewMode.ListMode)
            self.file_view.setGridSize(QSize())
            self.file_view.setIconSize(QSize(18, 18))
            self.file_view.setSpacing(1)
            self.file_view.setWordWrap(False)
        # setViewMode resets this; keep items from being dragged around inside the view
        self.file_view.setMovement(QListView.Movement.Static)

    def _show_file_view(self):
        """Show the folder view that matches the selected view mode."""
        if self.view_mode_combo.currentIndex() == VIEW_DETAILS:
            self.views_stack.setCurrentWidget(self.detail_view)
        else:
            self.views_stack.setCurrentWidget(self.file_view)

    def change_view_mode(self, index):
        """Change the view mode of the file explorer.

        Args:
            index: View mode index (0=Icons, 1=List, 2=Details)
        """
        if index in (VIEW_ICONS, VIEW_LIST):
            self._apply_list_mode(index)
        # Picture thumbnails only in the icon view; small type icons elsewhere
        self.file_model.set_thumbnails_enabled(index == VIEW_ICONS)
        if self.current_view == "files":
            self._show_file_view()
            self._update_selection_status()

    def show_drives_view(self, add_to_history=True):
        """Switch to the drives view."""
        if self.is_searching:
            self.clear_search()
        if add_to_history:
            self.history.visit("pc")

        self.current_view = "drives"
        self.views_stack.setCurrentWidget(self.drives_view)

        self.setWindowTitle("This PC - Shadows File Explorer")
        self._set_tab_title("This PC", "This PC")
        self.breadcrumb_bar.set_path("This PC")
        self.navigation_panel.set_active_item("pc")
        self._update_nav_buttons()

        self.drives_view.load_drives()
        self.preview_pane.clear_preview()
        self.status_label.setText(f"{len(self.drives_view.drive_widgets)} drives")

    def on_file_selection_changed(self, selected, deselected):
        """Update the preview and status bar when the folder selection changes."""
        self._preview_selection()
        self._update_selection_status()

    def on_search_selection_changed(self, selected, deselected):
        """Update the preview when the search result selection changes."""
        self._preview_selection()

    def navigate_to(self, path):
        """Navigate to a directory, or to "pc" for the drives view.

        Args:
            path: Path to navigate to
        """
        if path == "pc":
            self.show_drives_view()
            return
        if not path:
            return

        path = normalize_path(path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Error", f"Path does not exist or is not a directory: {path}")
            return

        if self.is_searching:
            self.clear_search()

        self.history.visit(path)
        self._show_directory(path)

    def _show_directory(self, path):
        """Display a folder without touching the history."""
        self.current_path = path
        self.current_view = "files"

        root = self.file_model.setRootPath(path)
        self.file_view.setRootIndex(root)
        self.detail_view.setRootIndex(root)
        self.file_view.clearSelection()
        self.detail_view.clearSelection()
        self._show_file_view()

        self.breadcrumb_bar.set_path(path)
        name = os.path.basename(os.path.normpath(path)) or path
        self.setWindowTitle(f"{name} - Shadows File Explorer")
        self._set_tab_title(name, path)

        self._update_nav_buttons()
        self._update_navigation_selection(path)
        self.preview_pane.clear_preview()
        self.update_status()

    def _go_to_history_entry(self, path):
        """Show a location taken from the history."""
        if self.is_searching:
            self.clear_search()
        if path == "pc":
            self.show_drives_view(add_to_history=False)
        elif os.path.isdir(path):
            self._show_directory(path)
        else:
            self._update_nav_buttons()
            QMessageBox.warning(self, "Error", f"Folder no longer exists: {path}")

    def _update_nav_buttons(self):
        """Enable or disable back/forward/up for the current location."""
        self.back_button.setEnabled(self.history.can_go_back())
        self.forward_button.setEnabled(self.history.can_go_forward())
        self.up_button.setEnabled(self.current_view in ("files", "search"))

    def _update_navigation_selection(self, path):
        """Highlight the sidebar item that matches path, if any.

        Args:
            path: Current path
        """
        self.navigation_panel.set_active_item(self.navigation_panel.item_id_for_path(path))

    def navigate_back(self):
        """Navigate to previous location in history."""
        path = self.history.back()
        if path is not None:
            self._go_to_history_entry(path)

    def navigate_forward(self):
        """Navigate to next location in history."""
        path = self.history.forward()
        if path is not None:
            self._go_to_history_entry(path)

    def navigate_up(self):
        """Navigate to the parent directory; from a drive root, go to This PC."""
        if self.current_view == "drives":
            return
        if self.current_view == "search":
            # Leave the search and return to the folder that was searched
            self.clear_search()
            return
        parent = os.path.dirname(os.path.normpath(self.current_path))
        if parent and not paths_equal(parent, self.current_path):
            self.navigate_to(parent)
        elif IS_WINDOWS:
            self.show_drives_view()

    def refresh_view(self):
        """Refresh the current view."""
        if self.is_searching:
            self.search_files()
        elif self.current_view == "drives":
            self.drives_view.load_drives()
        else:
            self._show_directory(self.current_path)
        if self.folder_pane.isVisible():
            self.folder_pane.refresh()

    # -------------------------- Search --------------------------

    def show_advanced_search(self):
        """Show the advanced search dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Search")
        dialog.setMinimumWidth(450)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)

        term_edit = QLineEdit(self.search_box.text())
        term_edit.setPlaceholderText("File name contains...")
        layout.addWidget(term_edit)

        # Date modified group
        date_group = QGroupBox("Date Modified")
        date_layout = QVBoxLayout(date_group)

        date_any = QRadioButton("Any time")
        date_any.setChecked(True)

        date_after = QRadioButton("After:")
        date_after_edit = QDateEdit()
        date_after_edit.setCalendarPopup(True)
        date_after_edit.setDate(date_after_edit.date().currentDate())
        date_after_layout = QHBoxLayout()
        date_after_layout.addWidget(date_after)
        date_after_layout.addWidget(date_after_edit, 1)

        date_before = QRadioButton("Before:")
        date_before_edit = QDateEdit()
        date_before_edit.setCalendarPopup(True)
        date_before_edit.setDate(date_before_edit.date().currentDate())
        date_before_layout = QHBoxLayout()
        date_before_layout.addWidget(date_before)
        date_before_layout.addWidget(date_before_edit, 1)

        date_layout.addWidget(date_any)
        date_layout.addLayout(date_after_layout)
        date_layout.addLayout(date_before_layout)

        # Size group
        size_group = QGroupBox("Size")
        size_layout = QVBoxLayout(size_group)

        size_any = QRadioButton("Any size")
        size_any.setChecked(True)

        def size_row(label, default):
            radio = QRadioButton(label)
            value = QSpinBox()
            value.setRange(0, 999999)
            value.setValue(default)
            unit = QComboBox()
            unit.addItems(["KB", "MB", "GB"])
            row = QHBoxLayout()
            row.addWidget(radio)
            row.addWidget(value)
            row.addWidget(unit)
            size_layout.addLayout(row)
            return radio, value, unit

        size_layout.addWidget(size_any)
        size_larger, size_larger_value, size_larger_unit = size_row("Larger than:", 1)
        size_smaller, size_smaller_value, size_smaller_unit = size_row("Smaller than:", 100)

        # File type group
        type_group = QGroupBox("File Type")
        type_layout = QVBoxLayout(type_group)
        type_buttons = {}
        for key, label in (('all', "All types"), ('documents', "Documents"), ('images', "Pictures"),
                           ('music', "Music"), ('videos', "Videos"), ('folders', "Folders")):
            type_buttons[key] = QRadioButton(label)
            type_layout.addWidget(type_buttons[key])
        type_buttons['all'].setChecked(True)

        include_subfolders = QCheckBox("Include subfolders")
        include_subfolders.setChecked(True)

        # Restore the previous options
        previous = self.search_options or {}
        if previous.get('date_filter'):
            kind, date = previous['date_filter']
            radio, edit = (date_after, date_after_edit) if kind == 'after' else (date_before, date_before_edit)
            radio.setChecked(True)
            edit.setDate(date)
        if previous.get('type_filter') in type_buttons:
            type_buttons[previous['type_filter']].setChecked(True)
        include_subfolders.setChecked(previous.get('include_subfolders', True))

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("Search")
        ok_button.setProperty("class", "primary")
        ok_button.setDefault(True)
        ok_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)

        layout.addWidget(date_group)
        layout.addWidget(size_group)
        layout.addWidget(type_group)
        layout.addWidget(include_subfolders)
        layout.addLayout(button_layout)

        if not dialog.exec():
            return

        unit_bytes = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}
        options = {'include_subfolders': include_subfolders.isChecked()}

        if date_after.isChecked():
            options['date_filter'] = ('after', date_after_edit.date().toPyDate())
        elif date_before.isChecked():
            options['date_filter'] = ('before', date_before_edit.date().toPyDate())
        else:
            options['date_filter'] = None

        if size_larger.isChecked():
            options['size_filter'] = (size_larger_value.value() * unit_bytes[size_larger_unit.currentText()], None)
        elif size_smaller.isChecked():
            options['size_filter'] = (None, size_smaller_value.value() * unit_bytes[size_smaller_unit.currentText()])
        else:
            options['size_filter'] = None

        options['type_filter'] = next(key for key, button in type_buttons.items() if button.isChecked())
        self.search_options = options

        self.search_box.setText(term_edit.text())
        if self.search_box.text().strip():
            self.search_files()

    def search_files(self):
        """Performs a search for files matching the search term."""
        search_term = self.search_box.text().strip()
        if not search_term:
            self.clear_search()
            return

        # "AllDrives:" prefix, or searching from This PC, searches every drive
        all_drives = search_term.lower().startswith("alldrives:")
        if all_drives:
            search_term = search_term[len("alldrives:"):].strip()
            if not search_term:
                return
        all_drives = all_drives or self.current_view == "drives" or (
            self.current_view == "search" and self.search_scope_all_drives)

        if all_drives:
            search_locations = [drive.rootPath() for drive in QStorageInfo.mountedVolumes() if drive.isReady()]
            scope = "all drives"
        else:
            search_locations = [self.current_path]
            scope = self.current_path
        self.search_scope_all_drives = all_drives

        # Switch the UI into search mode
        self.is_searching = True
        self.current_view = "search"
        self.search_results_model.clear_results()
        self.views_stack.setCurrentWidget(self.search_view)
        self.search_status_widget.setVisible(True)
        self.stop_search_button.setEnabled(True)
        self.clear_search_button.setVisible(True)
        self.search_progress.setRange(0, 0)  # Busy indicator
        self.search_status_label.setText("Preparing search...")
        self.preview_pane.clear_preview()
        self._update_nav_buttons()

        self.file_searcher.configure_search(search_locations, search_term, self.search_options)
        self.search_start_time = time.time()
        self.search_scanned = 0
        if self.file_searcher.start_search():
            self.timer.start(200)

        options_text = ""
        if self.search_options and not self.search_options.get('include_subfolders', True):
            options_text = " (current folder only)"
        self.status_label.setText(f"Searching for '{search_term}' in {scope}{options_text}")

    def _finish_search_ui(self, message):
        """Stop the progress indicator and show a final message."""
        self.timer.stop()
        self.search_progress.setRange(0, 1)
        self.search_progress.setValue(1)
        self.stop_search_button.setEnabled(False)
        self.search_status_label.setText(message)

    def stop_search(self):
        """Stop the search operation, keeping the results found so far."""
        if self.file_searcher.is_running:
            self.file_searcher.stop()
            count = self.search_results_model.rowCount()
            self._finish_search_ui(f"Stopped. Found {count} items")

    def clear_search(self):
        """Clears search results and returns to normal directory view."""
        if not self.is_searching:
            return

        self._exit_search_mode()
        self._show_directory(self.current_path)

    def _exit_search_mode(self):
        """Stop any search and hide the search UI."""
        self.file_searcher.stop()
        self.timer.stop()
        self.is_searching = False
        self.search_results_model.clear_results()
        self.search_status_widget.setVisible(False)
        self.clear_search_button.setVisible(False)
        self.search_box.clear()

    def update_search_message(self, message):
        """Show status messages from the searcher in the status bar.

        Args:
            message: Status message
        """
        if self.is_searching:
            self.status_label.setText(message)

    def update_search_progress(self, scanned, total):
        """Track how many items the search has scanned.

        Args:
            scanned: Number of items scanned so far
            total: Total items, or -1 if unknown
        """
        self.search_scanned = scanned

    @staticmethod
    def _format_elapsed(elapsed):
        if elapsed < 60:
            return f"{elapsed:.1f} s"
        return f"{int(elapsed // 60)}:{int(elapsed % 60):02d} min"

    def update_search_status(self):
        """Updates the search status text with elapsed time."""
        if not self.is_searching:
            return
        elapsed = self._format_elapsed(time.time() - self.search_start_time)
        count = self.search_results_model.rowCount()
        self.search_status_label.setText(f"Found {count} items, scanned {self.search_scanned:,} ({elapsed})")

    def add_search_result(self, result):
        """Adds a found item to the search results.

        Args:
            result: SearchResult object
        """
        # Ignore results still queued from a search that was stopped or replaced
        if self.is_searching and result.search_id == self.file_searcher.search_id:
            self.search_results_model.add_result(result)

    def search_completed(self, search_id):
        """Called when a search operation is complete.

        Args:
            search_id: ID of the search that finished
        """
        if not self.is_searching or search_id != self.file_searcher.search_id:
            return
        count = self.search_results_model.rowCount()
        elapsed = self._format_elapsed(time.time() - self.search_start_time)
        self._finish_search_ui(f"Found {count} items in {elapsed}")
        self.status_label.setText(f"Search complete: {count} items found, {self.search_scanned:,} scanned")
