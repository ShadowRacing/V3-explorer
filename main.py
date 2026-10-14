"""
Shadows File Explorer - Main Application

This is the main module that brings together all components of the Shadows File Explorer.
It handles initialization and provides the entry point for the application.
"""
import sys

from PyQt6.QtWidgets import QApplication

from explorer import ModernExplorer


def setup_application():
    """Set up the application with proper settings."""
    # Qt 6 handles high DPI scaling automatically
    app = QApplication(sys.argv)
    app.setApplicationName("Shadows File Explorer")
    app.setOrganizationName("ShadowsExplorer")
    return app


def main():
    """Main entry point for the application.

    An optional command-line argument sets the starting folder.
    """
    app = setup_application()

    start_path = sys.argv[1] if len(sys.argv) > 1 else None
    window = ModernExplorer(start_path=start_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
