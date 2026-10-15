"""
Start-up splash for Shadows File Explorer.

Plays the bundled logo video (resources/ShadowsExplorerLogo.mp4) in a
frameless window while the main window is built, then shows the main window
when the video ends. A click or any key skips it.

If the video cannot play (Qt Multimedia or its libraries are missing, the
file is gone or unreadable, or no frame arrives in time) the splash shows
the video's last frame (resources/ShadowsExplorerLogo.png) as a still
instead, and if that is missing too it just shows the main window.

Qt Multimedia is imported only here, when the video starts, so a broken
multimedia install never stops the app from starting.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPalette, QPixmap
from PyQt6.QtWidgets import QLabel, QStackedLayout, QWidget

RESOURCES = Path(__file__).resolve().parent.parent / "resources"
VIDEO_PATH = RESOURCES / "ShadowsExplorerLogo.mp4"
STILL_PATH = RESOURCES / "ShadowsExplorerLogo.png"

SPLASH_SETTING = "splash_video"   # QSettings key: play the splash at start-up
BACKGROUND = "#0B0F17"            # the video's own background colour
FIRST_FRAME_MS = 3000             # no frame by then: fall back to the still
STILL_MS = 1500                   # how long the still is shown
MAX_MS = 12000                    # never hold start-up longer than this
MAX_WIDTH = 960                   # splash size; the video is 16:9


def splash_enabled(settings):
    """Whether the splash plays at start-up (on unless turned off in Settings)."""
    return settings.value(SPLASH_SETTING, True, type=bool)


class SplashScreen(QWidget):
    """Frameless start-up window: the logo video, or its last frame as a still.

    Call start(), build the main window, then show_window_when_done(window):
    the window is shown when the video ends, is skipped, or fails.

    Signals:
        finished: The splash closed and the main window is showing
    """

    finished = pyqtSignal()

    def __init__(self, video_path=VIDEO_PATH, still_path=STILL_PATH):
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.video_path = Path(video_path)
        self.still_path = Path(still_path)
        self.player = None
        self.video_widget = None
        self.used_fallback = False
        self._got_frame = False
        self._done = False
        self._window = None

        self.setWindowTitle("Shadows File Explorer")
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(BACKGROUND))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._blank = QWidget()
        self._stack.addWidget(self._blank)
        self._still = QLabel()
        self._still.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._still)

        self._place()

    def _place(self):
        """Size the splash to the screen (16:9) and centre it."""
        screen = QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else None
        width = min(MAX_WIDTH, int(area.width() * 0.6)) if area else MAX_WIDTH
        self.resize(width, width * 9 // 16)
        if area:
            self.move(area.center() - self.rect().center())

    # --------------------------- Playback ---------------------------

    def start(self):
        """Show the splash and start the video (or the still if it cannot play)."""
        self.show()
        if not self._start_video():
            self._fall_back()
        QTimer.singleShot(MAX_MS, self._finish)

    def _start_video(self):
        if not self.video_path.is_file():
            return False
        try:
            from PyQt6.QtMultimedia import QMediaPlayer
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except ImportError:
            return False

        self.player = QMediaPlayer(self)
        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self._stack.addWidget(self.video_widget)
        self._stack.setCurrentWidget(self.video_widget)
        self.player.setVideoOutput(self.video_widget)

        self.player.errorOccurred.connect(self._on_error)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.video_widget.videoSink().videoFrameChanged.connect(self._on_frame)

        self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
        self.player.play()
        QTimer.singleShot(FIRST_FRAME_MS, self._check_first_frame)
        return True

    def _on_frame(self, frame):
        if frame.isValid():
            self._got_frame = True

    def _on_status(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish()
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            self._fall_back()

    def _on_error(self, error, message=""):
        self._fall_back()

    def _check_first_frame(self):
        if not self._done and not self.used_fallback and not self._got_frame:
            self._fall_back()

    def _fall_back(self):
        """Stop the video and show its last frame as a still, then finish."""
        if self._done or self.used_fallback:
            return
        self.used_fallback = True
        self._stop_player()
        pixmap = QPixmap(str(self.still_path)) if self.still_path.is_file() else QPixmap()
        if pixmap.isNull():
            self._finish()
            return
        self._still.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        self._stack.setCurrentWidget(self._still)
        QTimer.singleShot(STILL_MS, self._finish)

    def _stop_player(self):
        if self.player is not None:
            self.player.stop()
            self.player.setSource(QUrl())

    # ---------------------------- Finish ----------------------------

    def show_window_when_done(self, window):
        """Show *window* when the splash ends (at once if it already has)."""
        self._window = window
        if self._done:
            self._reveal()

    def _finish(self):
        if self._done:
            return
        self._done = True
        self._stop_player()
        if self._window is not None:
            self._reveal()
        else:
            self.hide()

    def _reveal(self):
        window, self._window = self._window, None
        if window is None:
            return
        window.show()
        window.raise_()
        window.activateWindow()
        self.close()
        self.finished.emit()

    def mousePressEvent(self, event):
        self._finish()

    def keyPressEvent(self, event):
        self._finish()
