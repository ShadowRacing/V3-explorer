"""
Search results model for Shadows File Explorer.

This module provides the SearchResultsModel class which manages 
and displays search results.
"""
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import QStyle, QApplication
from PyQt6.QtCore import Qt


class SearchResultsModel(QStandardItemModel):
    """Model for displaying search results.
    
    This model provides:
    - Formatted display of search results
    - Storage of result data for display in views
    - Support for sorting and filtering
    """
    
    def __init__(self, parent=None):
        """Initialize the search results model.
        
        Args:
            parent: Parent object
        """
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["Name", "Location", "Size", "Date Modified"])
        self.results = []
        
    def clear_results(self):
        """Clear all search results."""
        self.removeRows(0, self.rowCount())
        self.results = []
        
    def add_result(self, result):
        """Add a search result to the model.
        
        Args:
            result: SearchResult object to add
        """
        self.results.append(result)
        
        # Name column - add folder/file icon
        name_item = QStandardItem()
        name_item.setText(result.filename)
        name_item.setData(result.filepath, Qt.ItemDataRole.UserRole)
        
        # Set appropriate icon
        if result.is_directory:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            name_item.setIcon(icon)
        else:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            name_item.setIcon(icon)
        
        # Location column
        location_item = QStandardItem(result.directory)
        
        # Size column
        if result.is_directory:
            size_text = "Folder"
        else:
            size_text = self.format_file_size(result.size)
            
        size_item = QStandardItem(size_text)
        
        # Date modified column
        date_item = QStandardItem(result.last_modified)
        
        # Add row
        self.appendRow([name_item, location_item, size_item, date_item])
        
    def format_file_size(self, size):
        """Format file size into human-readable string.
        
        Args:
            size: Size in bytes
            
        Returns:
            str: Formatted size string
        """
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/(1024*1024):.1f} MB"
        else:
            return f"{size/(1024*1024*1024):.1f} GB"
