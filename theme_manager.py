"""
Theme management module for Shadows File Explorer.

This module provides the ThemeManager class which handles application themes 
including light, dark, and retro modes.
"""
from PyQt6.QtCore import pyqtSignal, QObject, QSettings


class ThemeManager(QObject):
    """Manages application themes including light, dark, and retro modes.
    
    The ThemeManager provides functionality to switch between different visual
    themes and retrieve the appropriate stylesheets.
    
    Signals:
        theme_changed: Emitted when the theme is changed
    """
    
    theme_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the theme manager.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self.current_theme = "dark"  # Default to dark theme
        self.themes = {
            "light": self._get_light_theme,
            "dark": self._get_dark_theme,
            "retro": self._get_retro_theme,
            "system": self._get_system_theme
        }
        
        # Load saved theme preference
        self.settings = QSettings("ShadowsExplorer", "Preferences")
        saved_theme = self.settings.value("theme", "dark")  # Default to dark
        if saved_theme in self.themes:
            self.current_theme = saved_theme
    
    def get_theme_stylesheet(self, theme_name=None):
        """Get the stylesheet for the specified theme.
        
        Args:
            theme_name: Name of the theme. If None, uses current theme.
            
        Returns:
            str: CSS stylesheet for the theme
        """
        if theme_name is None:
            theme_name = self.current_theme
            
        if theme_name in self.themes:
            return self.themes[theme_name]()
        return self._get_system_theme()
    
    def set_theme(self, theme_name):
        """Set the current theme.
        
        Args:
            theme_name: Name of the theme to set
        """
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.settings.setValue("theme", theme_name)
            self.theme_changed.emit(theme_name)
    
    def _get_system_theme(self):
        """Determine system theme (light or dark) and return the appropriate stylesheet.
        
        Returns:
            str: CSS stylesheet based on system theme
        """
        # In a real implementation, would detect the system theme
        # For now, default to dark theme
        return self._get_dark_theme()
    
    def _get_light_theme(self):
        """Get the light theme stylesheet.
        
        Returns:
            str: CSS stylesheet for light theme
        """
        return """
            /* Light Theme */
            QMainWindow, QWidget {
                background-color: #f5f5f5;
                color: #333333;
            }
            
            QSplitter::handle {
                background-color: #e0e0e0;
            }
            
            /* App Bar */
            QWidget#appbar {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                max-height: 30px;
            }
            
            /* Side Panel */
            QFrame#sidebar {
                background-color: #ffffff;
                border-right: 1px solid #e0e0e0;
            }
            
            /* Navigation Buttons */
            QPushButton.nav-button {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #555555;
                text-align: left;
                padding: 8px 16px;
            }
            
            QPushButton.nav-button:hover {
                background-color: #f0f0f0;
            }
            
            QPushButton.nav-button:pressed {
                background-color: #e5e5e5;
            }
            
            QPushButton.nav-button-active {
                background-color: #f0f0f0;
                font-weight: bold;
                color: #2979ff;
            }
            
            /* Main Content */
            QFrame#content {
                background-color: #ffffff;
                border-radius: 8px;
            }
            
            /* File Views */
            QListView, QTreeView {
                background-color: #ffffff;
                border: none;
                outline: none;
                border-radius: 6px;
            }
            
            QListView::item, QTreeView::item {
                padding: 4px;
                border-radius: 4px;
            }
            
            QListView::item:hover, QTreeView::item:hover {
                background-color: #f5f5f5;
            }
            
            QListView::item:selected, QTreeView::item:selected {
                background-color: #e3f2fd;
                color: #2979ff;
            }
            
            /* Headers */
            QHeaderView::section {
                background-color: #f5f5f5;
                color: #555555;
                padding: 6px;
                border: none;
                border-right: 1px solid #e0e0e0;
                font-weight: bold;
            }
            
            /* Search Box */
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 20px;
                padding: 8px 16px;
                selection-background-color: #2979ff;
                selection-color: white;
                max-height: 24px;
            }
            
            QLineEdit:focus {
                border: 1px solid #2979ff;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 16px;
                color: #333333;
            }
            
            QPushButton:hover {
                background-color: #e9e9e9;
                border: 1px solid #d0d0d0;
            }
            
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            
            QPushButton.primary {
                background-color: #2979ff;
                color: white;
                border: none;
            }
            
            QPushButton.primary:hover {
                background-color: #2196f3;
            }
            
            QPushButton.primary:pressed {
                background-color: #1e88e5;
            }
            
            /* Tool Buttons */
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 1px;
                margin: 0px;
                color: #555555;
            }
            
            QToolButton:hover {
                background-color: #f0f0f0;
            }
            
            QToolButton:pressed {
                background-color: #e0e0e0;
            }
            
            /* Scroll Bars */
            QScrollBar:vertical {
                background: #f5f5f5;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                min-height: 20px;
                border-radius: 5px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #b0b0b0;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background: #f5f5f5;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background: #d0d0d0;
                min-width: 20px;
                border-radius: 5px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background: #b0b0b0;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border: none;
                background-color: #ffffff;
                border-radius: 0px 6px 6px 6px;
            }
            
            QTabBar::tab {
                background-color: #f5f5f5;
                color: #555555;
                padding: 8px 16px;
                border: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2979ff;
                border-bottom: 2px solid #2979ff;
            }
            
            QTabBar::tab:hover {
                background-color: #e9e9e9;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #ffffff;
                color: #555555;
                border-top: 1px solid #e0e0e0;
            }
            
            /* Drive Items */
            DriveItemWidget {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
            }
            
            DriveItemWidget:hover {
                background-color: #f9f9f9;
                border: 1px solid #d0d0d0;
            }
            
            /* Progress Bar */
            QProgressBar {
                border: none;
                background-color: #f0f0f0;
                border-radius: 6px;
                text-align: center;
                color: #555555;
            }
            
            QProgressBar::chunk {
                background-color: #2979ff;
                border-radius: 6px;
            }
            
            /* Menu */
            QMenu {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                padding: 5px 0px;
            }
            
            QMenu::item {
                padding: 6px 30px 6px 20px;
                border-radius: 3px;
                margin: 2px 6px;
            }
            
            QMenu::item:selected {
                background-color: #f0f0f0;
                color: #2979ff;
            }
            
            /* Combo Box */
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 6em;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 20px;
                border-left: none;
            }
            
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 0px 0px 4px 4px;
                selection-background-color: #f0f0f0;
                selection-color: #2979ff;
            }
        """
    
    def _get_dark_theme(self):
        """Get the dark theme stylesheet.
        
        Returns:
            str: CSS stylesheet for dark theme
        """
        return """
            /* Dark Theme */
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                margin: 0;
                padding: 0;
            }
            
            /* Splitter handles - make them more visible */
            QSplitter::handle {
                background-color: #555555;
                width: 1px;
            }
            
            /* Side Panel - with clear right border */
            QFrame#sidebar {
                background-color: #1e1e1e;
                border-right: 2px solid #555555;
            }
            
            /* Main Content - clean without borders */
            QFrame#content {
                background-color: #1e1e1e;
                border-radius: 0px;
            }
    
            
            /* Preview Pane - subtle background difference */
            PreviewPane {
                background-color: #252525;
            }
            
            /* Bottom action bar */
            .action_bar {
                background-color: #252525;
                border-top: 1px solid #383838;
            }
            
            /* Navigation Buttons */
            QPushButton.nav-button {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                color: #b0b0b0;
                text-align: left;
                padding: 8px 16px;
            }
            
            QPushButton.nav-button:hover {
                background-color: #303030;
            }
            
            QPushButton.nav-button:pressed {
                background-color: #383838;
            }
            
            QPushButton.nav-button-active {
                background-color: #303030;
                font-weight: bold;
                color: #4fc3f7;
            }
            
            /* Make active file selection more visible */
            QListView::item:selected, QTreeView::item:selected {
                background-color: #0c2d48;
                color: #4fc3f7;
            }
            
            /* Main Content */
            QFrame#content {
                background-color: #1e1e1e;
                border-radius: 8px;
            }
            
            /* File Views */
            QListView, QTreeView {
                background-color: #1e1e1e;
                border: none;
                outline: none;
                border-radius: 6px;
                color: #e0e0e0;
            }
            
            QListView::item, QTreeView::item {
                padding: 4px;
                border-radius: 4px;
            }
            
            QListView::item:hover, QTreeView::item:hover {
                background-color: #303030;
            }
            
            QListView::item:selected, QTreeView::item:selected {
                background-color: #0c2d48;
                color: #4fc3f7;
            }
            
            /* Headers */
            QHeaderView::section {
                background-color: #252525;
                color: #b0b0b0;
                padding: 6px;
                border: none;
                border-right: 1px solid #303030;
                font-weight: bold;
            }
            
            /* Search Box */
            QLineEdit {
                background-color: #252525;
                border: 1px solid #383838;
                border-radius: 20px;
                padding: 8px 16px;
                color: #e0e0e0;
                selection-background-color: #0c2d48;
                selection-color: #4fc3f7;
                max-height: 24px;
            }
            
            QLineEdit:focus {
                border: 1px solid #4fc3f7;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #252525;
                border: 1px solid #383838;
                border-radius: 4px;
                padding: 8px 16px;
                color: #e0e0e0;
            }
            
            QPushButton:hover {
                background-color: #303030;
                border: 1px solid #454545;
            }
            
            QPushButton:pressed {
                background-color: #383838;
            }
            
            QPushButton.primary {
                background-color: #0277bd;
                color: white;
                border: none;
            }
            
            QPushButton.primary:hover {
                background-color: #0288d1;
            }
            
            QPushButton.primary:pressed {
                background-color: #026fa9;
            }
            
            /* Tool Buttons */
            QToolButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                padding: 1px;
                margin: 0px;
                color: #b0b0b0;
            }
            
            QToolButton:hover {
                background-color: #303030;
            }
            
            QToolButton:pressed {
                background-color: #383838;
            }
            
            /* Scroll Bars */
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: #454545;
                min-height: 20px;
                border-radius: 5px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #555555;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background: #1e1e1e;
                height: 10px;
                margin: 0px;
            }
            
            QScrollBar::handle:horizontal {
                background: #454545;
                min-width: 20px;
                border-radius: 5px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background: #555555;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
                border-radius: 0px 6px 6px 6px;
            }
            
            QTabBar::tab {
                background-color: #252525;
                color: #b0b0b0;
                padding: 8px 16px;
                border: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #4fc3f7;
                border-bottom: 2px solid #4fc3f7;
            }
            
            QTabBar::tab:hover {
                background-color: #303030;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #1e1e1e;
                color: #b0b0b0;
                border-top: 1px solid #303030;
            }
            
            /* Drive Items */
            DriveItemWidget {
                background-color: #252525;
                border-radius: 8px;
                border: 1px solid #383838;
            }
            
            DriveItemWidget:hover {
                background-color: #303030;
                border: 1px solid #454545;
            }
            
            /* Progress Bar */
            QProgressBar {
                border: none;
                background-color: #252525;
                border-radius: 6px;
                text-align: center;
                color: #b0b0b0;
            }
            
            QProgressBar::chunk {
                background-color: #0277bd;
                border-radius: 6px;
            }
            
            /* Menu */
            QMenu {
                background-color: #252525;
                border: 1px solid #383838;
                border-radius: 6px;
                padding: 5px 0px;
            }
            
            QMenu::item {
                padding: 6px 30px 6px 20px;
                border-radius: 3px;
                margin: 2px 6px;
            }
            
            QMenu::item:selected {
                background-color: #303030;
                color: #4fc3f7;
            }
            
            /* Combo Box */
            QComboBox {
                background-color: #252525;
                border: 1px solid #383838;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 6em;
                color: #e0e0e0;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 20px;
                border-left: none;
            }
            
            QComboBox QAbstractItemView {
                background-color: #252525;
                border: 1px solid #383838;
                border-radius: 0px 0px 4px 4px;
                selection-background-color: #303030;
                selection-color: #4fc3f7;
            }
            
            /* Breadcrumb styling */
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """
    
    def _get_retro_theme(self):
        """Get the retro theme stylesheet (inspired by Windows 98).
        
        Returns:
            str: CSS stylesheet for retro theme
        """
        return """
            /* Retro Theme (Windows 98 inspired) */
            QMainWindow, QWidget {
                background-color: #c0c0c0;
                color: #000000;
                font-family: "MS Sans Serif", Arial, sans-serif;
                font-size: 10pt;
            }
            
            QSplitter::handle {
                background-color: #c0c0c0;
                border: 1px solid #808080;
            }
            
            /* App Bar */
            QWidget#appbar {
                background-color: #c0c0c0;
                border-bottom: 2px solid #808080;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                max-height: 30px;
            }
            
            /* Side Panel */
            QFrame#sidebar {
                background-color: #c0c0c0;
                border-right: 2px solid #808080;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-bottom: 2px solid #808080;
            }
            
            /* Navigation Buttons */
            QPushButton.nav-button {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                color: #000000;
                text-align: left;
                padding: 6px 12px;
                border-radius: 0px;
            }
            
            QPushButton.nav-button:hover {
                background-color: #d4d0c8;
            }
            
            QPushButton.nav-button:pressed {
                background-color: #c0c0c0;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
            }
            
            QPushButton.nav-button-active {
                background-color: #d4d0c8;
                font-weight: bold;
                color: #000000;
            }
            
            /* Main Content */
            QFrame#content {
                background-color: #ffffff;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            /* File Views */
            QListView, QTreeView {
                background-color: #ffffff;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                outline: none;
            }
            
            QListView::item, QTreeView::item {
                padding: 2px;
            }
            
            QListView::item:hover, QTreeView::item:hover {
                background-color: #f0f0f0;
            }
            
            QListView::item:selected, QTreeView::item:selected {
                background-color: #0a246a;
                color: #ffffff;
            }
            
            /* Headers */
            QHeaderView::section {
                background-color: #c0c0c0;
                color: #000000;
                padding: 4px;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            /* Search Box */
            QLineEdit {
                background-color: #ffffff;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                padding: 4px 8px;
                selection-background-color: #0a246a;
                selection-color: white;
                border-radius: 0px;
                max-height: 24px;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 6px 12px;
                color: #000000;
                border-radius: 0px;
            }
            
            QPushButton:hover {
                background-color: #d4d0c8;
            }
            
            QPushButton:pressed {
                background-color: #c0c0c0;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
            }
            
            QPushButton.primary {
                background-color: #0a246a;
                color: white;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            QPushButton.primary:hover {
                background-color: #215dc6;
            }
            
            QPushButton.primary:pressed {
                background-color: #0a246a;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
            }
            
            /* Tool Buttons */
            QToolButton {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 1px;
                margin: 0px;
                color: #000000;
                border-radius: 0px;
            }
            
            QToolButton:hover {
                background-color: #d4d0c8;
            }
            
            QToolButton:pressed {
                background-color: #c0c0c0;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
            }
            
            /* Scroll Bars */
            QScrollBar:vertical {
                background: #c0c0c0;
                width: 16px;
                margin: 16px 0 16px 0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            QScrollBar::add-line:vertical {
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                background: #c0c0c0;
                height: 16px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
            }
            
            QScrollBar::sub-line:vertical {
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                background: #c0c0c0;
                height: 16px;
                subcontrol-position: top;
                subcontrol-origin: margin;
            }
            
            QScrollBar:horizontal {
                background: #c0c0c0;
                height: 16px;
                margin: 0 16px 0 16px;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                min-width: 20px;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            QScrollBar::add-line:horizontal {
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                background: #c0c0c0;
                width: 16px;
                subcontrol-position: right;
                subcontrol-origin: margin;
            }
            
            QScrollBar::sub-line:horizontal {
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                background: #c0c0c0;
                width: 16px;
                subcontrol-position: left;
                subcontrol-origin: margin;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                background-color: #c0c0c0;
            }
            
            QTabBar::tab {
                background-color: #c0c0c0;
                color: #000000;
                padding: 4px 8px;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: none;
                margin-right: 2px;
            }
            
            QTabBar::tab:selected {
                background-color: #d4d0c8;
                border-bottom: none;
            }
            
            QTabBar::tab:hover {
                background-color: #d4d0c8;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #c0c0c0;
                color: #000000;
                border-top: 2px solid #808080;
            }
            
            /* Drive Items */
            DriveItemWidget {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
            }
            
            DriveItemWidget:hover {
                background-color: #d4d0c8;
            }
            
            /* Progress Bar */
            QProgressBar {
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                background-color: #ffffff;
                text-align: center;
                color: #000000;
            }
            
            QProgressBar::chunk {
                background-color: #0a246a;
            }
            
            /* Menu */
            QMenu {
                background-color: #c0c0c0;
                border-top: 2px solid #ffffff;
                border-left: 2px solid #ffffff;
                border-right: 2px solid #808080;
                border-bottom: 2px solid #808080;
                padding: 2px 0px;
            }
            
            QMenu::item {
                padding: 4px 20px 4px 20px;
            }
            
            QMenu::item:selected {
                background-color: #0a246a;
                color: #ffffff;
            }
            
            /* Combo Box */
            QComboBox {
                background-color: #ffffff;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                padding: 4px 8px;
                min-width: 6em;
                color: #000000;
            }
            
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                width: 16px;
                border-left: none;
            }
            
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border-top: 2px solid #808080;
                border-left: 2px solid #808080;
                border-right: 2px solid #ffffff;
                border-bottom: 2px solid #ffffff;
                selection-background-color: #0a246a;
                selection-color: #ffffff;
            }
        """