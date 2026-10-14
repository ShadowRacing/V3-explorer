"""
Preview pane module for Shadows File Explorer.

This module provides the PreviewPane class which displays a preview
of the selected file or folder:
- Images (with dimensions)
- PDFs (first page, via QtPdf when available)
- Markdown (rendered)
- Source code (syntax highlighted when Pygments is installed)
- Plain text
- Folders (number of files and subfolders)
"""
import html
import os

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QTextEdit, QToolButton)
from PyQt6.QtGui import QPixmap, QImageReader, QFont, QFontDatabase
from PyQt6.QtCore import Qt, QFileInfo, QSize, pyqtSignal

from shadows_explorer.theme.icons import FileIconProvider, ui_icon
from shadows_explorer.core.utils import format_size

try:
    from PyQt6.QtPdf import QPdfDocument
except ImportError:  # QtPdf is optional
    QPdfDocument = None

try:
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_for_filename
    from pygments.util import ClassNotFound
except ImportError:  # Pygments is optional
    highlight = None

TEXT_EXTENSIONS = {'.txt', '.log', '.ini', '.cfg', '.conf', '.csv', '.tsv', '.env', '.gitignore'}
CODE_EXTENSIONS = {'.py', '.pyw', '.js', '.ts', '.jsx', '.tsx', '.html', '.htm', '.css', '.scss',
                   '.xml', '.json', '.yaml', '.yml', '.toml', '.bat', '.cmd', '.ps1', '.sh',
                   '.c', '.h', '.cpp', '.hpp', '.cs', '.java', '.kt', '.rs', '.go', '.rb',
                   '.php', '.sql', '.lua', '.swift'}
MARKDOWN_EXTENSIONS = {'.md', '.markdown'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.svg'}
PDF_EXTENSIONS = {'.pdf'}
MAX_TEXT_CHARS = 20000


def read_text(file_path, limit=MAX_TEXT_CHARS):
    """Read the start of a text file.

    Returns:
        tuple: (text, truncated)
    """
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read(limit + 1)
    return content[:limit], len(content) > limit


def looks_binary(file_path):
    """Heuristic: a NUL byte in the first 4 KB means the file is not text."""
    try:
        with open(file_path, 'rb') as f:
            return b'\0' in f.read(4096)
    except OSError:
        return True


def highlight_code(code, file_path, dark):
    """Syntax-highlight code as HTML with inline styles, or None without Pygments."""
    if highlight is None:
        return None
    try:
        lexer = get_lexer_for_filename(file_path, stripnl=False)
    except ClassNotFound:
        return None
    formatter = HtmlFormatter(noclasses=True, nobackground=True,
                              style="monokai" if dark else "default")
    return highlight(code, lexer, formatter)


class PreviewPane(QWidget):
    """Widget for previewing file contents.

    Signals:
        close_requested: Emitted when the user clicks the close button
    """

    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the preview pane.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        # Performance settings (see core/performance.py)
        self.max_text_chars = MAX_TEXT_CHARS
        self.max_image_bytes = 50 * 1024 * 1024
        self.pdfs_enabled = True
        self.dark = True
        self.current_file = None
        self.icon_provider = FileIconProvider()
        # Needed for the themed background and border on a QWidget subclass
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Preview")
        self.title_label.setObjectName("preview_title")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.close_button = QToolButton()
        self.close_button.setIcon(ui_icon("close", "#9aa1ab"))
        self.close_button.setToolTip("Close Preview")
        self.close_button.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.close_button)

        self.layout.addLayout(header_layout)

        # Message shown when there is nothing to preview
        self.message_label = QLabel("Select a file to preview")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setObjectName("preview_message")
        self.layout.addWidget(self.message_label)

        # Text, code and Markdown preview
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setVisible(False)
        self.layout.addWidget(self.text_preview, 1)

        # Image and PDF preview
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setVisible(False)
        self.layout.addWidget(self.image_preview)

        # File info
        self.info_container = QWidget()
        self.info_container.setVisible(False)
        info_layout = QVBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 16, 0, 0)

        icon_layout = QHBoxLayout()
        self.file_icon = QLabel()
        icon_layout.addWidget(self.file_icon)
        self.file_name = QLabel()
        self.file_name.setObjectName("preview_name")
        self.file_name.setWordWrap(True)
        icon_layout.addWidget(self.file_name, 1)
        info_layout.addLayout(icon_layout)

        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addWidget(self.info_label)

        self.layout.addWidget(self.info_container)
        self.layout.addStretch()

    def set_icon_color(self, color):
        self.close_button.setIcon(ui_icon("close", color))

    def set_dark(self, dark):
        """Pick syntax highlighting colors for a dark or light theme."""
        self.dark = dark
        if self.current_file:
            self.preview_file(self.current_file)

    def _reset(self):
        self.message_label.setVisible(False)
        self.text_preview.clear()
        self.text_preview.setVisible(False)
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.info_container.setVisible(False)

    def _show_message(self, text):
        self.message_label.setText(text)
        self.message_label.setVisible(True)

    def _show_info(self, file_info, rows):
        """Show the icon, name and a list of (label, value) details."""
        self.file_icon.setPixmap(self.icon_provider.icon(file_info).pixmap(40, 40))
        self.file_name.setText(file_info.fileName() or file_info.absoluteFilePath())
        self.info_label.setText("<br>".join(f"<b>{label}:</b> {html.escape(str(value))}"
                                            for label, value in rows))
        self.info_container.setVisible(True)

    def preview_file(self, file_path):
        """Show a preview of a file or folder.

        Args:
            file_path: Path to preview
        """
        self.current_file = file_path
        self._reset()

        if not os.path.exists(file_path):
            self._show_message("File not found")
            return

        file_info = QFileInfo(file_path)
        if file_info.isDir():
            self._preview_folder(file_info)
            return

        rows = [
            ("Type", f"{file_info.suffix().upper()} File" if file_info.suffix() else "File"),
            ("Size", format_size(file_info.size())),
            ("Modified", file_info.lastModified().toString("yyyy-MM-dd hh:mm")),
            ("Location", file_info.absolutePath()),
        ]

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in IMAGE_EXTENSIONS:
                rows.insert(1, ("Dimensions", self._preview_image(file_path)))
            elif ext in PDF_EXTENSIONS:
                rows.insert(1, ("Pages", self._preview_pdf(file_path)))
            elif ext in MARKDOWN_EXTENSIONS:
                self._preview_markdown(file_path)
            elif ext in CODE_EXTENSIONS:
                self._preview_code(file_path)
            elif ext in TEXT_EXTENSIONS or not looks_binary(file_path):
                self._preview_text(file_path)
            else:
                self._show_message("No preview available")
        except OSError as e:
            self._show_message(f"Could not read file: {e}")

        self._show_info(file_info, rows)

    def _preview_folder(self, file_info):
        files = folders = 0
        try:
            with os.scandir(file_info.absoluteFilePath()) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir():
                            folders += 1
                        else:
                            files += 1
                    except OSError:
                        continue
            contents = f"{files} files, {folders} folders"
        except OSError as e:
            contents = f"Cannot read folder ({e.strerror})"
        self._show_message("Folder")
        self._show_info(file_info, [
            ("Type", "Folder"),
            ("Contains", contents),
            ("Modified", file_info.lastModified().toString("yyyy-MM-dd hh:mm")),
            ("Location", file_info.absolutePath()),
        ])

    def _set_text_font(self, monospace):
        if monospace:
            font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        else:
            font = QFont()
        self.text_preview.setFont(font)

    def _show_truncated_note(self, truncated):
        if truncated:
            self.text_preview.append("\n[File content truncated...]")

    def _preview_text(self, file_path):
        content, truncated = read_text(file_path, self.max_text_chars)
        self._set_text_font(monospace=True)
        self.text_preview.setPlainText(content)
        self._show_truncated_note(truncated)
        self.text_preview.setVisible(True)

    def _preview_code(self, file_path):
        content, truncated = read_text(file_path, self.max_text_chars)
        self._set_text_font(monospace=True)
        highlighted = highlight_code(content, file_path, self.dark)
        if highlighted:
            self.text_preview.setHtml(highlighted)
        else:
            self.text_preview.setPlainText(content)
        self._show_truncated_note(truncated)
        self.text_preview.setVisible(True)

    def _preview_markdown(self, file_path):
        content, truncated = read_text(file_path, self.max_text_chars)
        self._set_text_font(monospace=False)
        self.text_preview.setMarkdown(content)
        self._show_truncated_note(truncated)
        self.text_preview.setVisible(True)

    def _max_image_size(self):
        # The label itself has no size until it is shown, so use the pane's
        return QSize(max(100, self.width() - 40), max(100, int(self.height() * 0.6)))

    def _show_pixmap(self, pixmap):
        limit = self._max_image_size()
        if pixmap.width() > limit.width() or pixmap.height() > limit.height():
            pixmap = pixmap.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        self.image_preview.setPixmap(pixmap)
        self.image_preview.setVisible(True)

    def _preview_image(self, file_path):
        """Show an image; returns its dimensions as text."""
        reader = QImageReader(file_path)
        reader.setAutoTransform(True)
        size = reader.size()
        if os.path.getsize(file_path) > self.max_image_bytes:
            self._show_message("Too large to preview\n(the limit is set in Settings → Performance)")
            return f"{size.width()} × {size.height()} pixels" if size.isValid() else "Unknown"
        limit = self._max_image_size()
        if size.isValid() and (size.width() > limit.width() or size.height() > limit.height()):
            # Decode at display size: much faster and lighter than decoding full size, then scaling
            reader.setScaledSize(size.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        pixmap = QPixmap.fromImage(image) if not image.isNull() else QPixmap(file_path)
        if pixmap.isNull():
            self._show_message("Could not load image")
            return "Unknown"
        self._show_pixmap(pixmap)
        if not size.isValid():
            size = pixmap.size()
        return f"{size.width()} × {size.height()} pixels"

    def _preview_pdf(self, file_path):
        """Render the first page of a PDF; returns the page count as text."""
        if not self.pdfs_enabled:
            self._show_message("PDF previews are off\n(Settings → Performance)")
            return "Unknown"
        if QPdfDocument is None:
            self._show_message("PDF preview needs the QtPdf module")
            return "Unknown"
        document = QPdfDocument(self)
        try:
            if document.load(file_path) != QPdfDocument.Error.None_ or document.pageCount() == 0:
                self._show_message("Could not open PDF")
                return "Unknown"
            page_size = document.pagePointSize(0)
            limit = self._max_image_size()
            scale = min(limit.width() / page_size.width(), limit.height() / page_size.height()) * 2
            render_size = QSize(int(page_size.width() * scale), int(page_size.height() * scale))
            image = document.render(0, render_size)
            if image.isNull():
                self._show_message("Could not render PDF")
            else:
                self._show_pixmap(QPixmap.fromImage(image))
            return str(document.pageCount())
        finally:
            document.close()
            document.deleteLater()

    def clear_preview(self):
        """Reset the preview pane to its empty state."""
        self.current_file = None
        self._reset()
        self._show_message("Select a file to preview")
