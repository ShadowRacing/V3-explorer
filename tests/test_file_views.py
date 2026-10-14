from PyQt6.QtCore import Qt

from file_views import same_device, should_move

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
