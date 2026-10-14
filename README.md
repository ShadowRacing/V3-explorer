# Shadows File Explorer

A modern file manager for Windows, macOS and Linux, built with Python and PyQt6.

## Features

- Tabs, each with its own back/forward history; open tabs are restored on the next start
- Icon, list and details views, with an optional hidden-files toggle
- Sidebar with pinned Favorites, standard folders and drives, plus a "This PC" overview with disk usage
- Drag and drop between folders, the sidebar and other apps
  (moves within a drive, copies between drives; hold Ctrl to copy, Shift to move)
- Breadcrumb path bar and browser-style back / forward / up navigation
- Multi-threaded search with filters for date, size and file type
  (prefix a search with `AllDrives:` to search every drive)
- Copy, cut, paste, rename and delete, using the system clipboard so it works with other file managers
- Delete moves items to the Recycle Bin / Trash; undo for copy, move and rename
- Safety checks before deleting from system folders or opening downloaded or executable files
- Preview panel: images (with dimensions), PDFs (first page), rendered Markdown,
  syntax-highlighted code, plain text, and folder summaries
- Properties dialog with folder size calculation
- Light, dark, retro and system themes; window size, view mode and preview state are remembered

## Getting started

Requires Python 3.9 or newer.

```bash
pip install -r requirements.txt   # Pygments is optional; it adds code highlighting
python main.py              # opens your home folder
python main.py C:\Projects  # or start in a specific folder
```

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+C / Ctrl+X / Ctrl+V | Copy / cut / paste |
| Delete / Shift+Delete | Move to Recycle Bin / delete permanently |
| F2 | Rename |
| Ctrl+Z | Undo copy, move or rename |
| Alt+Left / Backspace, Alt+Right | Back, forward |
| Alt+Up | Up one folder |
| F5 | Refresh |
| Ctrl+F / Esc | Search / clear search |
| Ctrl+Shift+N | New folder |
| Ctrl+H | Show or hide hidden files |
| Alt+Enter | Properties |
| Ctrl+T / Ctrl+W | New tab / close tab |
| Ctrl+Tab, Ctrl+Shift+Tab | Next / previous tab |
| Middle-click a folder | Open it in a new tab |
| Ctrl+D | Pin or unpin the current folder in Favorites |

## Project layout

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `explorer.py` | Main window: navigation, file operations, search UI |
| `navigation_panel.py` | Sidebar, including Favorites |
| `file_views.py` | Folder views with drag and drop |
| `breadcrumb_bar.py` | Clickable path bar |
| `drive_components.py` | "This PC" drive overview |
| `file_searcher.py` | Background search engine and filters |
| `search_results_model.py` | Search results table |
| `preview_pane.py` | File preview panel |
| `properties_dialog.py` | Properties dialog |
| `file_operation_safety_manager.py` | Protected folders, open/delete safety checks, Recycle Bin |
| `theme_manager.py`, `settings_dialog.py` | Themes and settings |
| `utils.py` | Shared helpers (no Qt widgets), covered by unit tests |

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest        # run the tests
python -m pyflakes *.py # lint
```

The tests need no display; they run Qt with the `offscreen` platform.
