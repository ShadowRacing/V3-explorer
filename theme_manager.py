"""
Theme management module for Shadows File Explorer.

This module provides the ThemeManager class which handles application themes.
Every theme is a palette of colors filled into one shared stylesheet, so all
themes style the same widgets consistently.
"""
from PyQt6.QtCore import pyqtSignal, QObject, QSettings, Qt
from PyQt6.QtGui import QGuiApplication

PALETTES = {
    "dark": {
        "font": '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif',
        "bg": "#1b1d21", "surface": "#202328", "raised": "#2a2e35", "input": "#25282e",
        "border": "#33373e", "text": "#e6e8eb", "muted": "#9aa1ab", "icon": "#c9ced6",
        "accent": "#4c9aff", "on_accent": "#ffffff", "hover": "rgba(255, 255, 255, 0.06)",
        "pressed": "rgba(255, 255, 255, 0.10)", "selected": "rgba(76, 154, 255, 0.24)",
        "selected_text": "#ffffff", "scroll": "#454a52", "radius": "6px", "small_radius": "4px",
        "button_border": "1px solid #33373e", "pressed_border": "1px solid #4c9aff",
        "checked": "rgba(76, 154, 255, 0.24)", "view_bg": "#1b1d21",
        "dark": True,
    },
    "light": {
        "font": '"Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif',
        "bg": "#ffffff", "surface": "#f5f6f8", "raised": "#ffffff", "input": "#ffffff",
        "border": "#dfe2e6", "text": "#1f2328", "muted": "#656d76", "icon": "#3d444d",
        "accent": "#0a66d8", "on_accent": "#ffffff", "hover": "rgba(0, 0, 0, 0.05)",
        "pressed": "rgba(0, 0, 0, 0.09)", "selected": "rgba(10, 102, 216, 0.14)",
        "selected_text": "#1f2328", "scroll": "#c4c9d0", "radius": "6px", "small_radius": "4px",
        "button_border": "1px solid #dfe2e6", "pressed_border": "1px solid #0a66d8",
        "checked": "rgba(10, 102, 216, 0.14)", "view_bg": "#ffffff",
        "dark": False,
    },
    # Windows 98: grey chrome, navy selection, bevelled borders, square corners
    "retro": {
        "font": '"MS Sans Serif", "Microsoft Sans Serif", Tahoma, Arial, sans-serif',
        "bg": "#c0c0c0", "surface": "#c0c0c0", "raised": "#c0c0c0", "input": "#ffffff",
        "border": "#808080", "text": "#000000", "muted": "#404040", "icon": "#000000",
        "accent": "#000080", "on_accent": "#ffffff", "hover": "rgba(0, 0, 128, 0.10)",
        "pressed": "rgba(0, 0, 0, 0.12)", "selected": "#000080",
        "selected_text": "#ffffff", "scroll": "#a0a0a0", "radius": "0px", "small_radius": "0px",
        "button_border": "2px outset #dfdfdf", "pressed_border": "2px inset #dfdfdf",
        "checked": "#dfdfdf", "view_bg": "#ffffff",
        "dark": False,
    },
}

STYLESHEET = """
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: {font};
    font-size: 13px;
}}
QToolTip {{
    background-color: {raised}; color: {text};
    border: 1px solid {border}; padding: 4px 6px;
}}

/* ---- Bars ---- */
QWidget#appbar, QWidget#tab_row {{ background-color: {surface}; }}
QWidget#appbar {{ border-bottom: 1px solid {border}; }}
QWidget#tab_row {{ border-bottom: 1px solid {border}; }}
QWidget#action_bar {{ background-color: {surface}; border-top: 1px solid {border}; }}
QLabel#app_title {{ font-weight: 600; font-size: 15px; background: transparent; }}
QLabel#status_label {{ color: {muted}; background: transparent; }}
QWidget#view_controls {{ background-color: {bg}; }}

/* ---- Sidebar ---- */
QFrame#sidebar, QFrame#sidebar QScrollArea, NavigationPanel {{
    background-color: {surface};
    border: none;
}}
QFrame#sidebar {{ border-right: 1px solid {border}; }}
QLabel#nav_header {{
    color: {muted}; font-size: 11px; font-weight: 600;
    padding: 0 0 2px 12px; background: transparent;
}}
QWidget#nav_container {{ background: transparent; }}
NavItem {{ background: transparent; border-radius: {radius}; }}
NavItem QLabel {{ background: transparent; }}
NavItem:hover {{ background-color: {hover}; }}
NavItem[active="true"] {{ background-color: {selected}; }}
NavItem[active="true"] QLabel {{ color: {selected_text}; }}
NavItem[parentActive="true"] {{ background-color: {hover}; }}
NavItem[dropTarget="true"] {{ background-color: {selected}; border: 1px dashed {accent}; }}

/* ---- Content ---- */
QFrame#content, PreviewPane {{ background-color: {bg}; }}
PreviewPane {{ border-left: 1px solid {border}; }}
QLabel#preview_title {{ font-weight: 600; font-size: 14px; }}
QLabel#preview_name {{ font-weight: 600; font-size: 14px; }}
QLabel#preview_message {{ color: {muted}; padding: 20px; }}
QSplitter::handle {{ background-color: {border}; width: 1px; }}

QListView, QTreeView {{
    background-color: {view_bg};
    border: none;
    outline: none;
    selection-background-color: {selected};
    selection-color: {selected_text};
}}
QListView::item, QTreeView::item {{ padding: 3px; border-radius: {small_radius}; color: {text}; }}
QListView::item:hover, QTreeView::item:hover {{ background-color: {hover}; }}
QListView::item:selected, QTreeView::item:selected {{
    background-color: {selected}; color: {selected_text};
}}
QHeaderView {{ background-color: {view_bg}; border: none; }}
QHeaderView::section {{
    background-color: {view_bg}; color: {muted};
    padding: 6px 8px; border: none;
    border-bottom: 1px solid {border}; border-right: 1px solid {border};
    font-weight: 600;
}}
QHeaderView::section:hover {{ background-color: {hover}; }}

/* ---- Breadcrumbs ---- */
FixedBreadcrumbBar, FixedBreadcrumbBar QScrollArea, FixedBreadcrumbBar QWidget {{
    background-color: {input};
}}
FixedBreadcrumbBar {{ border: {button_border}; border-radius: {radius}; }}
QPushButton#crumb {{
    background: transparent; border: none; border-radius: {small_radius};
    padding: 3px 6px; color: {text};
}}
QPushButton#crumb:hover {{ background-color: {hover}; }}
QPushButton#crumb:pressed {{ background-color: {pressed}; }}
QPushButton#crumb_current {{
    background: transparent; border: none; padding: 3px 6px;
    color: {text}; font-weight: 600;
}}
QLabel#crumb_separator {{ background: transparent; color: {muted}; }}

/* ---- Inputs ---- */
QLineEdit, QSpinBox, QDateEdit, QComboBox {{
    background-color: {input};
    border: {button_border};
    border-radius: {radius};
    padding: 4px 8px;
    min-height: 20px;
    selection-background-color: {accent};
    selection-color: {on_accent};
}}
QLineEdit:focus, QSpinBox:focus, QDateEdit:focus, QComboBox:focus {{ border: 1px solid {accent}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {raised}; border: 1px solid {border};
    selection-background-color: {selected}; selection-color: {selected_text};
}}
QTextEdit {{
    background-color: {input}; border: 1px solid {border};
    border-radius: {radius}; padding: 6px;
}}
QCheckBox, QRadioButton {{ background: transparent; spacing: 6px; }}
QGroupBox {{
    border: 1px solid {border}; border-radius: {radius};
    margin-top: 10px; padding: 10px 8px 8px 8px;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {muted}; }}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {raised};
    border: {button_border};
    border-radius: {radius};
    padding: 5px 12px;
}}
QPushButton:hover {{ background-color: {hover}; }}
QPushButton:pressed {{ background-color: {pressed}; border: {pressed_border}; }}
QPushButton:disabled {{ color: {muted}; }}
QPushButton[class="primary"] {{
    background-color: {accent}; color: {on_accent}; border: 1px solid {accent};
}}
QPushButton::menu-indicator {{ width: 0px; }}
QToolButton {{
    background: transparent; border: 1px solid transparent;
    border-radius: {radius}; padding: 3px;
}}
QToolButton:hover {{ background-color: {hover}; }}
QToolButton:pressed {{ background-color: {pressed}; }}
QToolButton:checked {{ background-color: {checked}; border: {pressed_border}; }}
QToolButton:disabled {{ color: {muted}; }}

/* ---- Tabs ---- */
QTabBar {{ background: transparent; qproperty-drawBase: 0; }}
QTabBar::tab {{
    background: transparent; color: {muted};
    padding: 6px 10px 6px 12px; margin-right: 2px;
    border: 1px solid transparent; border-bottom: none;
    border-top-left-radius: {radius}; border-top-right-radius: {radius};
    min-width: 80px; max-width: 220px;
}}
QTabBar::tab:hover {{ background-color: {hover}; color: {text}; }}
QTabBar::tab:selected {{
    background-color: {bg}; color: {text};
    border: 1px solid {border}; border-bottom: 2px solid {accent};
}}
QTabBar::scroller {{ width: 24px; }}

/* ---- Menus ---- */
QMenu {{
    background-color: {raised}; border: 1px solid {border};
    border-radius: {radius}; padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 10px; border-radius: {small_radius}; background: transparent; }}
QMenu::item:selected {{ background-color: {selected}; color: {selected_text}; }}
QMenu::item:disabled {{ color: {muted}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 4px 6px; }}
QMenu::icon {{ padding-left: 6px; }}

/* ---- Scroll bars ---- */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle {{ background: {scroll}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: 24px; }}
QScrollBar::handle:horizontal {{ min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- Progress and drives ---- */
QProgressBar {{
    background-color: {input}; border: 1px solid {border};
    border-radius: {small_radius}; text-align: center; color: {text};
    max-height: 14px;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: {small_radius}; }}
DriveItemWidget {{
    background-color: {surface}; border: 1px solid {border}; border-radius: 10px;
}}
DriveItemWidget:hover {{ border: 1px solid {accent}; }}
DriveItemWidget QLabel {{ background: transparent; }}

QDialog {{ background-color: {bg}; }}
"""


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
        self.current_theme = "dark"
        self.themes = {name: name for name in ("light", "dark", "retro", "system")}

        # Load saved theme preference
        self.settings = QSettings("ShadowsExplorer", "Preferences")
        saved_theme = self.settings.value("theme", "dark")
        if saved_theme in self.themes:
            self.current_theme = saved_theme

    def _resolve(self, theme_name=None):
        """The palette name for a theme, resolving "system" to light or dark."""
        theme_name = theme_name or self.current_theme
        if theme_name == "system":
            app = QGuiApplication.instance()
            light = app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Light
            return "light" if light else "dark"
        return theme_name if theme_name in PALETTES else "dark"

    def palette(self, theme_name=None):
        """Color tokens of a theme (see PALETTES)."""
        return PALETTES[self._resolve(theme_name)]

    def get_theme_stylesheet(self, theme_name=None):
        """Get the stylesheet for the specified theme.

        Args:
            theme_name: Name of the theme. If None, uses current theme.

        Returns:
            str: Qt stylesheet for the theme
        """
        return STYLESHEET.format(**self.palette(theme_name))

    def is_dark(self, theme_name=None):
        """Whether a theme has a dark background.

        Args:
            theme_name: Name of the theme. If None, uses current theme.
        """
        return self.palette(theme_name)["dark"]

    def set_theme(self, theme_name):
        """Set the current theme.

        Args:
            theme_name: Name of the theme to set
        """
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.settings.setValue("theme", theme_name)
            self.theme_changed.emit(theme_name)
