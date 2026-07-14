from __future__ import annotations

import logging
from typing import Callable

import openglider.materials
from openglider.materials.material import Material
from openglider.gui.qt import QtWidgets, QtCore

logger = logging.getLogger(__name__)


def _make_copy_handler(text: str) -> Callable[[bool], None]:
    def handler(checked: bool = False) -> None:
        QtWidgets.QApplication.clipboard().setText(text)
    return handler


class ClothMaterialRow(QtWidgets.QWidget):
    def __init__(self, material: Material, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        self.setLayout(layout)

        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(20, 20)
        r, g, b = material.get_color_rgb()
        swatch.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #888;"
        )

        copy_text = f"{str(material)}#{material.color_code}"
        name_label = QtWidgets.QLabel(copy_text)

        copy_btn = QtWidgets.QPushButton("Copy")
        copy_btn.setFixedWidth(60)
        copy_btn.clicked.connect(_make_copy_handler(copy_text))

        layout.addWidget(swatch)
        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(copy_btn)


class ClothMaterialView(QtWidgets.QWidget):
    # list of (row_widget, searchable_text, parent_group_box)
    _rows: list[tuple[QtWidgets.QWidget, str, QtWidgets.QGroupBox]]

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = []

        outer_layout = QtWidgets.QVBoxLayout()
        self.setLayout(outer_layout)

        self._filter_input = QtWidgets.QLineEdit()
        self._filter_input.setPlaceholderText("Filter materials…")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.textChanged.connect(self._apply_filter)
        outer_layout.addWidget(self._filter_input)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll)

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout()
        content_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        content.setLayout(content_layout)
        scroll.setWidget(content)

        # Group by manufacturer.name
        groups: dict[str, list[Material]] = {}
        for material in openglider.materials.cloth.materials.values():
            base = f"{material.manufacturer}.{material.name}"
            groups.setdefault(base, []).append(material)

        for base_name, materials in sorted(groups.items()):
            group_box = QtWidgets.QGroupBox(base_name)
            group_layout = QtWidgets.QVBoxLayout()
            group_box.setLayout(group_layout)

            for material in materials:
                row = ClothMaterialRow(material, group_box)
                copy_text = f"{str(material)}#{material.color_code}"
                group_layout.addWidget(row)
                self._rows.append((row, copy_text.lower(), group_box))

            content_layout.addWidget(group_box)

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        visible_groups: set[QtWidgets.QGroupBox] = set()

        for row, search_text, group_box in self._rows:
            visible = not needle or needle in search_text
            row.setVisible(visible)
            if visible:
                visible_groups.add(group_box)

        for _, _, group_box in self._rows:
            group_box.setVisible(group_box in visible_groups)
