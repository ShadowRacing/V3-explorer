import os

import pytest

from shadows_explorer.core.file_types import EXTENSION_KINDS, file_kind
from shadows_explorer.theme.icons import FILE_TYPE_COLORS, UI_ICONS, file_type_icon, ui_icon
from shadows_explorer.theme.theme_manager import PALETTES, build_stylesheet, check_mark_file


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_every_palette_fills_the_stylesheet(name):
    # A missing color token would raise KeyError here
    stylesheet = build_stylesheet(PALETTES[name])
    assert "{" in stylesheet and "{{" not in stylesheet
    # Checked boxes get a real check mark image
    assert os.path.exists(check_mark_file(PALETTES[name]["on_accent"]))


def test_file_kind():
    assert file_kind("Report.PDF") == "pdf"
    assert file_kind("photo.jpeg") == "image"
    assert file_kind("main.py") == "code"
    assert file_kind("no_extension") == "file"


def test_every_kind_has_a_color():
    assert set(EXTENSION_KINDS.values()) <= set(FILE_TYPE_COLORS)


def test_icons_render(qapp):
    for name in UI_ICONS:
        assert not ui_icon(name, "#000000").isNull(), name
    for kind in list(FILE_TYPE_COLORS) + ["folder", "folder_link"]:
        assert not file_type_icon(kind).isNull(), kind


def test_base_font_has_a_point_size(qapp):
    # A px font has pointSize() -1, which Qt's Windows 11 style passes to
    # QFont.setPointSize when drawing menu arrows
    from PyQt6.QtWidgets import QMenu, QToolButton
    button = QToolButton()
    button.setMenu(QMenu(button))
    button.setStyleSheet(build_stylesheet(PALETTES["dark"]))
    button.ensurePolished()
    font = button.font()
    assert font.pointSize() > 0
    # Still 13 px on screen
    assert round(font.pointSizeF() * button.logicalDpiY() / 72) == 13
