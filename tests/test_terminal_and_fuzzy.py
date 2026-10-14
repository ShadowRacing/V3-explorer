from shadows_explorer.core.fuzzy import fuzzy_score, rank
from shadows_explorer.core.terminal import terminal_command

TRICKY = "/home/me/it's; rm -rf ~"


def only(*names):
    return lambda program: f"/usr/bin/{program}" if program in names else None


def test_windows_prefers_windows_terminal():
    assert terminal_command("C:\\x", "Windows", only("wt", "powershell")) == (["wt", "-d", "C:\\x"], "C:\\x")
    assert terminal_command("C:\\x", "Windows", only("powershell")) == (["powershell", "-NoExit"], "C:\\x")
    assert terminal_command("C:\\x", "Windows", only()) == (["cmd"], "C:\\x")


def test_macos_uses_terminal_app():
    assert terminal_command(TRICKY, "Darwin") == (["open", "-a", "Terminal", TRICKY], TRICKY)


def test_linux_finds_a_terminal_and_passes_folder_as_one_argument():
    argv, cwd = terminal_command(TRICKY, "Linux", only("gnome-terminal"), {})
    assert argv == ["gnome-terminal", f"--working-directory={TRICKY}"] and cwd == TRICKY
    argv, _ = terminal_command(TRICKY, "Linux", only("konsole"), {})
    assert argv == ["konsole", "--workdir", TRICKY]


def test_linux_honours_terminal_variable_and_handles_none():
    assert terminal_command("/x", "Linux", only("foot", "xterm"), {"TERMINAL": "foot"})[0] == ["foot"]
    assert terminal_command("/x", "Linux", only(), {}) == (None, None)


def test_fuzzy_score():
    assert fuzzy_score("nf", "New Folder") is not None
    assert fuzzy_score("xyz", "New Folder") is None
    assert fuzzy_score("", "anything") == 0
    # Word starts beat letters in the middle of words
    assert fuzzy_score("nf", "New Folder") > fuzzy_score("nf", "Unify")


def test_rank():
    commands = ["Copy", "Copy as Path", "Paste", "Open Terminal Here", "Toggle Preview"]
    assert rank("cop", commands)[:2] == ["Copy", "Copy as Path"]
    assert rank("term", commands)[0] == "Open Terminal Here"
    assert rank("", commands) == commands
    assert rank("zzz", commands) == []
