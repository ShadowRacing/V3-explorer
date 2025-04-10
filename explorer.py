#Explorer module for Shadows File Explorer.

#This module provides the ModernExplorer class which is the main window
#for the Shadows File Explorer application.

import os
import platform
import time
import shutil
import threading
from datetime import datetime

from PyQt6.QtWidgets import (QMainWindow, QSplitter, QWidget, QVBoxLayout, QStyle,
                            QHBoxLayout, QToolBar, QLabel, QLineEdit, 
                            QPushButton, QMenu, QMessageBox, QToolButton, 
                            QProgressBar, QListView, QTreeView, QComboBox, 
                            QInputDialog, QDialog, QTextEdit, QFrame, QDateEdit, QRadioButton , QGroupBox, QSpinBox, QCheckBox,QApplication,
                            QStackedWidget, QFileDialog, QSizePolicy)
from PyQt6.QtCore import (Qt, QSize, QDir, QTimer, QFileInfo, 
                         QStorageInfo)
from PyQt6.QtGui import (QStandardItemModel, QStandardItem, QFileSystemModel)

# Import our optimized modules
from theme_manager import ThemeManager
from file_operation_safety_manager import FileOperationSafetyManager
from navigation_panel import NavigationPanel
from breadcrumb_bar import FixedBreadcrumbBar
from drive_components import DriveInfo, DriveItemWidget, DrivesView
from preview_pane import PreviewPane
from file_searcher import FileSearcher, SearchResult
from search_results_model import SearchResultsModel
from settings_dialog import SettingsDialog


class ModernExplorer(QMainWindow):
    """Main window for Shadows File Explorer.
    
    This class provides:
    - Main application window and UI
    - Navigation and file browsing
    - File operations
    - Search functionality
    - Theme management
    """
    
    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("Shadows File Explorer")
        self.setMinimumSize(1000, 600)
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.theme_manager.theme_changed.connect(self.apply_theme)
        
        self.settings_dialog = None
        
        # Initialize history and current path
        self.history = []
        self.history_index = -1
        self.current_path = self._get_default_start_path()
        
        # Create models
        self.file_model = self._create_file_model()
        
        # Initialize the file searcher
        self.file_searcher = FileSearcher(self)
        
        # Search state
        self.is_searching = False
        self.search_results_model = SearchResultsModel(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_search_status)
        self.search_start_time = 0
        self.search_options = None
        
        # Content view state
        self.current_view = "files"  # Options: "files", "drives", "search"
        
        # Setup UI components
        self.setup_ui()
        
        # Initialize safety manager
        self.safety_manager = FileOperationSafetyManager(self)
        
        # For undo functionality
        self.operation_history = []
        
        # Set default theme
        self.theme_manager.set_theme("dark")
        self.apply_theme("dark")
        
        # Navigate to starting directory
        self.navigate_to(self.current_path)

        # Set up a timer to refresh drives
        self.drives_refresh_timer = QTimer(self)
        self.drives_refresh_timer.timeout.connect(self.refresh_drives)
        self.drives_refresh_timer.start(10000)  # Refresh every 10 seconds
    
 
    def show_search_context_menu(self, position):
        """Context menu for search results."""
        indexes = self.search_view.selectedIndexes()
        if not indexes:
            return
            
        # Get the item data from unique rows
        unique_paths = []
        seen_rows = set()
        
        for index in indexes:
            row = index.row()
            if row not in seen_rows:
                seen_rows.add(row)
                file_index = index.siblingAtColumn(0)  # First column contains the file path
                file_path = file_index.data(Qt.ItemDataRole.UserRole)
                if file_path and os.path.exists(file_path):
                    unique_paths.append(file_path)
        
        if not unique_paths:
            return
            
        menu = QMenu(self)
        
        # Add actions based on selection
        open_action = menu.addAction("Open")
        open_location_action = menu.addAction("Open Location")
        
        menu.addSeparator()
        
        copy_action = menu.addAction("Copy")
        
        menu.addSeparator()
        
        properties_action = menu.addAction("Properties")
        
        # Show the context menu
        action = menu.exec(self.search_view.mapToGlobal(position))
        
        # Process the chosen action
        if action == open_action:
            for file_path in unique_paths:
                if os.path.isdir(file_path):
                    self.clear_search()
                    self.navigate_to(file_path)
                    break
                else:
                    os.startfile(file_path)
        elif action == open_location_action:
            # Navigate to the containing folder of the first selected item
            folder_path = os.path.dirname(unique_paths[0])
            self.clear_search()
            self.navigate_to(folder_path)
        elif action == copy_action:
            # Add to clipboard
            self.copy_selected_files(unique_paths)
        elif action == properties_action:
            # Show file properties of the first selected item
            if len(unique_paths) == 1:
                self.show_properties(unique_paths[0])
    
        
    def copy_selected_files(self, paths=None):
        """Copy selected files to clipboard."""
        if not paths:
            # Get selected files from the active view
            if self.is_searching:
                paths = self.get_selected_search_paths()
            else:
                view = self.file_view if self.views_stack.currentWidget() == self.file_view else self.detail_view
                indexes = view.selectedIndexes()
                paths = []
                seen_rows = set()
                for index in indexes:
                    if index.row() not in seen_rows:
                        seen_rows.add(index.row())
                        paths.append(self.file_model.filePath(index))
        
        if not paths:
            return
            
        # Store paths in clipboard
        text = "\n".join(paths)
        QApplication.clipboard().setText(text)
        
        self.status_label.setText(f"Copied {len(paths)} items to clipboard")
    
    def cut_selected_files(self, paths=None):
        """Cut selected files (mark for move operation)."""
        if not paths:
            # Get selected files from the active view
            if self.is_searching:
                paths = self.get_selected_search_paths()
            else:
                view = self.file_view if self.views_stack.currentWidget() == self.file_view else self.detail_view
                indexes = view.selectedIndexes()
                paths = []
                seen_rows = set()
                for index in indexes:
                    if index.row() not in seen_rows:
                        seen_rows.add(index.row())
                        paths.append(self.file_model.filePath(index))
        
        if not paths:
            return
            
        # Store paths in clipboard with special format for cut operation
        text = "cut\n" + "\n".join(paths)
        QApplication.clipboard().setText(text)
        
        self.status_label.setText(f"Cut {len(paths)} items to clipboard")
    

        
    def delete_selected_files(self, paths=None):
        """Delete selected files with safety checks and recycle bin."""
        if not paths:
            # Get selected files from the active view
            if self.is_searching:
                paths = self.get_selected_search_paths()
            else:
                view = self.file_view if self.views_stack.currentWidget() == self.file_view else self.detail_view
                indexes = view.selectedIndexes()
                paths = []
                seen_rows = set()
                for index in indexes:
                    if index.row() not in seen_rows:
                        seen_rows.add(index.row())
                        paths.append(self.file_model.filePath(index))
        
        if not paths:
            return
        
        # Safety check
        is_safe, warning = self.safety_manager.check_delete_safety(paths)
        
        message = "Are you sure you want to move the selected items to the Recycle Bin?"
        if len(paths) == 1:
            filename = os.path.basename(paths[0])
            message = f"Are you sure you want to move '{filename}' to the Recycle Bin?"
        
        if not is_safe:
            message = f"{warning}\n\n{message}"
            
        confirm = QMessageBox.question(
            self, 
            "Delete",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # Try recycle bin first
            success = self.safety_manager.move_to_recycle_bin(paths)
            
            if not success:
                # Fallback to manual deletion with confirmation
                perm_confirm = QMessageBox.question(
                    self,
                    "Permanent Deletion",
                    "Cannot move items to Recycle Bin. Permanently delete instead?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if perm_confirm == QMessageBox.StandardButton.Yes:
                    errors = []
                    for path in paths:
                        try:
                            if os.path.isdir(path):
                                shutil.rmtree(path)
                            else:
                                os.remove(path)
                        except Exception as e:
                            errors.append(f"Could not delete '{os.path.basename(path)}': {str(e)}")
                    
                    if errors:
                        error_message = "\n".join(errors)
                        QMessageBox.warning(self, "Delete Errors", f"Errors occurred during deletion:\n\n{error_message}")
            
            # Refresh view
            self.refresh_view()
            
            # Update status
            self.status_label.setText(f"Deleted {len(paths)} items")
            
            # If in search mode, update search results
            if self.is_searching:
                self.search_files()
        
    def update_status(self):
        """Update the status bar with current folder information."""
        try:
            if self.is_searching:
                # Status updates handled by search methods
                return
                
            if self.current_view == "drives":
                # Show drive info in status bar
                total_drives = QDir.drives().count()
                self.status_label.setText(f"Showing {total_drives} drives")
                return
                
            file_count = len([name for name in os.listdir(self.current_path) if os.path.isfile(os.path.join(self.current_path, name))])
            dir_count = len([name for name in os.listdir(self.current_path) if os.path.isdir(os.path.join(self.current_path, name))])
            
            # Calculate total size
            total_size = sum(os.path.getsize(os.path.join(self.current_path, f)) 
                           for f in os.listdir(self.current_path) 
                           if os.path.isfile(os.path.join(self.current_path, f)))
            
            if total_size < 1024:
                size_str = f"{total_size} bytes"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size/1024:.1f} KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size/(1024*1024):.1f} MB"
            else:
                size_str = f"{total_size/(1024*1024*1024):.1f} GB"
                
            self.status_label.setText(f"{file_count} files, {dir_count} folders | {size_str}")
        except Exception as e:
            self.status_label.setText(f"Error reading directory: {str(e)}")


    def paste_files(self):
        """Paste files from clipboard to current directory with safety checks."""
        if self.is_searching or self.current_view == "drives":
            # Can't paste in search results or drives view
            QMessageBox.information(self, "Cannot Paste", 
                                "Please navigate to a folder before pasting.")
            return
        
        # Check if current location is protected
        if self.safety_manager.is_location_protected(self.current_path):
            confirm = QMessageBox.question(
                self, 
                "Protected Location",
                "You're attempting to paste into a system folder. This could harm your system. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        
        # Check if admin rights needed
        if self.safety_manager.requires_admin_privileges(self.current_path):
            QMessageBox.warning(self, "Administrator Rights Required", 
                            "This location requires administrator rights to modify.")
            return
        
        text = QApplication.clipboard().text()
        if not text:
            return
        
        # Parse clipboard content
        lines = text.split("\n")
        is_cut = lines[0] == "cut"
        
        # Skip the first line if it's a cut operation marker
        source_paths = lines[1:] if is_cut else lines
        
        if not source_paths:
            return
        
        # Validate paths
        valid_paths = [path for path in source_paths if os.path.exists(path)]
        
        if not valid_paths:
            QMessageBox.warning(self, "Paste Error", "No valid files found in clipboard.")
            return
        
        # Check for overwrite
        conflicts = []
        for source_path in valid_paths:
            basename = os.path.basename(source_path)
            target_path = os.path.join(self.current_path, basename)
            if os.path.exists(target_path):
                conflicts.append(basename)
        
        if conflicts:
            if len(conflicts) == 1:
                confirm = QMessageBox.question(
                    self,
                    "File Exists",
                    f"'{conflicts[0]}' already exists. Do you want to replace it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.YesToAll | 
                    QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.No
                )
                
                if confirm == QMessageBox.StandardButton.Cancel:
                    return
                elif confirm == QMessageBox.StandardButton.No:
                    # Skip this file
                    valid_paths = [p for p in valid_paths if os.path.basename(p) != conflicts[0]]
                elif confirm == QMessageBox.StandardButton.YesToAll:
                    # Replace all, continue with all paths
                    pass
                else:  # Yes - replace only this one
                    pass
            else:
                confirm = QMessageBox.question(
                    self,
                    "Files Exist",
                    f"{len(conflicts)} files already exist. Do you want to replace them?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.No
                )
                
                if confirm == QMessageBox.StandardButton.Cancel:
                    return
                elif confirm == QMessageBox.StandardButton.No:
                    # Skip conflicting files
                    valid_paths = [p for p in valid_paths if os.path.basename(p) not in conflicts]
        
        # Perform copy/move operation
        operation = "move" if is_cut else "copy"
        errors = []
        
        # Set up progress dialog for large operations
        if len(valid_paths) > 5:
            progress = QProgressBar(self)
            progress.setRange(0, len(valid_paths))
            progress.setValue(0)
            
            status_dialog = QDialog(self)
            status_dialog.setWindowTitle(f"{'Moving' if is_cut else 'Copying'} Files")
            status_dialog.setMinimumWidth(300)
            
            layout = QVBoxLayout(status_dialog)
            layout.addWidget(QLabel(f"{'Moving' if is_cut else 'Copying'} {len(valid_paths)} items..."))
            layout.addWidget(progress)
            
            status_dialog.show()
            QApplication.processEvents()
        
        for i, source_path in enumerate(valid_paths):
            try:
                basename = os.path.basename(source_path)
                target_path = os.path.join(self.current_path, basename)
                
                # Avoid overwriting existing files if not confirmed
                if os.path.exists(target_path) and basename not in conflicts:
                    # Generate unique name
                    name, ext = os.path.splitext(basename)
                    counter = 1
                    while True:
                        new_name = f"{name} ({counter}){ext}"
                        target_path = os.path.join(self.current_path, new_name)
                        if not os.path.exists(target_path):
                            break
                        counter += 1
                
                if operation == "copy":
                    if os.path.isdir(source_path):
                        # Simple directory copy
                        shutil.copytree(source_path, target_path)
                    else:
                        shutil.copy2(source_path, target_path)
                else:  # move
                    shutil.move(source_path, target_path)
                    
                # Update progress if shown
                if len(valid_paths) > 5:
                    progress.setValue(i + 1)
                    QApplication.processEvents()
                    
            except Exception as e:
                errors.append(f"Error processing '{basename}': {str(e)}")
        
        # Close progress dialog if shown
        if len(valid_paths) > 5:
            status_dialog.close()
        
        # Show errors if any
        if errors:
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Operation Errors")
            error_dialog.setMinimumWidth(400)
            
            layout = QVBoxLayout(error_dialog)
            layout.addWidget(QLabel(f"Errors occurred during {operation}:"))
            
            error_text = QTextEdit()
            error_text.setPlainText("\n".join(errors))
            error_text.setReadOnly(True)
            layout.addWidget(error_text)
            
            close_button = QPushButton("Close")
            close_button.clicked.connect(error_dialog.accept)
            layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
            
            error_dialog.exec()
        
        # Refresh view
        self.refresh_view()
        
        # Clear clipboard if it was a cut operation
        if is_cut:
            QApplication.clipboard().clear()
            
        self.status_label.setText(f"{operation.capitalize()} operation completed: {len(valid_paths)} items")
    

    def show_context_menu(self, position):
        view = self.sender()
        indexes = view.selectedIndexes()
        if not indexes:
            # No selection, show background context menu
            menu = QMenu(self)
            
            view_submenu = menu.addMenu("View")
            
            icons_action = view_submenu.addAction("Icons")
            icons_action.triggered.connect(lambda: self.view_mode_combo.setCurrentIndex(0))
            
            list_action = view_submenu.addAction("List")
            list_action.triggered.connect(lambda: self.view_mode_combo.setCurrentIndex(1))
            
            details_action = view_submenu.addAction("Details")
            details_action.triggered.connect(lambda: self.view_mode_combo.setCurrentIndex(2))
            
            menu.addSeparator()
            
            refresh_action = menu.addAction("Refresh")
            refresh_action.triggered.connect(self.refresh_view)
            
            menu.addSeparator()
            
            new_folder_action = menu.addAction("New Folder")
            new_folder_action.triggered.connect(self.create_new_folder)
            
            paste_action = menu.addAction("Paste")
            paste_action.triggered.connect(self.paste_files)
            
            menu.exec(view.mapToGlobal(position))
            return
        
        # Selection context menu
        unique_indexes = []
        seen_rows = set()
        for index in indexes:
            if index.row() not in seen_rows:
                seen_rows.add(index.row())
                unique_indexes.append(index)
        
        if not unique_indexes:
            return
            
        # Get model and path from the correct view
        if view == self.file_view or view == self.detail_view:
            model = self.file_model
            paths = [model.filePath(index) for index in unique_indexes]
        else:
            return
            
        menu = QMenu(self)
        
        # Add actions based on selection
        open_action = menu.addAction("Open")
        
        menu.addSeparator()
        
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        
        menu.addSeparator()
        
        delete_action = menu.addAction("Delete")
        rename_action = menu.addAction("Rename")
        
        menu.addSeparator()
        
        properties_action = menu.addAction("Properties")
        
        # Additional options for folders
        if len(paths) == 1 and os.path.isdir(paths[0]):
            explore_action = menu.addAction("Open in New Window")
        
        # Show the context menu
        action = menu.exec(view.mapToGlobal(position))
        
        # Process the chosen action
        if action == open_action:
            for path in paths:
                if os.path.isdir(path):
                    self.navigate_to(path)
                    break
                else:
                    os.startfile(path)
        elif action == copy_action:
            self.copy_selected_files(paths)
        elif action == cut_action:
            self.cut_selected_files(paths)
        elif action == delete_action:
            self.delete_selected_files(paths)
        elif action == rename_action:
            if len(paths) == 1:
                self.rename_selected_file(paths[0])
        elif action == properties_action:
            if len(paths) == 1:
                self.show_properties(paths[0])
    

    def _get_default_start_path(self):
        """Get the default starting path based on platform."""
        if platform.system() == "Windows":
            return os.path.expanduser("~")  # User's home directory
        else:
            return os.path.expanduser("~")  # User's home directory on Unix
    
    def _create_file_model(self):
        """Create and configure the file model.
        
        Returns:
            QFileSystemModel: Configured file model
        """
        model = QFileSystemModel()
        model.setRootPath("")
        # Set filters if needed, e.g. to show hidden files
        # model.setFilter(QDir.Filter.AllEntries | QDir.Filter.Hidden | QDir.Filter.System)
        return model
        
    def apply_theme(self, theme_name):
        """Apply the selected theme to the application.
        
        Args:
            theme_name: Name of the theme to apply
        """
        stylesheet = self.theme_manager.get_theme_stylesheet(theme_name)
        self.setStyleSheet(stylesheet)
        
        # Update window title to show theme
        theme_display = theme_name.capitalize()
        self.setWindowTitle(f"Shadows File Explorer - {theme_display} Theme")
    
    def setup_ui(self):
        """Set up the user interface."""
        # Create a central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main layout for central widget
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Setup app bar at top
        self._setup_app_bar()
        
        # Setup content area
        self._setup_content_area()
        
        # Setup bottom action bar
        self._setup_action_bar()
        
    def _setup_app_bar(self):
        """Set up the application bar at the top."""
        self.app_bar = QWidget()
        self.app_bar.setObjectName("appbar")
        self.app_bar.setMaximumHeight(40)
        self.app_bar_layout = QHBoxLayout(self.app_bar)
        self.app_bar_layout.setContentsMargins(8, 4, 8, 4)
        
        # App icon and title
        app_title_layout = QHBoxLayout()
        app_icon = QLabel()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        app_icon.setPixmap(icon.pixmap(24, 24))
        app_title_layout.addWidget(app_icon)
        
        app_title = QLabel("Shadows Explorer")
        app_title.setStyleSheet("font-weight: bold; font-size: 16px;")
        app_title_layout.addWidget(app_title)
        
        self.app_bar_layout.addLayout(app_title_layout)
        self.app_bar_layout.addSpacing(10)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(2)
        
        self.back_button = QToolButton()
        self.back_button.setText("←")
        self.back_button.setToolTip("Back")
        self.back_button.clicked.connect(self.navigate_back)
        self.back_button.setFixedSize(30, 30)
        nav_layout.addWidget(self.back_button)
        
        self.forward_button = QToolButton()
        self.forward_button.setText("→")
        self.forward_button.setToolTip("Forward")
        self.forward_button.clicked.connect(self.navigate_forward)
        self.forward_button.setFixedSize(30, 30)
        nav_layout.addWidget(self.forward_button)
        
        self.up_button = QToolButton()
        self.up_button.setText("↑")
        self.up_button.setToolTip("Up")
        self.up_button.clicked.connect(self.navigate_up)
        self.up_button.setFixedSize(30, 30)
        nav_layout.addWidget(self.up_button)
        
        self.refresh_button = QToolButton()
        self.refresh_button.setText("⟳")
        self.refresh_button.setToolTip("Refresh")
        self.refresh_button.clicked.connect(self.refresh_view)
        self.refresh_button.setFixedSize(30, 30)
        nav_layout.addWidget(self.refresh_button)
        
        self.undo_button = QToolButton()
        self.undo_button.setText("↩")
        self.undo_button.setToolTip("Undo")
        self.undo_button.clicked.connect(self.undo_last_operation)
        self.undo_button.setEnabled(False)  # Start disabled
        self.undo_button.setFixedSize(30, 30)
        nav_layout.addWidget(self.undo_button)
        
        self.app_bar_layout.addLayout(nav_layout)
        self.app_bar_layout.addSpacing(10)
        
        # Breadcrumb navigation
        self.breadcrumb_bar = FixedBreadcrumbBar()
        self.breadcrumb_bar.path_changed.connect(self.navigate_to)
        self.app_bar_layout.addWidget(self.breadcrumb_bar, 1)  # Give breadcrumb stretch
        
        # Search bar
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search files...")
        self.search_box.setToolTip("Search in current location, or use 'AllDrives:' prefix to search all drives")
        self.search_box.setMaximumWidth(200)
        self.search_box.returnPressed.connect(self.search_files)
        
        search_bar_layout = QHBoxLayout()
        search_bar_layout.setSpacing(0)
        
        self.search_button = QToolButton()
        self.search_button.setText("🔍")
        self.search_button.setToolTip("Search")
        self.search_button.clicked.connect(self.search_files)
        
        self.clear_search_button = QToolButton()
        self.clear_search_button.setText("✕")
        self.clear_search_button.setToolTip("Clear Search")
        self.clear_search_button.clicked.connect(self.clear_search)
        self.clear_search_button.setVisible(False)
        
        # Add advanced search button
        self.advanced_search_button = QToolButton()
        self.advanced_search_button.setText("⚙")
        self.advanced_search_button.setToolTip("Advanced Search")
        self.advanced_search_button.clicked.connect(self.show_advanced_search)
        
        search_bar_layout.addWidget(self.search_box)
        search_bar_layout.addWidget(self.search_button)
        search_bar_layout.addWidget(self.clear_search_button)
        search_bar_layout.addWidget(self.advanced_search_button)
        
        self.app_bar_layout.addLayout(search_bar_layout)
        
        # Theme selection button
        self.theme_button = QToolButton()
        self.theme_button.setText("⚙")
        self.theme_button.setToolTip("Settings")
        self.theme_button.clicked.connect(self.show_settings)
        self.app_bar_layout.addWidget(self.theme_button)
        
        # Preview toggle button
        self.toggle_preview_button = QToolButton()
        self.toggle_preview_button.setText("◪")
        self.toggle_preview_button.setToolTip("Toggle Preview Panel")
        self.toggle_preview_button.clicked.connect(self.toggle_preview_panel)
        self.toggle_preview_button.setStyleSheet("font-size: 16px;")
        self.app_bar_layout.addWidget(self.toggle_preview_button)
        
        self.main_layout.addWidget(self.app_bar)
        
    def _setup_content_area(self):
        """Set up the main content area."""
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(4)
        
        # Sidebar with navigation panel
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMaximumWidth(200)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.navigation_panel = NavigationPanel()
        self.navigation_panel.item_clicked.connect(self.handle_navigation_item)
        sidebar_layout.addWidget(self.navigation_panel)
        
        content_layout.addWidget(self.sidebar)
        
        # Main splitter for content and preview
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Content frame
        self.content_frame = QFrame()
        self.content_frame.setObjectName("content")
        content_frame_layout = QVBoxLayout(self.content_frame)
        content_frame_layout.setContentsMargins(0, 0, 0, 0)
        
        # View controls
        view_controls = QWidget()
        view_layout = QHBoxLayout(view_controls)
        view_layout.setContentsMargins(8, 4, 8, 4)
        
        view_label = QLabel("View:")
        view_layout.addWidget(view_label)
        
        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItems(["Icons", "List", "Details"])
        self.view_mode_combo.currentIndexChanged.connect(self.change_view_mode)
        view_layout.addWidget(self.view_mode_combo)
        
        view_layout.addStretch()
        
        # Search status
        self.search_status_widget = QWidget()
        self.search_status_widget.setVisible(False)
        search_status_layout = QHBoxLayout(self.search_status_widget)
        search_status_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_progress = QProgressBar()
        self.search_progress.setRange(0, 100)
        self.search_progress.setValue(0)
        self.search_progress.setTextVisible(True)
        self.search_progress.setMaximumWidth(150)
        
        self.search_status_label = QLabel("")
        
        self.stop_search_button = QPushButton("Stop")
        self.stop_search_button.clicked.connect(self.stop_search)
        self.stop_search_button.setMaximumWidth(80)
        
        search_status_layout.addWidget(self.search_progress)
        search_status_layout.addWidget(self.search_status_label, 1)
        search_status_layout.addWidget(self.stop_search_button)
        
        view_layout.addWidget(self.search_status_widget)
        
        content_frame_layout.addWidget(view_controls)
        
        # File views stack
        self.views_stack = QStackedWidget()
        
        # Icon view
        self.file_view = QListView()
        self.file_view.setModel(self.file_model)
        self.file_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.file_view.doubleClicked.connect(self.file_view_double_clicked)
        self.file_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_view.customContextMenuRequested.connect(self.show_context_menu)
        self.file_view.setViewMode(QListView.ViewMode.IconMode)
        self.file_view.setIconSize(QSize(64, 64))
        self.file_view.setGridSize(QSize(120, 120))
        self.file_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.file_view.setSpacing(10)
        self.file_view.selectionModel().selectionChanged.connect(self.on_file_selection_changed)
        
        # Detail view
        self.detail_view = QTreeView()
        self.detail_view.setModel(self.file_model)
        self.detail_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.detail_view.doubleClicked.connect(self.file_view_double_clicked)
        self.detail_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.detail_view.customContextMenuRequested.connect(self.show_context_menu)
        self.detail_view.setSortingEnabled(True)
        self.detail_view.setRootIsDecorated(False)
        self.detail_view.selectionModel().selectionChanged.connect(self.on_file_selection_changed)
        
        # Search results view
        self.search_view = QTreeView()
        self.search_view.setModel(self.search_results_model)
        self.search_view.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.search_view.doubleClicked.connect(self.search_result_double_clicked)
        self.search_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.search_view.customContextMenuRequested.connect(self.show_search_context_menu)
        self.search_view.setRootIsDecorated(False)
        self.search_view.setSortingEnabled(True)
        self.search_view.selectionModel().selectionChanged.connect(self.on_search_selection_changed)
        
        # Drives view
        self.drives_view = DrivesView()
        self.drives_view.drive_clicked.connect(self.navigate_to)
        
        # Add views to stack
        self.views_stack.addWidget(self.file_view)
        self.views_stack.addWidget(self.detail_view)
        self.views_stack.addWidget(self.search_view)
        self.views_stack.addWidget(self.drives_view)
        content_frame_layout.addWidget(self.views_stack)
        
        # Add content frame to splitter
        self.main_splitter.addWidget(self.content_frame)
        
        # Preview pane
        self.preview_pane = PreviewPane()
        self.preview_pane.setObjectName("preview_pane")
        self.preview_pane.setMinimumWidth(300)
        self.main_splitter.addWidget(self.preview_pane)
        
        # Set initial splitter sizes
        self.main_splitter.setSizes([1, 0])
        self.preview_pane.setVisible(False)
        
        content_layout.addWidget(self.main_splitter)
        
        self.main_layout.addWidget(content_container)
        
    def _setup_action_bar(self):
        """Set up the bottom action bar."""
        self.action_bar = QWidget()
        self.action_bar.setObjectName("action_bar")
        action_bar_layout = QHBoxLayout(self.action_bar)
        action_bar_layout.setContentsMargins(16, 8, 16, 8)
        
        # New button with menu
        self.new_button = QPushButton("New")
        new_menu = QMenu(self)
        
        # Add folder creation option
        folder_action = new_menu.addAction("Folder")
        folder_action.triggered.connect(self.create_new_folder)
        
        # Add text file creation
        text_file_action = new_menu.addAction("Text Document")
        text_file_action.triggered.connect(lambda: self.create_new_file(".txt"))
        
        # Add common document types
        new_menu.addSeparator()
        word_doc_action = new_menu.addAction("Word Document")
        word_doc_action.triggered.connect(lambda: self.create_new_file(".docx"))
        
        excel_doc_action = new_menu.addAction("Excel Spreadsheet")
        excel_doc_action.triggered.connect(lambda: self.create_new_file(".xlsx"))
        
        # Add compressed archive options
        new_menu.addSeparator()
        zip_action = new_menu.addAction("Zip Archive")
        zip_action.triggered.connect(lambda: self.create_new_file(".zip"))
        
        self.new_button.setMenu(new_menu)
        action_bar_layout.addWidget(self.new_button)
        
        # File operation buttons
        self.copy_button = QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_selected_files)
        action_bar_layout.addWidget(self.copy_button)
        
        self.cut_button = QPushButton("Cut")
        self.cut_button.clicked.connect(self.cut_selected_files)
        action_bar_layout.addWidget(self.cut_button)
        
        self.paste_button = QPushButton("Paste")
        self.paste_button.clicked.connect(self.paste_files)
        action_bar_layout.addWidget(self.paste_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected_files)
        action_bar_layout.addWidget(self.delete_button)
        
        action_bar_layout.addStretch()
        
        # Status label
        self.status_label = QLabel()
        action_bar_layout.addWidget(self.status_label)
        
        self.main_layout.addWidget(self.action_bar)

    # -------------------------- Core Navigation Methods --------------------------
    
    def refresh_drives(self):
        """Refresh drives in both the drives view and navigation panel."""
        # Refresh the drives view if it's active
        if self.current_view == "drives":
            self.drives_view.load_drives()
        
        # Refresh the navigation panel's drive list
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
            self.settings_dialog.theme_changed.connect(self.apply_theme)
        
        self.settings_dialog.exec()
    
    def toggle_preview_panel(self):
        """Toggle the visibility of the preview panel."""
        if self.preview_pane.isVisible():
            # Hide preview panel
            self.preview_pane.setVisible(False)
            # Store the current sizes before hiding
            self.last_splitter_sizes = self.main_splitter.sizes()
            # Set the preview size to 0
            self.main_splitter.setSizes([1, 0])
            self.toggle_preview_button.setToolTip("Show Preview Panel")
        else:
            # Show preview panel
            self.preview_pane.setVisible(True)
            # If we have stored sizes, restore them
            if hasattr(self, 'last_splitter_sizes') and self.last_splitter_sizes[1] > 0:
                self.main_splitter.setSizes(self.last_splitter_sizes)
            else:
                # Default to a reasonable split
                self.main_splitter.setSizes([700, 300])
            self.toggle_preview_button.setToolTip("Hide Preview Panel")
                
            # Force the splitter to update
            self.main_splitter.update()
    
    def change_view_mode(self, index):
        """Change the view mode of the file explorer.
        
        Args:
            index: View mode index (0=Icons, 1=List, 2=Details)
        """
        # Update visible view
        if self.current_view == "files":
            if index == 0:  # Icons
                self.views_stack.setCurrentWidget(self.file_view)
                self.file_view.setViewMode(QListView.ViewMode.IconMode)
                self.file_view.setGridSize(QSize(120, 120))
                self.file_view.setIconSize(QSize(64, 64))
                self.file_view.setSpacing(10)
            elif index == 1:  # List
                self.views_stack.setCurrentWidget(self.file_view)
                self.file_view.setViewMode(QListView.ViewMode.ListMode)
                self.file_view.setGridSize(QSize())
                self.file_view.setIconSize(QSize(24, 24))
                self.file_view.setSpacing(2)
            elif index == 2:  # Details
                self.views_stack.setCurrentWidget(self.detail_view)
                
            # Update the model roots
            self.file_view.setRootIndex(self.file_model.index(self.current_path))
            self.detail_view.setRootIndex(self.file_model.index(self.current_path))
    
    def show_drives_view(self):
        """Switch to the drives view."""
        # Make sure search is cleared
        if self.is_searching:
            self.clear_search()
            
        # Set current view state
        self.current_view = "drives"
        
        # Update visible views
        self.views_stack.setCurrentWidget(self.drives_view)
        
        # Update title and breadcrumb
        self.setWindowTitle(f"This PC - Shadows File Explorer - {self.theme_manager.current_theme.capitalize()} Theme")
        self.breadcrumb_bar.set_path("This PC")
        
        # Update navigation panel selection
        self.navigation_panel.set_active_item("pc")
        
        # Refresh drives
        self.drives_view.load_drives()
        
        # Update status
        self.status_label.setText("Showing all drives")
    
    def on_file_selection_changed(self, selected, deselected):
        """Handle file selection changes to update preview.
        
        Args:
            selected: Selected items
            deselected: Deselected items
        """
        indexes = self.sender().selectedIndexes()
        if not indexes:
            self.preview_pane.clear_preview()
            return
            
        # For simplicity, just preview the first selected file
        file_index = indexes[0]
        path = self.file_model.filePath(file_index)
        
        if os.path.isfile(path):
            self.preview_pane.preview_file(path)
        else:
            self.preview_pane.clear_preview()
    
    def on_search_selection_changed(self, selected, deselected):
        """Handle search result selection changes to update preview.
        
        Args:
            selected: Selected items
            deselected: Deselected items
        """
        indexes = self.sender().selectedIndexes()
        if not indexes:
            self.preview_pane.clear_preview()
            return
            
        # Get file path from the first column (even if another column was clicked)
        file_index = indexes[0].siblingAtColumn(0)
        path = file_index.data(Qt.ItemDataRole.UserRole)
        
        if os.path.isfile(path):
            self.preview_pane.preview_file(path)
        else:
            self.preview_pane.clear_preview()
    
    def file_view_double_clicked(self, index):
        """Handle double-click on file or folder.
        
        Args:
            index: Model index of clicked item
        """
        path = self.file_model.filePath(index)
        
        if os.path.isdir(path):
            self.navigate_to(path)
        else:
            # Check file safety
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
            
            # Open file with default application
            QApplication.processEvents()  # Prevent UI freeze
            try:
                if platform.system() == "Windows":
                    os.startfile(path) 
                elif platform.system() == "Darwin":  # macOS
                    os.system(f"open '{path}'")
                else:  # Linux
                    os.system(f"xdg-open '{path}'")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")
    
    def search_result_double_clicked(self, index):
        """Handle double-click on search result.
        
        Args:
            index: Model index of clicked item
        """
        result_index = index.siblingAtColumn(0)  # Get the first column index
        file_path = result_index.data(Qt.ItemDataRole.UserRole)
        
        if os.path.exists(file_path):
            if os.path.isdir(file_path):
                self.clear_search()
                self.navigate_to(file_path)
            else:
                # Open file with default application
                QApplication.processEvents()  # Prevent UI freeze
                try:
                    if platform.system() == "Windows":
                        os.startfile(file_path) 
                    elif platform.system() == "Darwin":  # macOS
                        os.system(f"open '{file_path}'")
                    else:  # Linux
                        os.system(f"xdg-open '{file_path}'")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")
    
    def navigate_to(self, path):
        """Navigate to a directory with improved search cleanup.
        
        Args:
            path: Path to navigate to
        """
        # If we're in drives view and the path is "pc", don't change anything
        if path == "pc":
            self.show_drives_view()
            return
            
        # If searching, clear search first with full cleanup
        if self.is_searching:
            self.clear_search()
            
        # Handle root drive paths more carefully
        if platform.system() == "Windows" and len(path) <= 3 and path.endswith(":"): 
            # Add trailing slash for Windows drive letters
            path = path + "\\"
            
        # Verify path exists and is a directory
        if not os.path.exists(path) or not os.path.isdir(path):
            QMessageBox.warning(self, "Error", f"Path does not exist or is not a directory: {path}")
            # Don't attempt navigation if path doesn't exist
            return
            
        # Update history
        if self.current_path != path:
            if self.history_index < len(self.history) - 1:
                self.history = self.history[:self.history_index + 1]
            self.history.append(self.current_path)
            self.history_index = len(self.history) - 1
            
        self.current_path = path
        
        # Update file views
        self.file_view.setRootIndex(self.file_model.setRootPath(path))
        self.detail_view.setRootIndex(self.file_model.index(path))
        
        # Set current view state
        self.current_view = "files"
        
        # Select the active view based on view mode
        view_mode_index = self.view_mode_combo.currentIndex()
        if view_mode_index == 2:  # Details
            self.views_stack.setCurrentWidget(self.detail_view)
        else:
            self.views_stack.setCurrentWidget(self.file_view)
        
        # Update breadcrumb bar
        self.breadcrumb_bar.set_path(path)
        
        # Update window title
        theme_str = self.theme_manager.current_theme.capitalize()
        self.setWindowTitle(f"{os.path.basename(path)} - Shadows File Explorer - {theme_str} Theme")
        
        # Update navigation buttons
        self.back_button.setEnabled(self.history_index >= 0)
        self.forward_button.setEnabled(self.history_index < len(self.history) - 1)
        self.up_button.setEnabled(os.path.normpath(path) != os.path.normpath(QDir.rootPath()))
        
        # Update navigation panel selection
        self._update_navigation_selection(path)
        
        # Update status
        self.update_status()
        
    def _update_navigation_selection(self, path):
        """Update navigation panel selection based on path.
        
        Args:
            path: Current path
        """
        home_path = os.path.expanduser("~")
        
        # Check standard locations
        standard_locations = {
            "home": home_path,
            "desktop": os.path.join(home_path, "Desktop"),
            "documents": os.path.join(home_path, "Documents"),
            "downloads": os.path.join(home_path, "Downloads"),
            "pictures": os.path.join(home_path, "Pictures"),
            "music": os.path.join(home_path, "Music")
        }
        
        for location_id, location_path in standard_locations.items():
            if path == location_path:
                self.navigation_panel.set_active_item(location_id)
                return
                
        # Check if this is a drive path
        storage_drives = QStorageInfo.mountedVolumes()
        for drive in storage_drives:
            if drive.isReady() and path.startswith(drive.rootPath()):
                if path == drive.rootPath():
                    # Exact drive match
                    self.navigation_panel.set_active_item(f"drive_{path}")
                    return
    
    def navigate_back(self):
        """Navigate to previous location in history."""
        if self.is_searching:
            self.clear_search()
            
        if self.history_index > 0:
            self.history_index -= 1
            path = self.history[self.history_index]
            
            # Don't add to history again
            self.current_path = path
            
            # Update file views
            self.file_view.setRootIndex(self.file_model.setRootPath(path))
            self.detail_view.setRootIndex(self.file_model.index(path))
            
            # Update breadcrumb bar
            self.breadcrumb_bar.set_path(path)
            
            # Set current view state
            self.current_view = "files"
            
            # Select the active view based on view mode
            view_mode_index = self.view_mode_combo.currentIndex()
            if view_mode_index == 2:  # Details
                self.views_stack.setCurrentWidget(self.detail_view)
            else:
                self.views_stack.setCurrentWidget(self.file_view)
            
            # Update navigation buttons
            self.back_button.setEnabled(self.history_index > 0)
            self.forward_button.setEnabled(True)
            
            # Update navigation panel selection
            self._update_navigation_selection(path)
            
            # Update status
            self.update_status()
    
    def navigate_forward(self):
        """Navigate to next location in history."""
        if self.is_searching:
            self.clear_search()
            
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            path = self.history[self.history_index]
            
            # Don't add to history again
            self.current_path = path
            
            # Update file views
            self.file_view.setRootIndex(self.file_model.setRootPath(path))
            self.detail_view.setRootIndex(self.file_model.index(path))
            
            # Set current view state
            self.current_view = "files"
            
            # Select the active view based on view mode
            view_mode_index = self.view_mode_combo.currentIndex()
            if view_mode_index == 2:  # Details
                self.views_stack.setCurrentWidget(self.detail_view)
            else:
                self.views_stack.setCurrentWidget(self.file_view)
            
            # Update breadcrumb bar
            self.breadcrumb_bar.set_path(path)
            
            # Update navigation buttons
            self.back_button.setEnabled(True)
            self.forward_button.setEnabled(self.history_index < len(self.history) - 1)
            
            # Update navigation panel selection
            self._update_navigation_selection(path)
            
            # Update status
            self.update_status()
    
    def navigate_up(self):
        """Navigate to the parent directory."""
        if self.is_searching:
            self.clear_search()
            
        parent = os.path.dirname(self.current_path)
        if parent and parent != self.current_path:
            self.navigate_to(parent)
    
    def refresh_view(self):
        """Refresh the current view."""
        if self.is_searching:
            # Re-run the current search
            self.search_files()
        elif self.current_view == "drives":
            # Refresh drives view
            self.drives_view.load_drives()
        else:
            # Refresh file view
            self.file_model.setRootPath("")
            self.navigate_to(self.current_path)
    
    # -------------------------- Search Methods --------------------------
            
    def show_advanced_search(self):
        """Show the advanced search dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Search")
        dialog.setMinimumWidth(450)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(16)
        
        # Date modified group
        date_group = QGroupBox("Date Modified")
        date_layout = QVBoxLayout(date_group)
        
        date_any = QRadioButton("Any time")
        date_any.setChecked(True)
        
        date_after = QRadioButton("After:")
        date_after_edit = QDateEdit()
        date_after_edit.setCalendarPopup(True)
        date_after_edit.setDate(datetime.now().date())
        date_after_layout = QHBoxLayout()
        date_after_layout.addWidget(date_after)
        date_after_layout.addWidget(date_after_edit, 1)
        
        date_before = QRadioButton("Before:")
        date_before_edit = QDateEdit()
        date_before_edit.setCalendarPopup(True)
        date_before_edit.setDate(datetime.now().date())
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
        
        size_larger = QRadioButton("Larger than:")
        size_larger_value = QSpinBox()
        size_larger_value.setRange(0, 999999)
        size_larger_value.setValue(1)
        size_larger_unit = QComboBox()
        size_larger_unit.addItems(["KB", "MB", "GB"])
        size_larger_layout = QHBoxLayout()
        size_larger_layout.addWidget(size_larger)
        size_larger_layout.addWidget(size_larger_value)
        size_larger_layout.addWidget(size_larger_unit)
        
        size_smaller = QRadioButton("Smaller than:")
        size_smaller_value = QSpinBox()
        size_smaller_value.setRange(0, 999999)
        size_smaller_value.setValue(100)
        size_smaller_unit = QComboBox()
        size_smaller_unit.addItems(["KB", "MB", "GB"])
        size_smaller_layout = QHBoxLayout()
        size_smaller_layout.addWidget(size_smaller)
        size_smaller_layout.addWidget(size_smaller_value)
        size_smaller_layout.addWidget(size_smaller_unit)
        
        size_layout.addWidget(size_any)
        size_layout.addLayout(size_larger_layout)
        size_layout.addLayout(size_smaller_layout)
        
        # File type group
        type_group = QGroupBox("File Type")
        type_layout = QVBoxLayout(type_group)
        
        type_all = QRadioButton("All types")
        type_all.setChecked(True)
        type_documents = QRadioButton("Documents")
        type_pictures = QRadioButton("Pictures")
        type_music = QRadioButton("Music")
        type_videos = QRadioButton("Videos")
        type_folders = QRadioButton("Folders")
        
        type_layout.addWidget(type_all)
        type_layout.addWidget(type_documents)
        type_layout.addWidget(type_pictures)
        type_layout.addWidget(type_music)
        type_layout.addWidget(type_videos)
        type_layout.addWidget(type_folders)
        
        # Include subfolders
        include_subfolders = QCheckBox("Include subfolders")
        include_subfolders.setChecked(True)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_button = QPushButton("Search")
        ok_button.setProperty("class", "primary")
        ok_button.clicked.connect(dialog.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        
        # Add everything to main layout
        layout.addWidget(date_group)
        layout.addWidget(size_group)
        layout.addWidget(type_group)
        layout.addWidget(include_subfolders)
        layout.addLayout(button_layout)
        
        if dialog.exec():
            # Get search options
            self.search_options = {}
            self.search_options['include_subfolders'] = include_subfolders.isChecked()
            
            # Date filter
            if date_after.isChecked():
                self.search_options['date_filter'] = ('after', date_after_edit.date().toPython())
            elif date_before.isChecked():
                self.search_options['date_filter'] = ('before', date_before_edit.date().toPython())
            else:
                self.search_options['date_filter'] = None
                
            # Size filter
            if size_larger.isChecked():
                value = size_larger_value.value()
                unit = size_larger_unit.currentText()
                
                # Convert to bytes
                if unit == "KB":
                    min_bytes = value * 1024
                elif unit == "MB":
                    min_bytes = value * 1024 * 1024
                else:  # GB
                    min_bytes = value * 1024 * 1024 * 1024
                    
                self.search_options['size_filter'] = (min_bytes, None)
                
            elif size_smaller.isChecked():
                value = size_smaller_value.value()
                unit = size_smaller_unit.currentText()
                
                # Convert to bytes
                if unit == "KB":
                    max_bytes = value * 1024
                elif unit == "MB":
                    max_bytes = value * 1024 * 1024
                else:  # GB
                    max_bytes = value * 1024 * 1024 * 1024
                    
                self.search_options['size_filter'] = (None, max_bytes)
                
            else:
                self.search_options['size_filter'] = None
                
            # Type filter
            if type_documents.isChecked():
                self.search_options['type_filter'] = 'documents'
            elif type_pictures.isChecked():
                self.search_options['type_filter'] = 'images'
            elif type_music.isChecked():
                self.search_options['type_filter'] = 'music'
            elif type_videos.isChecked():
                self.search_options['type_filter'] = 'videos'
            elif type_folders.isChecked():
                self.search_options['type_filter'] = 'folders'
            else:
                self.search_options['type_filter'] = 'all'
                
            # Run the search if there's a search term
            if self.search_box.text().strip():
                self.search_files()
    
    def search_files(self):
        """Performs a search for files matching the search term."""
        search_term = self.search_box.text().strip()
        if not search_term:
            if self.is_searching:
                self.clear_search()
            return
            
        # Stop any existing search
        self.stop_search()
        
        # Update UI for search mode
        self.is_searching = True
        self.current_view = "search"
        self.search_results_model.clear_results()
        self.views_stack.setCurrentWidget(self.search_view)
        self.search_status_widget.setVisible(True)
        self.clear_search_button.setVisible(True)
        
        # Reset progress indicators
        self.search_progress.setValue(0)
        self.search_progress.setRange(0, 100)
        self.search_status_label.setText("Preparing search...")
        
        # Determine search locations
        search_locations = []
        
        # If we're in "This PC" view or search term starts with AllDrives:
        if self.current_view == "drives" or self.breadcrumb_bar.last_path == "This PC" or search_term.lower().startswith("alldrives:"):
            if search_term.lower().startswith("alldrives:"):
                search_term = search_term[10:].strip()  # Remove the prefix
                
            # Get all drives
            storage_drives = QStorageInfo.mountedVolumes()
            search_locations = [drive.rootPath() for drive in storage_drives if drive.isReady()]
            self.search_status_label.setText(f"Searching all drives for '{search_term}'...")
        else:
            # Default to current path
            search_locations = [self.current_path]
        
        # Disconnect previous connections to avoid duplicates
        try:
            self.file_searcher.finished.disconnect(self.search_completed)
            self.file_searcher.progress.disconnect(self.update_search_progress)
            self.file_searcher.found_item.disconnect(self.add_search_result)
            self.file_searcher.status_update.disconnect(self.update_search_message)
        except TypeError:
            # No connections exist yet, or they were already disconnected
            pass
        
        # Configure searcher with locations and term
        self.file_searcher.configure_search(search_locations, search_term, self.search_options)
        
        # Connect signals
        self.file_searcher.finished.connect(self.search_completed)
        self.file_searcher.progress.connect(self.update_search_progress)
        self.file_searcher.found_item.connect(self.add_search_result)
        self.file_searcher.status_update.connect(self.update_search_message)
        
        # Start the search
        self.search_start_time = time.time()
        self.timer.start(100)  # Update status every 100ms
        self.file_searcher.start_search()
        
        # Update status
        options_text = ""
        if self.search_options:
            if not self.search_options.get('include_subfolders', True):
                options_text = " (current folder only)"
        
        search_scope = "all drives" if len(search_locations) > 1 else self.current_path
        self.status_label.setText(f"Searching for '{search_term}' in {search_scope}{options_text}")

    def stop_search(self):
        """Stop the search operation."""
        if hasattr(self, 'file_searcher') and self.file_searcher.is_running:
            self.file_searcher.stop()
            self.timer.stop()

    def clear_search(self):
        """Clears search results and returns to normal directory view."""
        if not self.is_searching:
            return
            
        # Stop any active search
        self.stop_search()
        
        # Reset UI
        self.is_searching = False
        self.current_view = "files"  # Restore view state
        
        # Update view
        view_mode_index = self.view_mode_combo.currentIndex()
        if view_mode_index == 2:  # Details
            self.views_stack.setCurrentWidget(self.detail_view)
        else:
            self.views_stack.setCurrentWidget(self.file_view)
            
        self.search_status_widget.setVisible(False)
        self.clear_search_button.setVisible(False)
        self.search_box.clear()
        
        # Update status
        self.update_status()

    def update_search_message(self, message):
        """Update the search status message.
        
        Args:
            message: Status message
        """
        self.search_status_label.setText(message)

    def update_search_progress(self, current, total):
        """Updates the progress indicator during search.
        
        Args:
            current: Current progress value
            total: Total progress value
        """
        if total <= 0:
            # Indeterminate progress - use a busy indicator
            if not hasattr(self, '_progress_value'):
                self._progress_value = 0
            
            self._progress_value = (self._progress_value + 5) % 100
            self.search_progress.setValue(self._progress_value)
        else:
            # Determinate progress
            percent = min(100, int((current / total) * 100))
            self.search_progress.setValue(percent)

    def update_search_status(self):
        """Updates the search status text with elapsed time."""
        if not self.is_searching:
            return
            
        elapsed = time.time() - self.search_start_time
        result_count = self.search_results_model.rowCount()
        
        if elapsed < 60:
            time_text = f"{elapsed:.1f} seconds"
        else:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            time_text = f"{minutes}:{seconds:02d} minutes"
            
        self.search_status_label.setText(f"Found {result_count} items in {time_text}")

    def add_search_result(self, result):
        """Adds a found item to the search results.
        
        Args:
            result: SearchResult object
        """
        self.search_results_model.add_result(result)
        
        # Update the result count
        result_count = self.search_results_model.rowCount()
        
        # Periodically update status bar
        if result_count % 10 == 0:
            self.status_label.setText(f"Found {result_count} matches so far...")

    def search_completed(self):
        """Called when the search operation is complete."""
        self.timer.stop()
        self.search_status_widget.setVisible(True)
        
        result_count = self.search_results_model.rowCount()
        elapsed = time.time() - self.search_start_time
        
        if elapsed < 60:
            time_text = f"{elapsed:.1f} seconds"
        else:
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            time_text = f"{minutes}:{seconds:02d} minutes"
        
        self.search_status_label.setText(f"Found {result_count} items in {time_text}")
        self.search_progress.setValue(100)  # Set to 100% when done
        
        self.status_label.setText(f"Search complete: {result_count} items found")
    
    # -------------------------- File Operations --------------------------
    
    def create_new_folder(self):
        """Create a new folder in the current directory."""
        if self.is_searching or self.current_view == "drives":
            # Can't create folder in search results or drives view
            QMessageBox.information(self, "Cannot Create Folder", 
                                   "Please navigate to a folder before creating a new folder.")
            return
            
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Enter folder name:")
        if ok and folder_name:
            new_folder_path = os.path.join(self.current_path, folder_name)
            try:
                os.makedirs(new_folder_path, exist_ok=False)
                self.refresh_view()
            except FileExistsError:
                QMessageBox.warning(self, "Error", f"A folder named '{folder_name}' already exists.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder: {str(e)}")
    
    def create_new_file(self, extension):
        """Create a new file with the given extension.
        
        Args:
            extension: File extension (e.g., ".txt")
        """
        if self.is_searching or self.current_view == "drives":
            QMessageBox.information(self, "Cannot Create File", 
                                "Please navigate to a folder before creating a new file.")
            return
            
        default_name = f"New File{extension}"
        file_name, ok = QInputDialog.getText(self, f"New {extension[1:].upper()} File", 
                                        "Enter file name:", text=default_name)
        
        if ok and file_name:
            # Add extension if not provided
            if not file_name.lower().endswith(extension.lower()):
                file_name += extension
                
            new_file_path = os.path.join(self.current_path, file_name)
            
            try:
                # Check if file already exists
                if os.path.exists(new_file_path):
                    QMessageBox.warning(self, "Error", f"A file named '{file_name}' already exists.")
                    return
                    
                # Create empty file
                with open(new_file_path, 'w') as f:
                    # For certain file types, add basic template content
                    if extension == ".html":
                        f.write("<!DOCTYPE html>\n<html>\n<head>\n\t<title>New Page</title>\n</head>\n<body>\n\t<h1>Hello World</h1>\n</body>\n</html>")
                    elif extension == ".py":
                        f.write("#!/usr/bin/env python\n\n\ndef main():\n\tprint('Hello World')\n\n\nif __name__ == '__main__':\n\tmain()")
                    elif extension == ".md":
                        f.write("# New Document\n\nEnter your text here.")
                        
                self.refresh_view()
                self.status_label.setText(f"Created new file: {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create file: {str(e)}")
                
    def add_operation_to_history(self, op_type, source, target=None):
        """Add an operation to the history for potential undo.
        
        Args:
            op_type: Operation type ('copy', 'move', 'delete', 'rename')
            source: Source path
            target: Target path (if applicable)
        """
        self.operation_history.append({
            'type': op_type,
            'source': source,
            'target': target,
            'timestamp': time.time()
        })
        
        # Enable undo button
        self.undo_button.setEnabled(True)
        
        # Limit history size
        if len(self.operation_history) > 20:
            self.operation_history.pop(0)
            
    def undo_last_operation(self):
        """Undo the last file operation if possible."""
        if not self.operation_history:
            self.undo_button.setEnabled(False)
            return
            
        # Get the last operation
        op = self.operation_history.pop()
        
        # Set undo button state
        self.undo_button.setEnabled(bool(self.operation_history))
        
        # Perform the undo
        try:
            if op['type'] == 'copy':
                # Remove the copied file
                if op['target'] and os.path.exists(op['target']):
                    if os.path.isdir(op['target']):
                        shutil.rmtree(op['target'])
                    else:
                        os.remove(op['target'])
                    self.status_label.setText("Undid copy operation")
                    
            elif op['type'] == 'move':
                # Move back
                if op['target'] and os.path.exists(op['target']):
                    shutil.move(op['target'], op['source'])
                    self.status_label.setText("Undid move operation")
                    
            elif op['type'] == 'delete':
                # Can't undo unless we have the original file backed up
                QMessageBox.information(self, "Cannot Undo", 
                                    "Deletion cannot be undone. Files may be available in the Recycle Bin.")
                
            elif op['type'] == 'rename':
                # Rename back
                if op['target'] and os.path.exists(op['target']):
                    os.rename(op['target'], op['source'])
                    self.status_label.setText("Undid rename operation")
                    
            # Refresh view
            self.refresh_view()
            
        except Exception as e:
            QMessageBox.warning(self, "Undo Failed", f"Could not undo operation: {str(e)}")