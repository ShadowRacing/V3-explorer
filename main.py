"""
Shadows File Explorer - Main Application

This is the main module that brings together all components of the Shadows File Explorer.
It handles initialization and provides the entry point for the application.
"""
import sys
import platform
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from explorer import ModernExplorer


def setup_application():
    """Set up the application with proper settings."""
    app = QApplication(sys.argv)
    
    # High DPI settings
    if hasattr(Qt.ApplicationAttribute, 'HighDpiScaleFactorRoundingPolicy'):
        app.setAttribute(Qt.ApplicationAttribute.HighDpiScaleFactorRoundingPolicy, 
                        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        
    # Use high DPI pixmaps
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    elif hasattr(Qt.ApplicationAttribute, 'UseHighDpiPixmaps'):
        app.setAttribute(Qt.ApplicationAttribute.UseHighDpiPixmaps, True)
    
    # Set application name and organization
    app.setApplicationName("Shadows File Explorer")
    app.setOrganizationName("ShadowsExplorer")
    
    return app


def main():
    """Main entry point for the application."""
    app = setup_application()
    
    # Create and show the main window
    window = ModernExplorer()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
