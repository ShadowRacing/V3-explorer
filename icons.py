"""
Icon module for Shadows File Explorer.

All icons are simple SVG drawings defined here, so the app looks the same on
every platform and the interface icons can be recolored to match the theme.

- ui_icon(name, color): line icons for toolbars, menus and the sidebar
- file_type_icon(kind): colored icons for files and folders
- FileIconProvider: gives QFileSystemModel our file icons when the OS has none
"""
import os

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QFileIconProvider

ICON_SIZES = (16, 20, 24, 32, 48, 64, 96, 128)

# 24x24 line icons; {c} is replaced with the stroke color
UI_ICONS = {
    "back": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
    "forward": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "up": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "filter": '<path d="M4 6h16M7 12h10M10 18h4"/>',
    "settings": '<circle cx="12" cy="12" r="3"/>'
                '<path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1'
                'M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "preview": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M14 4v16"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron_right": '<path d="M9 6l6 6-6 6"/>',
    "chevron_down": '<path d="M6 9l6 6 6-6"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "home": '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "desktop": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "documents": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
    "downloads": '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M5 20h14"/>',
    "pictures": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/>'
                '<path d="M21 16l-5-5-8 8"/>',
    "music": '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "pc": '<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 19h20"/>',
    "drive": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 13h18"/><circle cx="17" cy="15.5" r="0.8"/>',
    "star": '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z"/>',
    "new": '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M12 11v6M9 14h6"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    "cut": '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/><path d="M8.5 16L18 4M15.5 16L6 4"/>',
    "paste": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 11h6M9 15h6"/>',
    "delete": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    "rename": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
    "properties": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "tab": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M9 6v4"/>',
    "window": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 8h18"/>',
    "view_icons": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
                  '<rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    "view_list": '<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4.5 6h.5M4.5 12h.5M4.5 18h.5"/>',
    "view_details": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14.5h18M9 9v11"/>',
    "archive": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/>'
               '<path d="M10 13h4"/>',
    "extract": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/>'
               '<path d="M12 11v6M9.5 14.5L12 17l2.5-2.5"/>',
    "dual": '<rect x="3" y="5" width="8" height="14" rx="1.5"/><rect x="13" y="5" width="8" height="14" rx="1.5"/>',
    "copy_to": '<rect x="3" y="5" width="8" height="14" rx="1.5"/><path d="M14 12h7M18 9l3 3-3 3"/>',
    "sort": '<path d="M7 4v16M3.5 16.5L7 20l3.5-3.5M14 6h7M14 11h5M14 16h3"/>',
    "group": '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M6 11h12M6 15h12M6 19h8"/>',
    "hidden": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
}

# Colored file type icons (24x24). A page with a folded corner and a glyph.
_PAGE = ('<path d="M6 2.5h8.5L19 7v14.5H6z" fill="{fill}" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>'
         '<path d="M14.5 2.5V7H19" fill="none" stroke="{c}" stroke-width="1.2" stroke-linejoin="round"/>')
_GLYPHS = {
    "text": '<path d="M9 11h7M9 14h7M9 17h5" stroke="{c}" stroke-width="1.3" stroke-linecap="round"/>',
    "code": '<path d="M10.5 11.5L8.5 14l2 2.5M14.5 11.5l2 2.5-2 2.5" fill="none" stroke="{c}" stroke-width="1.4" '
            'stroke-linecap="round" stroke-linejoin="round"/>',
    "image": '<circle cx="10" cy="11" r="1.4" fill="{c}"/><path d="M8 18.5l3-3.5 2 2 2-2.5 2.5 4z" fill="{c}"/>',
    "video": '<path d="M10.5 11v6l5-3z" fill="{c}"/>',
    "audio": '<path d="M11 17.5v-6l5-1v5.5" fill="none" stroke="{c}" stroke-width="1.3"/>'
             '<circle cx="10" cy="17.5" r="1.3" fill="{c}"/><circle cx="15" cy="16" r="1.3" fill="{c}"/>',
    "archive": '<path d="M12 4v2M12 7v2M12 10v2" stroke="{c}" stroke-width="1.6"/>'
               '<rect x="10.5" y="13" width="3" height="4" rx="0.6" fill="{c}"/>',
    "pdf": '<rect x="7.5" y="12" width="10" height="5" rx="1" fill="{c}"/>',
    "spreadsheet": '<path d="M8.5 11h8v7h-8zM8.5 14.5h8M12.5 11v7" fill="none" stroke="{c}" stroke-width="1.2"/>',
    "presentation": '<rect x="8.5" y="11" width="8" height="5.5" rx="0.8" fill="none" stroke="{c}" stroke-width="1.2"/>'
                    '<path d="M12.5 16.5v2" stroke="{c}" stroke-width="1.2"/>',
    "executable": '<rect x="8.5" y="11" width="8" height="7" rx="1" fill="none" stroke="{c}" stroke-width="1.2"/>'
                  '<path d="M8.5 13h8" stroke="{c}" stroke-width="1.2"/>',
    "file": '',
}
FILE_TYPE_COLORS = {
    "text": "#6b7a90", "code": "#3b82f6", "image": "#16a34a", "video": "#9333ea",
    "audio": "#db2777", "archive": "#b7791f", "pdf": "#dc2626", "spreadsheet": "#15803d",
    "presentation": "#ea580c", "executable": "#475569", "file": "#8792a2",
}
_FOLDER = ('<path d="M2.5 6.5a1.5 1.5 0 0 1 1.5-1.5h5l2 2h9a1.5 1.5 0 0 1 1.5 1.5v1.5H2.5z" fill="#d99a1e"/>'
           '<path d="M2.5 9.5h19v9a1.5 1.5 0 0 1-1.5 1.5H4a1.5 1.5 0 0 1-1.5-1.5z" fill="#f5b83d"/>')
_FOLDER_LINK = _FOLDER + '<path d="M13 16.5l4-4M14 12.5h3v3" fill="none" stroke="#7a4b00" stroke-width="1.4" ' \
                         'stroke-linecap="round" stroke-linejoin="round"/>'

EXTENSION_KINDS = {}
for _kind, _extensions in {
    "text": ".txt .log .ini .cfg .conf .md .rtf .csv .tsv .doc .docx .odt",
    "code": ".py .pyw .js .ts .jsx .tsx .html .htm .css .scss .json .xml .yaml .yml .toml .c .h .cpp .hpp "
            ".cs .java .kt .rs .go .rb .php .sql .lua .swift .sh .bat .cmd .ps1",
    "image": ".jpg .jpeg .png .gif .bmp .webp .svg .ico .tif .tiff .heic",
    "video": ".mp4 .avi .mov .wmv .mkv .flv .webm .m4v",
    "audio": ".mp3 .wav .flac .aac .ogg .wma .m4a",
    "archive": ".zip .rar .7z .tar .gz .bz2 .xz .tgz",
    "pdf": ".pdf",
    "spreadsheet": ".xls .xlsx .ods",
    "presentation": ".ppt .pptx .odp",
    "executable": ".exe .msi .com .dll .app .apk .appimage .deb .rpm",
}.items():
    for _ext in _extensions.split():
        EXTENSION_KINDS[_ext] = _kind


def file_kind(path):
    """Category of a file for its icon, from the extension ("file" if unknown)."""
    return EXTENSION_KINDS.get(os.path.splitext(path)[1].lower(), "file")


def _svg_document(body, view_box="0 0 24 24"):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}">{body}</svg>'


def _icon_from_svg(svg):
    """Render an SVG at several sizes into a QIcon (crisp at any size)."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    for size in ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


_cache = {}


def ui_icon(name, color):
    """A line icon in the given color (e.g. "#e6e8eb")."""
    key = ("ui", name, color)
    if key not in _cache:
        body = (f'<g fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
                f'stroke-linejoin="round">{UI_ICONS[name]}</g>')
        _cache[key] = _icon_from_svg(_svg_document(body))
    return _cache[key]


def file_type_icon(kind):
    """A colored icon for a file category, or "folder" / "folder_link"."""
    key = ("file", kind)
    if key not in _cache:
        if kind == "folder":
            body = _FOLDER
        elif kind == "folder_link":
            body = _FOLDER_LINK
        else:
            color = FILE_TYPE_COLORS.get(kind, FILE_TYPE_COLORS["file"])
            body = _PAGE.format(c=color, fill="#ffffff") + _GLYPHS.get(kind, "").format(c=color)
        _cache[key] = _icon_from_svg(_svg_document(body))
    return _cache[key]


def file_icon_for_path(path, is_dir=None):
    """The colored icon for a file or folder path."""
    if is_dir is None:
        is_dir = os.path.isdir(path)
    return file_type_icon("folder" if is_dir else file_kind(path))


class FileIconProvider(QFileIconProvider):
    """Icon provider using the app's own file icons.

    On Windows, files whose icon comes from the program itself (.exe, .lnk,
    .ico) keep their native icon; everything else uses our icon set so it
    matches the rest of the interface on every platform.
    """

    NATIVE_EXTENSIONS = {".exe", ".lnk", ".ico", ".url"}

    def icon(self, arg):
        if isinstance(arg, QFileIconProvider.IconType):
            if arg in (QFileIconProvider.IconType.Folder, QFileIconProvider.IconType.Desktop):
                return file_type_icon("folder")
            if arg == QFileIconProvider.IconType.File:
                return file_type_icon("file")
            return super().icon(arg)

        info = arg
        if info.isDir():
            return file_type_icon("folder_link" if info.isSymLink() else "folder")
        if f".{info.suffix().lower()}" in self.NATIVE_EXTENSIONS:
            native = super().icon(info)
            if not native.isNull():
                return native
        return file_type_icon(file_kind(info.fileName()))
