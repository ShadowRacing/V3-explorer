"""
File type categories for Shadows File Explorer.

Maps file extensions to broad categories ("image", "code", "pdf", ...) used
for icons and for grouping by type. No Qt dependency.
"""
import os

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
