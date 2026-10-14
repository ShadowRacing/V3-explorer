import os

from file_operation_safety_manager import FileOperationSafetyManager


def test_protected_location_is_not_prefix_match(tmp_path):
    manager = FileOperationSafetyManager()
    manager.protected_locations = [str(tmp_path / "etc")]
    assert manager.is_location_protected(str(tmp_path / "etc" / "hosts"))
    assert not manager.is_location_protected(str(tmp_path / "etcetera"))


def test_executable_detection():
    manager = FileOperationSafetyManager()
    assert manager.is_executable_file("setup.EXE")
    assert not manager.is_executable_file("notes.txt")


def test_check_file_open_safety(tmp_path):
    manager = FileOperationSafetyManager()
    script = tmp_path / "run.bat"
    script.write_text("echo hi")
    text = tmp_path / "notes.txt"
    text.write_text("hi")
    assert manager.check_file_open_safety(str(script))[0] is False
    assert manager.check_file_open_safety(str(text)) == (True, None)


def test_writable_folder_needs_no_admin(tmp_path):
    manager = FileOperationSafetyManager()
    assert not manager.requires_admin_privileges(str(tmp_path))
    assert os.listdir(tmp_path) == []  # The check leaves nothing behind
