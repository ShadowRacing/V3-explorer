from shadows_explorer.core.open_with import (MAX_PROGRAMS_PER_TYPE, ProgramHistory, launch_command,
                                             program_display_name, system_chooser_command)


class FakeSettings(dict):
    def value(self, key, default=None):
        return self.get(key, default)

    def setValue(self, key, value):
        self[key] = value


def test_launch_command_passes_paths_as_arguments():
    # File names go straight to the program as arguments, never through a shell
    tricky = "it's; rm -rf ~.txt"
    assert launch_command("/usr/bin/gedit", [tricky], system="Linux") == ["/usr/bin/gedit", tricky]
    assert launch_command("C:/Tools/np.exe", ["a.txt", "b.txt"], system="Windows") == \
        ["C:/Tools/np.exe", "a.txt", "b.txt"]
    assert launch_command("/Applications/Preview.app", ["p.png"], system="Darwin") == \
        ["open", "-a", "/Applications/Preview.app", "p.png"]


def test_system_chooser_only_on_windows():
    assert system_chooser_command("x.txt", system="Windows")[:2] == ["rundll32.exe", "shell32.dll,OpenAs_RunDLL"]
    assert system_chooser_command("x.txt", system="Linux") is None


def test_program_display_name():
    assert program_display_name("C:/Windows/notepad.exe") == "notepad"
    assert program_display_name("/Applications/Preview.app/") == "Preview"
    assert program_display_name("/usr/bin/gimp") == "gimp"


def test_program_history_per_type(tmp_path):
    programs = []
    for i in range(MAX_PROGRAMS_PER_TYPE + 2):
        program = tmp_path / f"prog{i}"
        program.write_text("")
        programs.append(str(program))
    settings = FakeSettings()
    history = ProgramHistory(settings)
    for program in programs:
        history.remember("a.TXT", program)
    history.remember("b.txt", programs[0])  # Moves to the front, no duplicate
    remembered = history.programs_for("other.txt")
    assert remembered[0] == programs[0]
    assert len(remembered) == MAX_PROGRAMS_PER_TYPE
    assert history.programs_for("x.png") == []
    assert ProgramHistory(settings).programs_for("c.txt") == remembered  # Persisted

    (tmp_path / "prog0").unlink()
    assert programs[0] not in history.programs_for("c.txt")  # Missing programs skipped


def test_corrupt_history_is_ignored():
    assert ProgramHistory(FakeSettings(open_with_programs="nope")).programs == {}
