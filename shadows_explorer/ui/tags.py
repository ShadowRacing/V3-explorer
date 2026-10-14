"""
Tag widgets for Shadows File Explorer.

Colored dots for tagged items, the "Tags" context submenu and the dialog for
creating or editing a tag. The tags themselves live in core/tags.py.
"""
from PyQt6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
                             QStyle, QStyledItemDelegate, QStyleOptionViewItem, QButtonGroup, QColorDialog,
                             QDialogButtonBox, QMenu)
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QPen

from shadows_explorer.core.tags import TAG_COLORS

TAG_COLORS_ROLE = Qt.ItemDataRole.UserRole + 20  # list of "#rrggbb" for an item's tags
DOT_SIZE = 9


def tag_dot_icon(color, size=16):
    """A round colored dot, for menus and the sidebar."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    margin = size * 0.18
    painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    painter.end()
    return QIcon(pixmap)


def paint_tag_dots(painter, rect, colors, top_right=False, background=None, left=None):
    """Draw overlapping dots for colors in rect.

    They go at the top-right corner (top_right), else at x = left when given
    (right after the name), else at the right edge, never past the right edge.
    """
    if not colors:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = DOT_SIZE + 3 if top_right else DOT_SIZE  # Bigger next to big icons
    step = size - 3  # Dots overlap a little, like Finder's
    width = size + step * (len(colors) - 1)
    x = rect.right() - width - 4
    if left is not None and not top_right:
        x = min(left, x)
    y = rect.top() + 4 if top_right else rect.center().y() - size / 2
    # A ring in the background color keeps overlapping dots apart
    ring = QPen(QColor(background) if background else QColor(0, 0, 0, 0), 1.5)
    for i, color in enumerate(colors):
        painter.setPen(ring)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(x + i * step, y, size, size))
    painter.restore()


class TagDotsDelegate(QStyledItemDelegate):
    """Item delegate that adds tag dots, from TAG_COLORS_ROLE or a lookup by path.

    Args:
        colors_for: Optional callable(index) -> colors, used when the model
            doesn't provide TAG_COLORS_ROLE itself
    """

    def __init__(self, parent=None, colors_for=None):
        super().__init__(parent)
        self.colors_for = colors_for

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        colors = index.data(TAG_COLORS_ROLE)
        if colors is None and self.colors_for is not None:
            colors = self.colors_for(index)
        if colors:
            view = self.parent()
            icon_mode = hasattr(view, "viewMode") and view.viewMode() == view.ViewMode.IconMode
            # Right after the name, where they read as part of it
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            style = opt.widget.style() if opt.widget else QApplication.style()
            text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, opt, opt.widget)
            text_width = min(opt.fontMetrics.horizontalAdvance(opt.text), text_rect.width())
            paint_tag_dots(painter, option.rect, colors, top_right=icon_mode,
                           background=option.palette.base().color(), left=text_rect.left() + text_width + 8)


def build_tags_menu(menu, paths, store, changed, new_tag):
    """Fill menu with a checkable entry per tag, plus New Tag... and Remove All Tags.

    Args:
        menu: QMenu to fill
        paths: Items the menu acts on
        store: core.tags.TagStore
        changed: Callback() after tags were changed
        new_tag: Callback(paths) that asks for a new tag and applies it
    """
    for name, color in store.tags.items():
        have = sum(1 for path in paths if name in store.tags_for(path))
        action = menu.addAction(tag_dot_icon(color), name)
        action.setCheckable(True)
        action.setChecked(bool(paths) and have == len(paths))
        if 0 < have < len(paths):
            action.setText(f"{name}  (some)")
        action.triggered.connect(lambda checked=False, n=name: (store.toggle_tag(paths, n), changed()))
    menu.addSeparator()
    menu.addAction("New Tag...", lambda: new_tag(paths))
    remove = menu.addAction("Remove All Tags", lambda: (store.clear(paths), changed()))
    remove.setEnabled(any(store.tags_for(path) for path in paths))
    return menu


def add_tags_submenu(menu, paths, store, changed, new_tag):
    """Add a "Tags" submenu to a context menu."""
    submenu = QMenu("Tags", menu)
    build_tags_menu(submenu, paths, store, changed, new_tag)
    menu.addMenu(submenu)
    return submenu


class TagDialog(QDialog):
    """Ask for a tag's name and color (for a new tag, or to edit one)."""

    def __init__(self, title, name="", color=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.color = color or TAG_COLORS[len(name) % len(TAG_COLORS)]
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("e.g. Work, Important, To do")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("Color:"))
        swatches = QHBoxLayout()
        self.buttons = QButtonGroup(self)
        for color_option in TAG_COLORS:
            button = QPushButton()
            button.setCheckable(True)
            button.setFixedSize(QSize(28, 28))
            button.setToolTip(color_option)
            button.setIcon(tag_dot_icon(color_option, 22))
            button.setIconSize(QSize(22, 22))
            button.setStyleSheet("QPushButton { padding: 0; border-radius: 14px; }"
                                 "QPushButton:checked { border: 2px solid palette(highlight); }")
            button.setChecked(color_option.lower() == self.color.lower())
            button.clicked.connect(lambda checked=False, c=color_option: self._set_color(c))
            self.buttons.addButton(button)
            swatches.addWidget(button)
        other = QPushButton("Other...")
        other.clicked.connect(self._pick_color)
        swatches.addWidget(other)
        swatches.addStretch()
        layout.addLayout(swatches)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.name_edit.textChanged.connect(lambda text: self.ok_button.setEnabled(bool(text.strip())))
        self.ok_button.setEnabled(bool(name.strip()))
        layout.addWidget(buttons)

    def _set_color(self, color):
        self.color = color

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self.color), self, "Tag Color")
        if color.isValid():
            self.color = color.name()
            # An exclusive group can't have nothing checked, so lift that briefly
            self.buttons.setExclusive(False)
            for button in self.buttons.buttons():
                button.setChecked(False)
            self.buttons.setExclusive(True)

    def values(self):
        return self.name_edit.text().strip(), self.color
