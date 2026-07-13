from __future__ import annotations

from openglider.gui.qt import QtWidgets
from openglider.gui.widgets.vertical_tabs import VerticalTabs
from openglider.gui.views.help.dto import DtoHelpView
from openglider.gui.views.help.cloth_material import ClothMaterialView
from openglider.gui.views.help.line_material import LineMaterialView


class HelpView(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        tabs = VerticalTabs(self)
        tabs.addTab(DtoHelpView(), "DTO Helper")
        tabs.addTab(ClothMaterialView(), "Cloth")
        tabs.addTab(LineMaterialView(), "Lines")
        layout.addWidget(tabs)
