from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar
import logging
import asyncio

from openglider.utils.types import expect_value
from openglider.gui.qt import QtWidgets, QtCore
from openglider.gui.icons import icon

from openglider.utils.tasks import TaskQueue, Task
from openglider.gui.views.window import Window

if TYPE_CHECKING:
    from openglider.gui.app.main_window import MainWindow


logger = logging.getLogger(__name__)


Td = QtWidgets.QTableWidgetItem
TaskType = TypeVar("TaskType", bound=Task)

class TaskWindow(Window, Generic[TaskType]):
    task: TaskType
    def __init__(self, app: MainWindow, task: TaskType):
        self.task = task
        super().__init__(app)


class QTaskListWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, app: MainWindow, task: Task, view: type[TaskWindow] | None):
        super().__init__(parent)
        self.task = task
        self.app = app
        self.view_class = view

        self.setLayout(QtWidgets.QHBoxLayout())
        self.label_status = QtWidgets.QLabel()
        self.label_name = QtWidgets.QLabel(self.task.get_name())
        self.label_runtime = QtWidgets.QLabel()

        self.button_view = QtWidgets.QToolButton()
        self.button_view.setIcon(icon("fa.plus"))
        

        if self.view_class is None:
            self.button_view.setDisabled(True)
        else:
            self.button_view.clicked.connect(self.open_widget)

        expect_value(self.layout()).addWidget(self.label_status)
        expect_value(self.layout()).addWidget(self.label_name)
        expect_value(self.layout()).addWidget(self.label_runtime)
        expect_value(self.layout()).addWidget(self.button_view)

        self.update()
    
    def update(self, *args: Any, **kwargs: Any) -> None:
        button = "fa.database"
        if self.task.finished:
            button = "fa.check"
        elif self.task.running:
            button = "fa.play"

        if self.task.failed:
            button = "fa.thumbs-down"

        _icon = icon(button)
        
        self.label_status.setPixmap(_icon.pixmap(QtCore.QSize(40, 40)))

        self.label_runtime.setText(self.task.runtime())
    
    def open_widget(self) -> None:
        if self.view_class is not None:
            view = self.view_class(self.app, self.task)
        
            self.app.show_tab(view)
        


class QTaskEntry(QtWidgets.QListWidgetItem):
    def __init__(self, parent: QtWidgets.QWidget, app: MainWindow, task: Task, view: type[TaskWindow] | None):
        super().__init__()
        self.app = app
        self.task = task
        self.widget = QTaskListWidget(parent, app, task, view)

        self.setSizeHint(self.widget.sizeHint())

    def update(self) -> None:
        self.widget.update()





class QTaskQueue(QtWidgets.QWidget):
    tasks: list[QTaskEntry]

    app: MainWindow
    queue: TaskQueue

    def __init__(self, app: MainWindow, queue: TaskQueue):
        super().__init__()
        self.app = app
        self.queue = queue
    
        self.setLayout(QtWidgets.QVBoxLayout())

        self.list = QtWidgets.QListWidget(self)
        self.list.setDragEnabled(True)
        
        expect_value(self.layout()).addWidget(self.list)
        self.update_task = asyncio.ensure_future(self._update())

        self.tasks = []

    def append(self, task: Task, view: type[TaskWindow] | None = None) -> None:
        list_entry = QTaskEntry(self.list, self.app, task, view)

        self.tasks.append(list_entry)
        self.list.addItem(list_entry)
        self.list.setItemWidget(list_entry, list_entry.widget)

        self.queue.tasks.append(task)
        # self.app.show_tab(self)

    async def _update(self) -> None:
        while True:
            for entry in self.tasks:
                entry.update()
            await asyncio.sleep(1)

    def shutdown(self) -> None:
        if self.update_task.done():
            return
        self.update_task.cancel()

    def close(self, *args: Any, **kwargs: Any) -> None:  # type: ignore
        self.shutdown()
        super().close(*args, **kwargs)


