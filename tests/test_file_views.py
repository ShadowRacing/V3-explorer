from PyQt6.QtCore import Qt

from shadows_explorer.ui.file_views import same_device, should_move

NO_KEYS = Qt.KeyboardModifier.NoModifier


def test_drop_within_same_drive_moves(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "dest").mkdir()
    assert should_move([str(tmp_path / "a.txt")], str(tmp_path / "dest"), NO_KEYS)


def test_ctrl_forces_copy_and_shift_forces_move(tmp_path):
    source, dest = str(tmp_path), str(tmp_path)
    assert not should_move([source], dest, Qt.KeyboardModifier.ControlModifier)
    assert should_move([source], dest, Qt.KeyboardModifier.ShiftModifier)


def test_missing_path_is_not_same_device(tmp_path):
    assert not same_device(str(tmp_path / "missing"), str(tmp_path))
    # Unknown device: copy rather than move, so nothing is lost
    assert not should_move([str(tmp_path / "missing")], str(tmp_path), NO_KEYS)


def test_list_view_selection_is_found(qapp):
    # Regression: a QListView selects one column, so selectedRows() returned
    # nothing and Copy/Delete/menus ignored the selection in icon and list views
    from PyQt6.QtGui import QStandardItem, QStandardItemModel
    from PyQt6.QtWidgets import QListView
    from shadows_explorer.ui.main_window import ModernExplorer

    model = QStandardItemModel(0, 4)
    for name in ("a", "b", "c"):
        model.appendRow([QStandardItem(name)] + [QStandardItem("x") for _ in range(3)])
    view = QListView()
    view.setModel(model)
    selection = view.selectionModel()
    selection.select(model.index(0, 0), selection.SelectionFlag.Select)
    selection.select(model.index(2, 0), selection.SelectionFlag.Select)

    indexes = ModernExplorer._selected_first_column(view)
    assert [index.data() for index in indexes] == ["a", "c"]


def test_load_thumbnail(qapp, tmp_path):
    from PyQt6.QtGui import QColor, QImage
    from shadows_explorer.ui.thumbnails import load_thumbnail

    image = QImage(400, 200, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    path = str(tmp_path / "wide.png")
    image.save(path)
    thumb = load_thumbnail(path, 100)
    assert (thumb.width(), thumb.height()) == (100, 50)  # Aspect ratio kept

    (tmp_path / "broken.png").write_bytes(b"not an image")
    assert load_thumbnail(str(tmp_path / "broken.png"), 100).isNull()
    assert load_thumbnail(str(tmp_path / "missing.png"), 100).isNull()
