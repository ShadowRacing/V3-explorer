"""
Preview pane module for Shadows File Explorer.

This module provides the PreviewPane class which displays a preview
of the selected file's content.
"""
import html
import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QTextEdit, QFrame, QToolButton, QStyle)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QFileInfo, pyqtSignal

from utils import format_size

TEXT_EXTENSIONS = {'.txt', '.log', '.ini', '.cfg', '.conf', '.toml', '.yaml', '.yml', '.py', '.pyw',
                   '.js', '.ts', '.html', '.htm', '.css', '.xml', '.json', '.md', '.csv', '.bat',
                   '.ps1', '.sh', '.c', '.h', '.cpp', '.java', '.rs', '.go', '.sql'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.svg'}
MAX_TEXT_CHARS = 10000


class PreviewPane(QWidget):
    """Widget for previewing file contents.
    
    This component provides:
    - Text file content preview
    - Image file preview
    - File metadata display
    - Support for multiple file types
    
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
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        
        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel("Preview")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        # Close button
        self.close_button = QToolButton()
        self.close_button.setText("×")
        self.close_button.setStyleSheet("font-size: 18px;")
        self.close_button.setToolTip("Close Preview")
        self.close_button.clicked.connect(self.close_requested.emit)
        header_layout.addWidget(self.close_button)
        
        self.layout.addLayout(header_layout)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: rgba(0, 0, 0, 0.1);")
        self.layout.addWidget(divider)
        
        # Default message
        self.message_label = QLabel("Select a file to preview")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("color: #888888; font-size: 14px; padding: 20px;")
        self.layout.addWidget(self.message_label)
        
        # Text preview
        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setVisible(False)
        self.layout.addWidget(self.text_preview)
        
        # Image preview
        self.image_preview = QLabel()
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setVisible(False)
        self.layout.addWidget(self.image_preview)
        
        # File info
        self.info_container = QWidget()
        self.info_container.setVisible(False)
        info_layout = QVBoxLayout(self.info_container)
        info_layout.setContentsMargins(0, 16, 0, 0)
        
        # File icon and name
        icon_layout = QHBoxLayout()
        self.file_icon = QLabel()
        icon_layout.addWidget(self.file_icon)
        
        self.file_name = QLabel()
        self.file_name.setStyleSheet("font-weight: bold; font-size: 16px;")
        icon_layout.addWidget(self.file_name)
        icon_layout.addStretch()
        
        info_layout.addLayout(icon_layout)
        
        # File details
        self.info_label = QLabel()
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("line-height: 150%;")
        info_layout.addWidget(self.info_label)
        
        self.layout.addWidget(self.info_container)
        
        # Add spacer at the bottom
        self.layout.addStretch()
        
        self.current_file = None
        
    def preview_file(self, file_path):
        """Show a preview of the selected file.
        
        Args:
            file_path: Path to the file to preview
        """
        self.current_file = file_path
        
        # Reset visibility
        self.message_label.setVisible(False)
        self.text_preview.setVisible(False)
        self.image_preview.setVisible(False)
        self.info_container.setVisible(True)
        
        if not os.path.exists(file_path):
            self.message_label.setText("File not found")
            self.message_label.setVisible(True)
            self.info_container.setVisible(False)
            return
            
        # Get file info
        try:
            file_info = QFileInfo(file_path)
            
            # Set file icon
            icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_FileIcon if file_info.isFile() else QStyle.StandardPixmap.SP_DirIcon
            )
            self.file_icon.setPixmap(icon.pixmap(24, 24))
            
            # Set file name
            self.file_name.setText(file_info.fileName())
            
            # Format size
            size = file_info.size()
            size_str = format_size(size)
                
            mod_date = file_info.lastModified().toString("yyyy-MM-dd hh:mm:ss")
            
            info_text = (f"<b>Type:</b> {html.escape(file_info.suffix().upper()) or 'File'}<br>"
                        f"<b>Size:</b> {size_str}<br>"
                        f"<b>Modified:</b> {mod_date}<br>"
                        f"<b>Path:</b> {html.escape(file_info.absolutePath())}")
                        
            self.info_label.setText(info_text)
        except Exception as e:
            self.info_label.setText(f"Error reading file info: {str(e)}")
            
        # Preview based on file type
        ext = os.path.splitext(file_path)[1].lower()
        
        # Text files
        if ext in TEXT_EXTENSIONS:
            self._preview_text_file(file_path)
                
        # Image files
        elif ext in IMAGE_EXTENSIONS:
            self._preview_image_file(file_path)
    
    def _preview_text_file(self, file_path):
        """Preview a text file.
        
        Args:
            file_path: Path to the text file
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(MAX_TEXT_CHARS + 1)
                if len(content) > MAX_TEXT_CHARS:
                    content = content[:MAX_TEXT_CHARS]
                    content += "\n\n[File content truncated...]"
                self.text_preview.setPlainText(content)
                self.text_preview.setVisible(True)
        except Exception as e:
            self.text_preview.setPlainText(f"Error reading file: {str(e)}")
            self.text_preview.setVisible(True)
    
    def _preview_image_file(self, file_path):
        """Preview an image file.
        
        Args:
            file_path: Path to the image file
        """
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            self.message_label.setText("Could not load image")
            self.message_label.setVisible(True)
            return
        
        # Scale to fit the pane width (the label itself has no size until shown)
        max_width = max(100, self.width() - 40)
        max_height = max(100, int(self.height() * 0.6))
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        
        self.image_preview.setPixmap(pixmap)
        self.image_preview.setVisible(True)
    
    def clear_preview(self):
        """Reset the preview pane to its empty state."""
        self.current_file = None
        self.text_preview.clear()
        self.text_preview.setVisible(False)
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.info_container.setVisible(False)
        self.message_label.setText("Select a file to preview")
        self.message_label.setVisible(True)
