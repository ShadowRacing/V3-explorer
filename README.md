# Shadows File Explorer

A modern file manager for Windows, macOS and Linux, built with Python and PyQt6.

## Features

- Tabs, each with its own back/forward history; open tabs are restored on the next start
- Icon, list and details views, with an optional hidden-files toggle; the icon view shows picture
  thumbnails, loaded in the background
- Sidebar with pinned Favorites, standard folders and drives, plus a "This PC" overview with disk usage
- Drag and drop between folders, the sidebar and other apps
  (moves within a drive, copies between drives; hold Ctrl to copy, Shift to move)
- Breadcrumb path bar (click an empty spot or press Ctrl+L to type a path, with folder completion)
  and browser-style back / forward / up navigation
- Rename in place with F2 or by clicking a selected item; only the name is selected, not the extension
- Multi-threaded search with filters for date, size and file type
  (prefix a search with `AllDrives:` to search every drive)
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
- Properties dialog with folder size calculation
- Light, dark, retro (Windows 98) and system themes with a matching icon set;
  window size, view mode and preview state are remembered

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
| F2 | Rename in place (several selected: bulk rename) |
| Ctrl+L / Alt+D | Type or paste a path in the path bar |
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
| Ctrl+Shift+D | Show or hide the second pane |

## Project layout

| File | Purpose |
|---|---|
| `main.py` | Entry point |
| `explorer.py` | Main window: navigation, file operations, search UI |
| `navigation_panel.py` | Sidebar, including Favorites |
| `file_views.py` | Folder views with drag and drop |
| `dual_pane.py` | The second folder pane |
| `thumbnails.py` | Background picture thumbnails for the icon view |
| `bulk_rename.py`, `bulk_rename_dialog.py` | Bulk rename logic and dialog |
| `archive_ops.py`, `background.py` | Zip/unzip, and running slow jobs off the UI thread |
| `breadcrumb_bar.py` | Clickable path bar |
| `drive_components.py` | "This PC" drive overview |
| `file_searcher.py` | Background search engine and filters |
| `search_results_model.py` | Search results table |
| `preview_pane.py` | File preview panel |
| `properties_dialog.py` | Properties dialog |
| `file_operation_safety_manager.py` | Protected folders, open/delete safety checks, Recycle Bin |
| `theme_manager.py`, `settings_dialog.py` | Themes (one stylesheet, a color palette per theme) and settings |
| `icons.py` | The app's own SVG icon set, recolored per theme |
| `utils.py` | Shared helpers (no Qt widgets), covered by unit tests |

## Development

```bash
pip install -r requirements-dev.txt
python -m pytest        # run the tests
python -m pyflakes *.py # lint
```

The tests need no display; they run Qt with the `offscreen` platform.
