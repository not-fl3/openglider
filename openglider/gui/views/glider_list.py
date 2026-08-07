from __future__ import annotations
import asyncio

import os
import pathlib
import tempfile
from typing import Any
import logging

import openglider
from openglider.utils.types import expect_value
from openglider.gui.icons import icon
from openglider.glider.project import GliderProject
from openglider.gui.state.glider_list import GliderListItem, GliderList
from openglider.gui.qt import QtCore, QtGui, QtWidgets
from openglider.gui.widgets.list_select.item import ListWidgetItem, ListItemWidget
from openglider.gui.widgets.list_select.list import GenericListWidget

logger = logging.getLogger(__name__)

class GliderListWidgetItemWidget(ListItemWidget[GliderProject]):
    list_item: GliderListItem
    def __init__(self, parent: GliderListWidget, list_item: GliderListItem):
        super().__init__(parent, list_item)  # type: ignore

    
    def draw_buttons(self) -> None:
        super().draw_buttons()

        self.button_save = QtWidgets.QPushButton()
        self.button_save.setFixedSize(30, 30)
        self.button_save.setIcon(icon("fa.save"))
        self.button_save.clicked.connect(self.save)
        expect_value(self.layout()).addWidget(self.button_save)

        self.button_edit = QtWidgets.QPushButton()
        self.button_edit.setFixedSize(30, 30)
        self.button_edit.setIcon(icon("fa.edit"))
        self.button_edit.clicked.connect(self.edit)
        expect_value(self.layout()).addWidget(self.button_edit)

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        
        if self.list_item.failed:
            self.setStyleSheet("background-color: #880000;")
        else:
            self.setStyleSheet("background-color: none;")

    def edit(self) -> None:
        if not self.list_item.element.filename:
            tempdir = pathlib.Path(tempfile.gettempdir())
            filename = str(tempdir / f"{self.list_item.name}.ods")
            self.list_item.element.save(filename)
            self.list_item.is_temporary = True
        else:
            filename = self.list_item.element.filename

        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(filename))


    def save(self) -> str | None:
        filters = {
            "OpenGlider ods (*.ods)": ".ods",
            "OpenGlider json (*.json)": ".json",
            "OpenGlider markdown (*.og.md)": ".og.md"
        }
        filename, extension = QtWidgets.QFileDialog.getSaveFileName(
            self,
            f"Save {self.list_item.element.name}",
            self.list_item.element.name,
            filter=";;".join(filters.keys())
            )

        if not filename:
            return None

        if not filename.endswith((".json", ".ods", ".og.md")):
            filename += filters[extension]

        self.list_item.element.save(filename)
        self.update()
        return filename

class GliderListWidgetItem(ListWidgetItem[GliderProject, GliderListWidgetItemWidget]):
    # An item in the gliderlist
    def save(self) -> None:
        pass

    def edit(self) -> None:
        pass

    def get_widget(self, parent: GliderListWidget, element: GliderListItem) -> GliderListWidgetItemWidget:  # type: ignore
        widget = GliderListWidgetItemWidget(parent, element)

        widget.changed.connect(lambda: self._changed)
        widget.button_remove.clicked.connect(lambda: self._remove())
        #widget.button_reload.clicked.connect(lambda: self.parent)

        return widget

    def _remove(self) -> None:
        logger.info(f"remove glider: {self.item.name}")
        super()._remove()

class GliderListWidget(GenericListWidget[GliderProject, GliderListWidgetItemWidget]):
    WidgetType = GliderListWidgetItem

    def __init__(self, parent: QtWidgets.QWidget, selection_list: GliderList):
        super().__init__(parent, selection_list)
        asyncio.ensure_future(selection_list.watch(self))

    @staticmethod
    def import_glider(filename: str) -> GliderProject:
        name_lower = filename.lower()
        if name_lower.endswith(".ods"):
            glider = openglider.glider.project.GliderProject.import_ods(filename)
        elif name_lower.endswith(".og.md"):
            glider = openglider.glider.project.GliderProject.import_markdown(filename)
        else:
            glider = openglider.load(filename)

        if isinstance(glider, openglider.glider.ParametricGlider):
            project = GliderProject(glider, filename=filename)
        elif isinstance(glider, GliderProject):
            project = glider
            project.filename = filename
        else:
            raise ValueError(f"cannot import {glider}")
        
        if project.name is None:
            name = os.path.split(filename)[1]
            project.name = ".".join(name.split(".")[:-1])
        
        project.get_glider_3d().rename_parts()

        return project
