import pytest

from icons import EXTENSION_KINDS, FILE_TYPE_COLORS, UI_ICONS, file_kind, file_type_icon, ui_icon
from theme_manager import PALETTES, STYLESHEET


@pytest.mark.parametrize("name", sorted(PALETTES))
def test_every_palette_fills_the_stylesheet(name):
    # A missing color token would raise KeyError here
    stylesheet = STYLESHEET.format(**PALETTES[name])
    assert "{" in stylesheet and "{{" not in stylesheet


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
