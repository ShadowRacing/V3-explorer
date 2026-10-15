"""
Settings dialog module for Shadows File Explorer.

Pages are listed on the left: Appearance (theme, start-up video), Performance
(threads, caches, size limits and refresh rates, with presets) and About
(version).
Changes apply at once.
"""
import platform
from dataclasses import fields, replace

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QGroupBox,
                             QListWidget, QStackedWidget, QWidget, QFormLayout, QSpinBox, QCheckBox,
                             QScrollArea, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QT_VERSION_STR, PYQT_VERSION_STR

from shadows_explorer import __version__

from shadows_explorer.core.performance import (LIMITS, PRESET_DESCRIPTIONS, PRESETS, PerformanceSettings)
from shadows_explorer.ui.splash import SPLASH_SETTING, splash_enabled

# (setting name, label, suffix, tooltip) per group; booleans have no suffix
PERFORMANCE_GROUPS = [
    ("Thumbnails", [
        ("thumbnails", "Show picture thumbnails", None,
         "Off: pictures show a type icon in the icon view (fastest on slow disks and network folders)"),
        ("thumbnail_threads", "Threads making thumbnails", "",
         "More threads fill a folder of pictures faster, but use more CPU"),
        ("thumbnail_cache", "Thumbnails kept in memory", " thumbnails",
         "Bigger caches make going back to a folder instant, but use more memory "
         "(about 64 KB each, more when zoomed in)"),
        ("thumbnail_max_mb", "Skip pictures larger than", " MB", "Very large pictures are slow to decode"),
    ]),
    ("Search", [
        ("search_threads", "Search threads", "",
         "Folders searched at the same time. Automatic uses one per CPU core; fewer keeps the PC responsive, "
         "more can help on fast SSDs"),
        ("search_hidden_folders", "Search inside hidden folders", None,
         "Also look inside folders whose name starts with a dot (slower, more results)"),
        ("content_max_mb", "Search inside files up to", " MB",
         "content:\"...\" searches read each file; larger files are skipped because they take long"),
    ]),
    ("Folders and drives", [
        ("folder_size_threads", "Threads measuring folder sizes", "",
         "Used for the folder sizes in the details view"),
        ("folder_refresh_ms", "Wait before refreshing grouped folders", " ms",
         "Changes that come in bursts (copying many files) are shown together after this pause"),
        ("drive_refresh_s", "Check for new drives every", " s",
         "How quickly USB sticks and new drives appear. Off: only when you press Refresh"),
    ]),
    ("Preview panel", [
        ("preview_text_kb", "Preview text and code up to", " KB", "Longer files show their beginning"),
        ("preview_image_mb", "Preview pictures up to", " MB", "Larger pictures show a note instead"),
        ("preview_pdfs", "Preview PDF files", None, "Rendering the first page of big PDFs can take a moment"),
    ]),
    ("Memory", [
        ("undo_steps", "Undo steps to remember", " steps", "How many copies, moves and renames Ctrl+Z can undo"),
    ]),
]


class SettingsDialog(QDialog):
    """The settings window.

    Args:
        theme_manager: ThemeManager instance
        performance: The current PerformanceSettings
        settings: QSettings for options saved straight from the dialog (the start-up video)
        parent: Parent widget

    Signals:
        theme_changed: Emitted when theme is changed (theme_name)
        performance_changed: A performance setting changed (PerformanceSettings)
        clear_thumbnails_requested: "Clear thumbnail cache" was clicked
    """

    theme_changed = pyqtSignal(str)
    performance_changed = pyqtSignal(object)
    clear_thumbnails_requested = pyqtSignal()

    def __init__(self, theme_manager, performance=None, parent=None, settings=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.settings = settings
        self.performance = performance or PerformanceSettings()
        self.editors = {}
        self._updating = False
        self.setWindowTitle("Settings")
        self.resize(760, 620)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        body = QHBoxLayout()

        self.pages_list = QListWidget()
        self.pages_list.setFixedWidth(170)
        self.pages = QStackedWidget()
        for name, page in (("Appearance", self._appearance_page()), ("Performance", self._performance_page()),
                           ("About", self._about_page())):
            self.pages_list.addItem(name)
            self.pages.addWidget(page)
        self.pages_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.pages_list.setCurrentRow(0)
        body.addWidget(self.pages_list)
        body.addWidget(self.pages, 1)
        layout.addLayout(body, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def show_page(self, name):
        """Open the dialog on a page ("Appearance", "Performance" or "About")."""
        matches = self.pages_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.pages_list.setCurrentItem(matches[0])

    # -------------------------- Appearance --------------------------

    def _appearance_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("Appearance")
        group_layout = QVBoxLayout(group)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark", "Retro"])
        names = ["system", "light", "dark", "retro"]
        current = self.theme_manager.current_theme
        self.theme_combo.setCurrentIndex(names.index(current) if current in names else 0)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo, 1)
        group_layout.addLayout(theme_layout)

        self.theme_preview = QLabel()
        self.theme_preview.setMinimumHeight(100)
        self.theme_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_theme_preview()
        group_layout.addWidget(self.theme_preview)

        self.splash_check = QCheckBox("Play the start-up video")
        self.splash_check.setToolTip("Shows the logo video while the app starts. "
                                     "Click it or press any key to skip; --no-splash skips it for one run.")
        self.splash_check.setChecked(splash_enabled(self.settings) if self.settings is not None else True)
        self.splash_check.setEnabled(self.settings is not None)
        self.splash_check.toggled.connect(self.on_splash_toggled)
        group_layout.addWidget(self.splash_check)
        layout.addWidget(group)
        layout.addStretch()
        return page

    def on_theme_changed(self, index):
        selected_theme = ["system", "light", "dark", "retro"][index]
        self.theme_manager.set_theme(selected_theme)
        self.theme_changed.emit(selected_theme)
        self.update_theme_preview()

    def on_splash_toggled(self, checked):
        if self.settings is not None:
            self.settings.setValue(SPLASH_SETTING, checked)

    def update_theme_preview(self):
        theme = self.theme_manager.current_theme
        self.theme_preview.setText(f"Preview of {theme.capitalize()} Theme")

    # -------------------------- About --------------------------

    def _about_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("About")
        group_layout = QVBoxLayout(group)
        title = QLabel("Shadows File Explorer")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        group_layout.addWidget(title)
        self.version_label = QLabel(f"Version {__version__}")
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(self.version_label)
        built_with = QLabel(f"Python {platform.python_version()}, Qt {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}")
        built_with.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        group_layout.addWidget(built_with)
        layout.addWidget(group)
        layout.addStretch()
        return page

    # -------------------------- Performance --------------------------

    def _performance_page(self):
        content = QWidget()
        layout = QVBoxLayout(content)

        # Presets
        preset_group = QGroupBox("Preset")
        preset_layout = QVBoxLayout(preset_group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Tune for:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(PRESETS) + ["Custom"])
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        row.addWidget(self.preset_combo, 1)
        preset_layout.addLayout(row)
        self.preset_description = QLabel()
        self.preset_description.setWordWrap(True)
        self.preset_description.setObjectName("status_label")
        preset_layout.addWidget(self.preset_description)
        cores = PerformanceSettings.cpu_cores()
        system = QLabel(f"This computer has {cores} CPU core{'s' if cores != 1 else ''}.")
        system.setObjectName("status_label")
        preset_layout.addWidget(system)
        layout.addWidget(preset_group)

        types = {f.name: f.type for f in fields(PerformanceSettings)}
        for title, settings in PERFORMANCE_GROUPS:
            group = QGroupBox(title)
            form = QFormLayout(group)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            for name, label, suffix, tooltip in settings:
                if types[name] is bool:
                    editor = QCheckBox(label)
                    editor.toggled.connect(lambda value, n=name: self._set(n, value))
                    form.addRow("", editor)
                else:
                    editor = QSpinBox()
                    limit = LIMITS[name]
                    editor.setRange(limit.low, limit.high)
                    editor.setSuffix(suffix)
                    editor.setMinimumWidth(150)
                    if name == "search_threads":
                        editor.setSpecialValueText(f"Automatic ({cores})")
                    elif name == "drive_refresh_s":
                        editor.setSpecialValueText("Off")
                    editor.valueChanged.connect(lambda value, n=name: self._set(n, value))
                    form.addRow(f"{label}:", editor)
                editor.setToolTip(tooltip)
                self.editors[name] = editor
            if title == "Thumbnails":
                clear = QPushButton("Clear Thumbnail Cache")
                clear.setToolTip("Free the memory used by thumbnails; they are made again when needed")
                clear.clicked.connect(self.clear_thumbnails_requested.emit)
                form.addRow("", clear)
            layout.addWidget(group)

        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset = QPushButton("Restore Defaults")
        reset.clicked.connect(lambda: self.preset_combo.setCurrentText("Balanced"))
        reset_row.addWidget(reset)
        layout.addLayout(reset_row)
        layout.addStretch()

        self._show_performance()

        # The page is long, so it scrolls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _show_performance(self):
        """Put the current settings in the editors without triggering changes."""
        self._updating = True
        for name, editor in self.editors.items():
            value = getattr(self.performance, name)
            if isinstance(editor, QCheckBox):
                editor.setChecked(value)
            else:
                editor.setValue(value)
        preset = self.performance.preset_name()
        self.preset_combo.setCurrentText(preset)
        self.preset_description.setText(PRESET_DESCRIPTIONS[preset])
        self._updating = False

    def _set(self, name, value):
        if self._updating:
            return
        self.performance = replace(self.performance, **{name: value})
        self._updating = True
        preset = self.performance.preset_name()
        self.preset_combo.setCurrentText(preset)
        self.preset_description.setText(PRESET_DESCRIPTIONS[preset])
        self._updating = False
        self.performance_changed.emit(self.performance)

    def _apply_preset(self, name):
        if self._updating or name not in PRESETS:
            if name == "Custom" and not self._updating:
                self.preset_description.setText(PRESET_DESCRIPTIONS["Custom"])
            return
        self.performance = PRESETS[name]
        self._show_performance()
        self.performance_changed.emit(self.performance)
