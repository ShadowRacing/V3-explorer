import time

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget

from shadows_explorer.app import parse_args
from shadows_explorer.ui import splash as splash_module
from shadows_explorer.ui.splash import STILL_PATH, VIDEO_PATH, SplashScreen, splash_enabled


def wait_for(qapp, condition, timeout=5.0):
    end = time.monotonic() + timeout
    while not condition() and time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)
    return condition()


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(splash_module, "STILL_MS", 50)
    monkeypatch.setattr(splash_module, "FIRST_FRAME_MS", 200)


def test_assets_ship_in_the_package():
    assert VIDEO_PATH.is_file() and VIDEO_PATH.stat().st_size > 0
    assert STILL_PATH.is_file() and STILL_PATH.stat().st_size > 0


def test_parse_args():
    assert parse_args([]) == (None, True)
    assert parse_args(["C:/Projects"]) == ("C:/Projects", True)
    assert parse_args(["--no-splash", "C:/Projects"]) == ("C:/Projects", False)
    assert parse_args(["--no-splash"]) == (None, False)


def test_splash_setting_defaults_on(tmp_path):
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    assert splash_enabled(settings)
    settings.setValue(splash_module.SPLASH_SETTING, False)
    assert not splash_enabled(settings)


def test_missing_video_falls_back_to_still(qapp, quick, tmp_path):
    splash = SplashScreen(video_path=tmp_path / "missing.mp4")
    window = QWidget()
    splash.start()
    splash.show_window_when_done(window)
    assert splash.used_fallback
    assert not splash._still.pixmap().isNull()
    assert wait_for(qapp, window.isVisible)
    assert not splash.isVisible()


def test_unplayable_video_falls_back_to_still(qapp, quick, tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"not a video")
    splash = SplashScreen(video_path=broken)
    window = QWidget()
    splash.start()
    splash.show_window_when_done(window)
    assert wait_for(qapp, window.isVisible)
    assert splash.used_fallback


def test_nothing_to_show_opens_window_at_once(qapp, tmp_path):
    splash = SplashScreen(video_path=tmp_path / "a.mp4", still_path=tmp_path / "b.png")
    splash.start()
    window = QWidget()
    splash.show_window_when_done(window)
    assert window.isVisible()


def test_key_press_skips(qapp, tmp_path):
    splash = SplashScreen(video_path=tmp_path / "missing.mp4")
    splash.start()
    window = QWidget()
    splash.show_window_when_done(window)
    QTest.keyClick(splash, Qt.Key.Key_Escape)
    assert window.isVisible()
    assert not splash.isVisible()


def test_settings_checkbox_saves_the_choice(qapp, tmp_path):
    from shadows_explorer.theme.theme_manager import ThemeManager
    from shadows_explorer.ui.dialogs.settings import SettingsDialog
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.Format.IniFormat)
    dialog = SettingsDialog(ThemeManager(), settings=settings)
    assert dialog.splash_check.isChecked()
    dialog.splash_check.setChecked(False)
    assert not splash_enabled(settings)
