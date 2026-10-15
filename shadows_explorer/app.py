"""
Application entry point for Shadows File Explorer.

Creates the QApplication and the main window. Run with
``python -m shadows_explorer [folder]``, ``python main.py [folder]``, or the
``shadows-explorer`` command after ``pip install .``.
"""
import sys

from PyQt6.QtWidgets import QApplication

from shadows_explorer import __version__
from shadows_explorer.ui.main_window import ModernExplorer


def setup_application():
    """Set up the application with proper settings."""
    # Qt 6 handles high DPI scaling automatically
    app = QApplication(sys.argv)
    app.setApplicationName("Shadows File Explorer")
    app.setApplicationVersion(__version__)
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
