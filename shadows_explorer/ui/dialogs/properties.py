"""
Properties dialog module for Shadows File Explorer.

This module provides the PropertiesDialog class which shows details about a
file or folder. Folder sizes are calculated in a background thread.
"""
import threading

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton,
                            QHBoxLayout, QStyle, QFileIconProvider, QTabWidget, QWidget)
from PyQt6.QtCore import Qt, QFileInfo, pyqtSignal
from PyQt6.QtGui import QImageReader

from shadows_explorer.core.disk_usage import folder_size
from shadows_explorer.core.file_types import file_kind
from shadows_explorer.core.media_info import media_details
from shadows_explorer.core.utils import format_size


class PropertiesDialog(QDialog):
    """Dialog showing the properties of a file or folder.

    Signals:
        _size_ready: Internal; delivers the folder size from the worker thread
    """

    # object, not int: folder sizes overflow a 32-bit C int
    _size_ready = pyqtSignal(object, object, object)

    def __init__(self, path, parent=None):
        """Initialize the properties dialog.

        Args:
            path: File or folder to describe
            parent: Parent widget
        """
        super().__init__(parent)
        self.path = path
        self._cancel = threading.Event()
        info = QFileInfo(path)

        self.setWindowTitle(f"{info.fileName() or path} Properties")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # Icon and name
        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QFileIconProvider().icon(info).pixmap(32, 32))
        header.addWidget(icon_label)
        name_label = QLabel(info.fileName() or path)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(name_label, 1)
        layout.addLayout(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        if info.isDir():
            type_text = "Folder"
        elif info.suffix():
            type_text = f"{info.suffix().upper()} File"
        else:
            type_text = "File"
        if info.isSymLink():
            type_text += f" (link to {info.symLinkTarget()})"
        form.addRow("Type:", QLabel(type_text))

        location = QLabel(info.absolutePath())
        location.setWordWrap(True)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Location:", location)

        if info.isDir():
            self.size_label = QLabel("Calculating...")
            self.contains_label = QLabel("Calculating...")
            form.addRow("Size:", self.size_label)
            form.addRow("Contains:", self.contains_label)
            self._size_ready.connect(self._show_folder_size)
            threading.Thread(target=self._calculate_folder_size, daemon=True).start()
        else:
            size = info.size()
            form.addRow("Size:", QLabel(f"{format_size(size)} ({size:,} bytes)"))

        date_format = "yyyy-MM-dd hh:mm:ss"
        if info.birthTime().isValid():
            form.addRow("Created:", QLabel(info.birthTime().toString(date_format)))
        form.addRow("Modified:", QLabel(info.lastModified().toString(date_format)))
        form.addRow("Accessed:", QLabel(info.lastRead().toString(date_format)))

        attributes = []
        if not info.isWritable():
            attributes.append("Read-only")
        if info.isHidden():
            attributes.append("Hidden")
        if info.isExecutable() and not info.isDir():
            attributes.append("Executable")
        form.addRow("Attributes:", QLabel(", ".join(attributes) or "None"))

        details = [] if info.isDir() else self._media_rows(path)
        if details:
            # Like Explorer: General and Details tabs
            tabs = QTabWidget()
            general = QWidget()
            QVBoxLayout(general).addLayout(form)
            general.layout().addStretch()
            tabs.addTab(general, "General")
            details_widget = QWidget()
            details_form = QFormLayout(details_widget)
            details_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            for label, value in details:
                value_label = QLabel(value)
                value_label.setWordWrap(True)
                value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                if label == "Location":
                    # Where the photo was taken, on a map
                    lat, lon = (part.strip() for part in value.split(","))
                    value_label.setText(f'<a href="https://www.openstreetmap.org/?mlat={lat}&mlon={lon}'
                                        f'#map=15/{lat}/{lon}">{value}</a>')
                    value_label.setOpenExternalLinks(True)
                    value_label.setToolTip("Show on OpenStreetMap")
                details_form.addRow(f"{label}:", value_label)
            tabs.addTab(details_widget, "Details")
            layout.addWidget(tabs)
        else:
            layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_button = QPushButton("Close")
        close_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    @staticmethod
    def _media_rows(path):
        """Media details for the Details tab, with picture dimensions from Qt when the file has none."""
        rows = media_details(path)
        if file_kind(path) == "image" and not any(label == "Dimensions" for label, _ in rows):
            size = QImageReader(path).size()
            if size.isValid():
                rows.insert(0, ("Dimensions", f"{size.width()} x {size.height()}"))
        return rows

    def _calculate_folder_size(self):
        """Worker thread: measure the folder and report back via a signal."""
        total, files, folders = folder_size(self.path, self._cancel)
        if not self._cancel.is_set():
            self._size_ready.emit(total, files, folders)

    def _show_folder_size(self, total, files, folders):
        """Display the calculated folder size."""
        self.size_label.setText(f"{format_size(total)} ({total:,} bytes)")
        self.contains_label.setText(f"{files:,} files, {folders:,} folders")

    def done(self, result):
        """Stop the size calculation when the dialog closes."""
        self._cancel.set()
        super().done(result)
