"""
"Open with" support for Shadows File Explorer.

Builds the command lines for opening files with a chosen program (no shell is
involved, so file names are never interpreted as commands) and remembers the
programs used per file type, newest first.
"""
import json
import os
import platform

MAX_PROGRAMS_PER_TYPE = 5


def program_display_name(program):
    """A readable name for a program path ("C:/.../notepad.exe" -> "notepad")."""
    name = os.path.basename(os.path.normpath(program))
    for suffix in (".exe", ".app", ".bat", ".cmd"):
        if name.lower().endswith(suffix):
            return name[:-len(suffix)]
    return name


def launch_command(program, paths, system=None):
    """argv that opens paths with program.

    macOS application bundles (.app) are started through ``open -a``;
    everything else gets the paths as arguments.
    """
    system = system or platform.system()
    if system == "Darwin" and program.lower().rstrip("/").endswith(".app"):
        return ["open", "-a", program, *paths]
    return [program, *paths]


def system_chooser_command(path, system=None):
    """argv for the operating system's own "choose an app" dialog, or None.

    Only Windows has one that can be started for a file.
    """
    system = system or platform.system()
    if system == "Windows":
        return ["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path]
    return None


def file_type_key(path):
    """Key used to remember programs: the lowercase extension, or "" for none."""
    return os.path.splitext(path)[1].lower()


class ProgramHistory:
    """Programs the user opened files with, per file type, newest first.

    Stored as JSON in QSettings (or any object with value()/setValue()).
    """

    SETTINGS_KEY = "open_with_programs"

    def __init__(self, settings):
        self.settings = settings
        raw = settings.value(self.SETTINGS_KEY, "{}")
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except ValueError:
            data = {}
        self.programs = {k: [p for p in v if isinstance(p, str)]
                         for k, v in data.items() if isinstance(v, list)} if isinstance(data, dict) else {}

    def remember(self, path, program):
        """Record that a file like path was opened with program."""
        key = file_type_key(path)
        programs = [p for p in self.programs.get(key, []) if os.path.normcase(p) != os.path.normcase(program)]
        programs.insert(0, program)
        self.programs[key] = programs[:MAX_PROGRAMS_PER_TYPE]
        self.settings.setValue(self.SETTINGS_KEY, json.dumps(self.programs))

    def programs_for(self, path):
        """Remembered programs for files like path that still exist."""
        return [p for p in self.programs.get(file_type_key(path), []) if os.path.exists(p)]
