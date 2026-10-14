"""
Bulk rename dialog for Shadows File Explorer.

Lets the user rename many files at once with find/replace, a numbered name
template, prefix/suffix and case changes, showing a live preview of every new
name and blocking the rename while any name would clash.
"""
import os
import re

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QCheckBox,
                            QSpinBox, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
                            QLabel, QPushButton, QGroupBox, QAbstractItemView)
from PyQt6.QtGui import QColor

from bulk_rename import CASE_MODES, RenameOptions, find_problems, plan_renames


class BulkRenameDialog(QDialog):
    """Dialog for renaming several items at once.

    After exec() returns Accepted, rename_pairs() gives the (old, new) paths.
    """

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.paths = list(paths)
        self.plan = []
        self.problems = {}
        self.setWindowTitle(f"Rename {len(self.paths)} Items")
        self.resize(720, 560)

        layout = QVBoxLayout(self)

        # Find and replace
        find_group = QGroupBox("Find and replace")
        find_form = QFormLayout(find_group)
        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        find_form.addRow("Find:", self.find_edit)
        find_form.addRow("Replace with:", self.replace_edit)
        find_options = QHBoxLayout()
        self.regex_check = QCheckBox("Regular expression")
        self.case_check = QCheckBox("Match case")
        find_options.addWidget(self.regex_check)
        find_options.addWidget(self.case_check)
        find_options.addStretch()
        find_form.addRow("", find_options)
        layout.addWidget(find_group)

        # Template, numbering, prefix/suffix, case
        name_group = QGroupBox("New name")
        name_form = QFormLayout(name_group)
        self.template_edit = QLineEdit()
        self.template_edit.setPlaceholderText("e.g. Holiday {n}  —  {name} is the current name, {n} a number")
        name_form.addRow("Template:", self.template_edit)
        numbering = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 999999)
        self.start_spin.setValue(1)
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(1, 8)
        numbering.addWidget(QLabel("Start at"))
        numbering.addWidget(self.start_spin)
        numbering.addSpacing(12)
        numbering.addWidget(QLabel("Digits"))
        numbering.addWidget(self.padding_spin)
        numbering.addStretch()
        name_form.addRow("Numbering:", numbering)
        self.prefix_edit = QLineEdit()
        self.suffix_edit = QLineEdit()
        name_form.addRow("Add before:", self.prefix_edit)
        name_form.addRow("Add after:", self.suffix_edit)
        self.case_combo = QComboBox()
        self.case_combo.addItems(["Unchanged", "lowercase", "UPPERCASE", "Title Case"])
        name_form.addRow("Case:", self.case_combo)
        self.extension_check = QCheckBox("Also change file extensions")
        name_form.addRow("", self.extension_check)
        layout.addWidget(name_group)

        # Live preview
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Current name", "New name", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Buttons
        buttons = QHBoxLayout()
        self.summary_label = QLabel()
        buttons.addWidget(self.summary_label, 1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        self.rename_button = QPushButton("Rename")
        self.rename_button.setProperty("class", "primary")
        self.rename_button.setDefault(True)
        self.rename_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(self.rename_button)
        layout.addLayout(buttons)

        for edit in (self.find_edit, self.replace_edit, self.template_edit, self.prefix_edit, self.suffix_edit):
            edit.textChanged.connect(self.update_preview)
        for check in (self.regex_check, self.case_check, self.extension_check):
            check.toggled.connect(self.update_preview)
        for spin in (self.start_spin, self.padding_spin):
            spin.valueChanged.connect(self.update_preview)
        self.case_combo.currentIndexChanged.connect(self.update_preview)

        self.update_preview()
        self.find_edit.setFocus()

    def options(self):
        """The RenameOptions described by the form."""
        return RenameOptions(
            find=self.find_edit.text(), replace=self.replace_edit.text(),
            use_regex=self.regex_check.isChecked(), case_sensitive=self.case_check.isChecked(),
            template=self.template_edit.text(), start=self.start_spin.value(),
            padding=self.padding_spin.value(), prefix=self.prefix_edit.text(),
            suffix=self.suffix_edit.text(), case=CASE_MODES[self.case_combo.currentIndex()],
            include_extension=self.extension_check.isChecked(),
        )

    def update_preview(self):
        """Recompute the new names and show them."""
        try:
            self.plan = plan_renames(self.paths, self.options())
            error = None
        except re.error as e:
            self.plan = [(path, os.path.basename(os.path.normpath(path))) for path in self.paths]
            error = f"Invalid regular expression: {e}"
        self.problems = find_problems(self.plan)

        self.table.setRowCount(len(self.plan))
        changed = 0
        for row, (path, new_name) in enumerate(self.plan):
            old_name = os.path.basename(os.path.normpath(path))
            problem = self.problems.get(path)
            if new_name != old_name:
                changed += 1
            new_item = QTableWidgetItem(new_name)
            status_item = QTableWidgetItem(problem or ("" if new_name == old_name else "✓"))
            if problem:
                for item in (new_item, status_item):
                    item.setForeground(QColor("#dc2626"))
            elif new_name != old_name:
                status_item.setForeground(QColor("#16a34a"))
            self.table.setItem(row, 0, QTableWidgetItem(old_name))
            self.table.setItem(row, 1, new_item)
            self.table.setItem(row, 2, status_item)

        if error:
            self.summary_label.setText(error)
        elif self.problems:
            self.summary_label.setText(f"{len(self.problems)} name(s) need fixing before renaming")
        else:
            self.summary_label.setText(f"{changed} of {len(self.plan)} items will be renamed")
        self.rename_button.setEnabled(bool(changed) and not self.problems and not error)

    def rename_pairs(self):
        """(old path, new path) for every item whose name changes."""
        return [(path, os.path.join(os.path.dirname(os.path.normpath(path)), new_name))
                for path, new_name in self.plan
                if new_name != os.path.basename(os.path.normpath(path))]
