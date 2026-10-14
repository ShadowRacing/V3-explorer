# Shadows File Explorer

A modern file manager for Windows, macOS and Linux, built with Python and PyQt6.

## Features

- Tabs, each with its own back/forward history; open tabs are restored on the next start
- Sort by name, date, size or type from any view; group items by type, date modified (Today,
  Last week, ...) or size, with collapsible groups that refresh as files change
- Icon, list and details views, with an optional hidden-files toggle; the icon view shows picture
  thumbnails, loaded in the background
- Sidebar with pinned Favorites, standard folders and drives, plus a "This PC" overview with disk usage
- Drag and drop between folders, the sidebar and other apps
  (moves within a drive, copies between drives; hold Ctrl to copy, Shift to move)
- Breadcrumb path bar (click an empty spot or press Ctrl+L to type a path, with folder completion)
  and browser-style back / forward / up navigation
- Rename in place with F2 or by clicking a selected item; only the name is selected, not the extension
- Live filter (Ctrl+E): instantly show only the items in the current folder whose names match
- Recent page in the sidebar: folders you visited and files you opened, newest first
- Multi-threaded search with filters for date, size and file type
  (prefix a search with `AllDrives:` to search every drive)
- Open with: pick a program (remembered per file type) or, on Windows, the system's app chooser;
  Send to: a zip, Desktop, Documents, a favorite, the other pane or any folder
- Copy, cut, paste, rename and delete, using the system clipboard so it works with other file managers
- Delete moves items to the Recycle Bin / Trash; undo for copy, move and rename
- Two panes side by side (Ctrl+Shift+D): each with its own path bar and history; commands apply to
  the pane you last clicked, plus drag and drop and "Copy/Move to Other Pane"
- Bulk rename: find/replace (optionally regex), numbered templates like `Holiday {n}`, prefix/suffix
  and case changes, with a live preview; clashes are blocked and the whole rename undoes in one step
- Compress to ZIP and extract .zip / .tar archives in the background, with progress, cancel and undo
  ("Extract" uses a new folder so files never spill out; archives can't write outside it)
- Safety checks before deleting from system folders or opening downloaded or executable files
- Preview panel: images (with dimensions), PDFs (first page), rendered Markdown,
  syntax-highlighted code, plain text, and folder summaries
- Properties dialog with folder size calculation; optional folder sizes in the details view
  (Sort → Show folder sizes), measured in the background
- Find Duplicates (right-click a folder): files with identical content, compared by size then hash;
  tick copies (or keep oldest/newest automatically) and send them to the Recycle Bin, never all copies
- Analyze Disk Usage (right-click a folder): a size-sorted tree with share bars and the largest files
- Open Terminal Here (Ctrl+` or right-click): opens Windows Terminal, PowerShell, macOS Terminal or
  your Linux terminal ($TERMINAL first) in the current folder
- Command bar (Ctrl+Shift+P): type a few letters of any command ("new fol", "theme dark") and press Enter
- Light, dark, retro (Windows 98) and system themes with a matching icon set;
  window size, view mode and preview state are remembered

## Getting started

Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt   # Pygments is optional; it adds code highlighting
python main.py                    # opens your home folder
python main.py C:\Projects        # or start in a specific folder
```

Or install it as a package, which adds a `shadows-explorer` command:

```bash
pip install .                     # or: pip install ".[highlighting]"
shadows-explorer                  # same as: python -m shadows_explorer
```

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+C / Ctrl+X / Ctrl+V | Copy / cut / paste |
| Delete / Shift+Delete | Move to Recycle Bin / delete permanently |
| F2 | Rename in place (several selected: bulk rename) |
| Ctrl+L / Alt+D | Type or paste a path in the path bar |
| Ctrl+Z | Undo copy, move or rename |
| Alt+Left / Backspace, Alt+Right | Back, forward |
| Alt+Up | Up one folder |
| F5 | Refresh |
| Ctrl+F / Esc | Search / clear search |
| Ctrl+E | Filter the current folder (Esc clears it) |
| Ctrl+Shift+N | New folder |
| Ctrl+H | Show or hide hidden files |
| Alt+Enter | Properties |
| Ctrl+T / Ctrl+W | New tab / close tab |
| Ctrl+Tab, Ctrl+Shift+Tab | Next / previous tab |
| Middle-click a folder | Open it in a new tab |
| Ctrl+D | Pin or unpin the current folder in Favorites |
| Ctrl+Shift+D | Show or hide the second pane |
| Ctrl+Shift+P | Command bar: search and run any command |
| Ctrl+` | Open a terminal in the current folder |

## Project layout

```
main.py                     Starts the app from a source checkout
pyproject.toml              Package metadata and the shadows-explorer command
shadows_explorer/
├── app.py                  Creates the QApplication and main window
├── core/                   File-system logic, no widgets (unit tested)
│   ├── archive.py          Zip/unzip, safe against archives escaping their folder
│   ├── background.py       Runs slow jobs off the UI thread
│   ├── bulk_rename.py      Bulk rename rules and safe two-phase renaming
│   ├── disk_usage.py       Folder sizes and disk usage scans
│   ├── duplicates.py       Duplicate file finder
│   ├── file_types.py       File extension → category (image, code, pdf, ...)
│   ├── fuzzy.py            Fuzzy matching for the command bar
│   ├── grouping.py         Sorting and grouping rules
│   ├── open_with.py        Open-with commands and remembered programs
│   ├── recent.py           Recent files/folders and the live filter pattern
│   ├── safety.py           Protected folders, open/delete checks, Recycle Bin
│   ├── search.py           Multi-threaded search engine and filters
│   ├── terminal.py         Finds the terminal program to open in a folder
│   └── utils.py            Paths, sizes, navigation history
├── ui/                     Windows, views and panes
│   ├── main_window.py      The main window: navigation, tabs, file operations, search
│   ├── navigation_panel.py Sidebar with Favorites, Recent, locations and drives
│   ├── breadcrumb_bar.py   Clickable, editable path bar
│   ├── file_views.py       Folder views with drag and drop and in-place rename
│   ├── dual_pane.py        The second folder pane
│   ├── grouped_view.py     The grouped list
│   ├── thumbnails.py       Background picture thumbnails
│   ├── preview_pane.py     File preview panel
│   ├── drives_view.py      "This PC" drive overview
│   ├── search_results_model.py
│   ├── command_palette.py  The Ctrl+Shift+P command bar
│   └── dialogs/            Properties, settings, bulk rename, disk usage and duplicates dialogs
└── theme/
    ├── theme_manager.py    One stylesheet, a color palette per theme
    └── icons.py            The app's own SVG icon set
tests/                      pytest suite (runs without a display)
```

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest        # run the tests
python -m pyflakes main.py shadows_explorer tests  # lint
```

The tests need no display; they run Qt with the `offscreen` platform.
