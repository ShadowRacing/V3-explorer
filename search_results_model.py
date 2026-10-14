"""
Search results model for Shadows File Explorer.

This module provides the SearchResultsModel class which manages
and displays search results.
"""
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QStyle, QApplication
from PyQt6.QtCore import Qt

from utils import format_size

PATH_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class SearchResultsModel(QStandardItemModel):
    """Model for displaying search results.

    This model provides:
    - Formatted display of search results
    - Storage of result data for display in views
    - Correct sorting by size and date (not by their display text)
    """

    def __init__(self, parent=None):
        """Initialize the search results model.

        Args:
            parent: Parent object
        """
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["Name", "Location", "Size", "Date Modified"])
        self.setSortRole(SORT_ROLE)

        style = QApplication.style()
        self._dir_icon = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self._file_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)

    def clear_results(self):
        """Clear all search results."""
        self.removeRows(0, self.rowCount())

    def add_result(self, result):
        """Add a search result to the model.

        Args:
            result: SearchResult object to add
        """
        name_item = QStandardItem(result.filename)
        name_item.setData(result.filepath, PATH_ROLE)
        name_item.setData(result.filename.lower(), SORT_ROLE)
        name_item.setIcon(self._dir_icon if result.is_directory else self._file_icon)

        location_item = QStandardItem(result.directory)
        location_item.setData(result.directory.lower(), SORT_ROLE)

        size_item = QStandardItem("Folder" if result.is_directory else format_size(result.size))
        size_item.setData(-1 if result.is_directory else result.size, SORT_ROLE)

        date_item = QStandardItem(result.last_modified)
        date_item.setData(result.mtime or 0, SORT_ROLE)

        for item in (name_item, location_item, size_item, date_item):
            item.setEditable(False)

        self.appendRow([name_item, location_item, size_item, date_item])
