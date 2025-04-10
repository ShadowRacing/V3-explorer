"""
Settings dialog module for Shadows File Explorer.

This module provides the SettingsDialog class which allows users
to configure application settings like themes.
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QComboBox, QPushButton, QGroupBox)
from PyQt6.QtCore import Qt, pyqtSignal


class SettingsDialog(QDialog):
    """Dialog for application settings including theme selection.
    
    This dialog provides:
    - Theme selection and preview
    - Settings persistence
    - UI configuration options
    
    Signals:
        theme_changed: Emitted when theme is changed (theme_name)
    """
    
    theme_changed = pyqtSignal(str)
    
    def __init__(self, theme_manager, parent=None):
        """Initialize the settings dialog.
        
        Args:
            theme_manager: ThemeManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Appearance section
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QVBoxLayout(appearance_group)
        
        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_layout.addWidget(theme_label)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["System", "Light", "Dark", "Retro"])
        
        # Set current theme
        current_theme = self.theme_manager.current_theme
        if current_theme == "light":
            self.theme_combo.setCurrentIndex(1)
        elif current_theme == "dark":
            self.theme_combo.setCurrentIndex(2)
        elif current_theme == "retro":
            self.theme_combo.setCurrentIndex(3)
        else:  # system
            self.theme_combo.setCurrentIndex(0)
            
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(self.theme_combo)
        appearance_layout.addLayout(theme_layout)
        
        # Theme preview
        self.theme_preview = QLabel()
        self.theme_preview.setMinimumHeight(100)
        self.theme_preview.setAlignment(QLabel().alignment() | Qt.AlignmentFlag.AlignCenter)
        self.update_theme_preview()
        appearance_layout.addWidget(self.theme_preview)
        
        layout.addWidget(appearance_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def on_theme_changed(self, index):
        """Handle theme selection change.
        
        Args:
            index: Selected theme index
        """
        theme_names = ["system", "light", "dark", "retro"]
        selected_theme = theme_names[index]
        
        self.theme_manager.set_theme(selected_theme)
        self.theme_changed.emit(selected_theme)
        self.update_theme_preview()
    
    def update_theme_preview(self):
        """Update the theme preview image."""
        # This would normally show a preview image of the selected theme
        # For simplicity, we'll just show the theme name
        theme = self.theme_manager.current_theme
        self.theme_preview.setText(f"Preview of {theme.capitalize()} Theme")
