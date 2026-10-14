"""
Command bar for Shadows File Explorer.

A searchable list of everything the app can do (Ctrl+Shift+P), like the
command palette in code editors: type a few letters, pick with the arrow
keys, Enter runs it.
"""
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QSize

from shadows_explorer.core.fuzzy import rank


@dataclass
class Command:
    """One entry in the command bar."""
    name: str
    run: Callable
    shortcut: str = ""
    enabled: bool = True


class _CommandRow(QWidget):
    """Command name on the left, its shortcut on the right."""

    def __init__(self, command):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        name = QLabel(command.name)
        name.setStyleSheet("background: transparent;")
        layout.addWidget(name, 1)
        if command.shortcut:
            shortcut = QLabel(command.shortcut)
            shortcut.setObjectName("status_label")  # Muted color from the theme
            shortcut.setStyleSheet("background: transparent;")
            layout.addWidget(shortcut)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


class CommandPalette(QDialog):
    """Popup with a search field and the matching commands.

    Args:
        commands: The Command objects to offer (disabled ones are hidden)
        parent: Window to center the popup on
    """

    def __init__(self, commands, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.commands = [c for c in commands if c.enabled]
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command...  (Enter to run, Esc to close)")
        self.search.textChanged.connect(self._refresh)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.itemActivated.connect(self._run_item)
        self.list.itemClicked.connect(self._run_item)
        layout.addWidget(self.list)
        self._refresh()

        if parent is not None:
            # Near the top of the window, like an editor's command palette
            width = max(self.minimumWidth(), int(parent.width() * 0.45))
            self.resize(width, 420)
            top_left = parent.mapToGlobal(parent.rect().topLeft())
            self.move(top_left.x() + (parent.width() - width) // 2, top_left.y() + 60)
        self.search.setFocus()

    def _refresh(self):
        self.list.clear()
        for command in rank(self.search.text(), self.commands, key=lambda c: c.name):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, command)
            item.setSizeHint(QSize(0, 32))
            self.list.addItem(item)
            self.list.setItemWidget(item, _CommandRow(command))
        if self.list.count():
            self.list.setCurrentRow(0)

    def eventFilter(self, obj, event):
        # Arrow keys and Enter in the search field drive the list
        if obj is self.search and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if key == Qt.Key.Key_Down else -1
                row = max(0, min(self.list.count() - 1, self.list.currentRow() + step))
                self.list.setCurrentRow(row)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.list.currentItem() is not None:
                    self._run_item(self.list.currentItem())
                return True
        return super().eventFilter(obj, event)

    def _run_item(self, item):
        command = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        command.run()
