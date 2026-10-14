"""
"Open terminal here" for Shadows File Explorer.

Works out how to start the system's terminal in a folder. The folder is
always passed as the working directory or as its own argument, never pasted
into a command line, so folder names with quotes or semicolons are safe.
"""
import os
import platform
import shutil

# Linux terminals, in order of preference, with the arguments that set the folder
LINUX_TERMINALS = [
    ("x-terminal-emulator", []),
    ("gnome-terminal", ["--working-directory={folder}"]),
    ("konsole", ["--workdir", "{folder}"]),
    ("xfce4-terminal", ["--working-directory", "{folder}"]),
    ("mate-terminal", ["--working-directory", "{folder}"]),
    ("tilix", ["--working-directory", "{folder}"]),
    ("alacritty", ["--working-directory", "{folder}"]),
    ("kitty", ["--directory", "{folder}"]),
    ("wezterm", ["start", "--cwd", "{folder}"]),
    ("xterm", []),
]


def terminal_command(folder, system=None, which=shutil.which, environ=os.environ):
    """How to open a terminal in folder.
    
    Args:
        folder: Folder the terminal should start in
        system: platform.system() value (for tests)
        which: shutil.which-like lookup (for tests)
        environ: Environment (for tests); $TERMINAL is honoured on Linux
        
    Returns:
        tuple: (argv, working_directory), or (None, None) if no terminal was found
    """
    system = system or platform.system()
    if system == "Windows":
        if which("wt"):
            return ["wt", "-d", folder], folder
        if which("powershell"):
            return ["powershell", "-NoExit"], folder
        return ["cmd"], folder
    if system == "Darwin":
        return ["open", "-a", "Terminal", folder], folder
    
    preferred = environ.get("TERMINAL")
    if preferred and which(preferred):
        return [preferred], folder
    for program, args in LINUX_TERMINALS:
        if which(program):
            return [program] + [arg.format(folder=folder) for arg in args], folder
    return None, None
