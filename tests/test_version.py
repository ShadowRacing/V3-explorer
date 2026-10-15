from shadows_explorer import __version__


def test_version_is_3_0():
    assert __version__ == "3.0"


def test_settings_about_page_shows_version(qapp):
    from shadows_explorer.theme.theme_manager import ThemeManager
    from shadows_explorer.ui.dialogs.settings import SettingsDialog

    dialog = SettingsDialog(ThemeManager())
    dialog.show_page("About")
    assert dialog.pages_list.currentItem().text() == "About"
    assert dialog.version_label.text() == "Version 3.0"
