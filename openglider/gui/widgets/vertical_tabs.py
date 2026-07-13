from __future__ import annotations

from pathlib import Path

from openglider.gui.qt import QtWidgets, QtCore

_SIDEBAR_STYLE = (Path(__file__).parent / "vertical_tabs.qss").read_text()


class VerticalTabs(QtWidgets.QWidget):
    """A sidebar-style tab container with a QListWidget navigator on the left
    and a QStackedWidget for the content on the right."""

    currentChanged = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self._sidebar = QtWidgets.QListWidget()
        self._sidebar.setStyleSheet(_SIDEBAR_STYLE)
        self._sidebar.setFixedWidth(130)
        self._sidebar.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._sidebar)

        self._stack = QtWidgets.QStackedWidget()
        layout.addWidget(self._stack)

        self._sidebar.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._sidebar.currentRowChanged.connect(self.currentChanged)

    def addTab(self, widget: QtWidgets.QWidget, label: str) -> int:
        self._sidebar.addItem(label)
        index = self._stack.addWidget(widget)
        if self._stack.count() == 1:
            self._sidebar.setCurrentRow(0)
        return index

    def currentIndex(self) -> int:
        return self._sidebar.currentRow()

    def setCurrentIndex(self, index: int) -> None:
        self._sidebar.setCurrentRow(index)

    def widget(self, index: int) -> QtWidgets.QWidget | None:
        return self._stack.widget(index)

    def count(self) -> int:
        return self._stack.count()
