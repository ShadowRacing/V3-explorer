"""
Application entry point for Shadows File Explorer.

Creates the QApplication, plays the start-up splash video and builds the
main window behind it. Run with ``python -m shadows_explorer [folder]``,
``python main.py [folder]``, or the ``shadows-explorer`` command after
``pip install .``. ``--no-splash`` skips the splash for that run.
"""
import sys

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from shadows_explorer import __version__
from shadows_explorer.ui.splash import SplashScreen, splash_enabled


def setup_application():
    """Set up the application with proper settings."""
    # Qt 6 handles high DPI scaling automatically
    app = QApplication(sys.argv)
    app.setApplicationName("Shadows File Explorer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ShadowsExplorer")
    return app


def parse_args(args):
    """Split the command line into (start folder or None, whether to play the splash)."""
    play_splash = "--no-splash" not in args
    rest = [arg for arg in args if arg != "--no-splash"]
    return (rest[0] if rest else None), play_splash


def main():
    """Main entry point for the application.

    An optional command-line argument sets the starting folder.
    """
    app = setup_application()
    start_path, play_splash = parse_args(sys.argv[1:])

    splash = None
    if play_splash and splash_enabled(QSettings("ShadowsExplorer", "Preferences")):
        splash = SplashScreen()
        splash.start()
        app.processEvents()

    # Imported after the splash is up: loading the main window's modules is
    # part of the start-up time the splash covers.
    from shadows_explorer.ui.main_window import ModernExplorer

    window = ModernExplorer(start_path=start_path)
    if splash is not None:
        splash.show_window_when_done(window)
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
