from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, Any, Literal
from collections.abc import Callable

import euklid
from openglider.glider.parametric.shape import ParametricShape
from openglider.glider.project import GliderProject
from openglider.gui.qt import QtWidgets, QtCore
from openglider.gui.views_2d import Canvas, DraggableLine, Line2D
from openglider.gui.views_2d.canvas import LayoutGraphics
from openglider.gui.widgets import NumberInput
from openglider.gui.wizzards.base import GliderSelectionWizard
from openglider.plots.sketches.shapeplot import ShapePlot, ShapePlotConfig
from openglider.utils.colors import Color
from openglider.utils.dataclass import dataclass

if TYPE_CHECKING:
    from openglider.gui.app.main_window import MainWindow

logger = logging.getLogger(__name__)
# TODO: Show & change data: Area, Aspect ratio, Span, Tip Chord, Tip center


class ShapeInput(Canvas):
    locked_aspect_ratio = True

    glider_shape: ParametricShape
    on_change: list[Callable[[ParametricShape], None]]
    glider_shapes: list[LayoutGraphics]

    def __init__(self, project: GliderProject):
        super().__init__(parent=None)
        self.on_change = []
        self.project = project
        self.glider_shape = project.glider.shape

        self.front = DraggableLine(self.glider_shape.front_curve.controlpoints.nodes)
        self.back = DraggableLine(self.glider_shape.back_curve.controlpoints.nodes)

        self.front.on_node_move.append(self.on_node_move)
        self.back.on_node_move.append(self.on_node_move)

        self.front.on_node_release.append(self.on_node_release)
        self.back.on_node_release.append(self.on_node_release)

        self.addItem(self.front)
        self.addItem(self.back)
        self.config = ShapePlotConfig()

        self.shape_drawing = ShapePlot(self.project)
        dwg = self.shape_drawing.redraw(self.config)
        self.glider_shape_2d = LayoutGraphics(dwg)

        #self.shape_drawing.redraw(self.config)
        #self.glider_shape_2d = Shape2D(self.glider_shape, [], (255, 255, 255), 160)

        self.glider_shapes = []
        self.addItem(self.glider_shape_2d)

        self._update_curves()
        self.redraw()

    def draw_shapes(self, shapes: list[tuple[GliderProject, Color]], clear: bool=True, normalize_area: bool=False, normalize_span: bool=False) -> None:
        # list of glider projects
        if clear:
            for shape in self.glider_shapes:
                self.removeItem(shape)
            self.glider_shapes = []

        area = self.glider_shape.area
        span = self.glider_shape.span


        if normalize_area:
            self.config.scale_area = area
        elif normalize_span:
            self.config.scale_span = span

        for project, color in shapes:
            drawing = ShapePlot(project).redraw(self.config)

            dwg_pyqt = LayoutGraphics(drawing, color=Color(*color))  #, color=color

            self.addItem(dwg_pyqt)
            self.glider_shapes.append(dwg_pyqt)

        self.update()

    def on_node_move(self, curve: DraggableLine, event: Any) -> None:
        node_index = curve.drag_node_index
        if node_index is None:
            return

        curve.data["pos"][node_index][0] = max(0, curve.data["pos"][node_index][0])

        if node_index + 1 == len(curve.controlpoints):
            source = curve
            if curve is self.front:
                target = self.back
            else:
                target = self.front

            target.data["pos"][-1][0] = source.data["pos"][node_index][0]
            target.updateGraph()

        self.redraw()

        for f in self.on_change:
            f(self.glider_shape)
        self.update()
    
    def redraw(self) -> None:
        self.glider_shape.front_curve.controlpoints = self.front.controlpoints
        self.glider_shape.back_curve.controlpoints = self.back.controlpoints
        self.glider_shape.rescale_curves()

        self.removeItem(self.glider_shape_2d)
        self.glider_shape_2d = LayoutGraphics(self.shape_drawing.redraw(self.config, force=True))
        self.addItem(self.glider_shape_2d)


    def on_node_release(self, curve: DraggableLine, event: Any) -> None:
        self._update_curves()
        self.redraw()
        for f in self.on_change:
            f(self.glider_shape)
        self.update()
    
    def _update_curves(self) -> None:
        self.glider_shape._clean()
        self.front.set_controlpoints(self.glider_shape.front_curve.controlpoints.nodes)
        self.back.set_controlpoints(self.glider_shape.back_curve.controlpoints.nodes)
        #self.update()
            

class RibDistInput(Canvas):
    shapes: list[Line2D]
    on_change: list[Callable]

    def __init__(self, shape: ParametricShape):
        super().__init__()
        self.glider_shape = shape
        
        data = self.glider_shape.rib_distribution.get_sequence(100).nodes
        self.spline_curve = Line2D(data)
        self.addItem(self.spline_curve)

        self.curve = DraggableLine(self.glider_shape.rib_distribution.controlpoints.nodes)
        self.curve.on_node_move.append(self.on_node_move)
        self.curve.on_node_release.append(self.on_node_release)
        self.addItem(self.curve)

        self.linear = Line2D([
            euklid.vector.Vector2D([0,0]),
            euklid.vector.Vector2D([1, 1])
            ], dashed=True)
        self.addItem(self.linear)


        const_dist = euklid.vector.PolyLine2D(self.glider_shape.depth_integrated)
        self.constant_ar = Line2D(const_dist.nodes, dashed=True)
        self.addItem(self.constant_ar)

        self.on_change = []
        self.shapes = []

    def draw_shapes(self, projects: list[tuple[GliderProject, Color]], clear: bool=True) -> None:
        # list of glider projects
        if clear:
            for shape in self.shapes:
                self.removeItem(shape)
            self.shapes = []

        for project, color in projects:
            distribution = project.glider.shape.rib_distribution
            curve = Line2D(distribution.get_sequence(100).nodes, color=color)
            self.addItem(curve)
            self.shapes.append(curve)

        self.update()
    
    def on_node_move(self, curve: DraggableLine, event: Any) -> None:
        node_index = curve.drag_node_index

        curve.data["pos"][node_index][0] = max(0, curve.data["pos"][node_index][0])

        if node_index == len(curve.controlpoints) - 1:
            curve.data["pos"][node_index][0] = self.glider_shape.span
            curve.data["pos"][node_index][1] = 1
        elif node_index == 0:
            curve.data["pos"][0] = [0, 0]
        
        self.glider_shape.rib_distribution.controlpoints = self.curve.controlpoints
        self.spline_curve.curve_data = self.glider_shape.rib_distribution.get_sequence(100).nodes

        for f in self.on_change:
            f(curve, event)

    def on_node_release(self, curve: DraggableLine, event: Any) -> None:
        pass


@dataclass
class ShapeSettings:
    area: float
    aspect_ratio: float
    sweep: float
    cell_count: int
    scale: Literal["Area"] | Literal["Span"] | None = None
    zrot: bool = False
    scale_lines: bool = True

class ShapeSettingsWidget(QtWidgets.QWidget):
    changed = QtCore.Signal()
    def __init__(self, shape: ParametricShape):
        super().__init__()
        layout = QtWidgets.QVBoxLayout()

        self.settings = ShapeSettings(
            area=shape.area,
            aspect_ratio=shape.aspect_ratio,
            sweep=shape.get_sweep(),
            cell_count=shape.cell_num
        )

        self.setLayout(layout)

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)

        self.input_area = NumberInput(self, "Area", default=shape.area, places=2)
        self.input_aspect_ratio = NumberInput(self, "Aspect Ratio", default=shape.aspect_ratio, places=2)
        self.input_sweep = NumberInput(self, "Sweep", default=shape.get_sweep(), places=3)
        self.input_cell_count = NumberInput(self, "Cell Count", default=shape.cell_num, places=0)

        self.input_scale = QtWidgets.QComboBox(self)

        self.input_scale.insertItem(0, "No Scale")
        self.input_scale.insertItem(1, "Scale Area")
        self.input_scale.insertItem(2, "Scale Span")

        self.input_zrot = QtWidgets.QCheckBox()
        self.input_zrot.setText("Apply ZRot")
        self.input_zrot.setChecked(False)

        self.input_scale_lines = QtWidgets.QCheckBox()
        self.input_scale_lines.setText("Scale Lines")
        self.input_scale_lines.setChecked(self.settings.scale_lines)

        self.input_scale_lines.clicked.connect(self._update_settings)
        self.input_zrot.clicked.connect(self._update_settings)
        self.input_area.on_changed.append(self._update_settings)
        self.input_aspect_ratio.on_changed.append(self._update_settings)
        self.input_sweep.on_changed.append(self._update_settings)
        self.input_cell_count.on_changed.append(self._update_settings)

        layout.addWidget(self.input_area)
        layout.addWidget(self.input_aspect_ratio)
        layout.addWidget(self.input_sweep)
        layout.addWidget(self.input_cell_count)
        layout.addWidget(self.input_scale)
        layout.addWidget(self.input_zrot)
        layout.addWidget(self.input_scale_lines)

    def _update_settings(self, value: Any=None) -> None:
        self.settings.area = self.input_area.value
        self.settings.aspect_ratio = self.input_aspect_ratio.value
        self.settings.sweep = self.input_sweep.value
        self.settings.cell_count = int(self.input_cell_count.value)
        if self.normalize_area:
            self.settings.scale = "Area"
        elif self.normalize_span:
            self.settings.scale = "Span"
        else:
            self.settings.scale = None

        self.settings.zrot = self.input_zrot.isChecked()
        self.settings.scale_lines = self.input_scale_lines.isChecked()

        self.changed.emit()
    
    @property
    def normalize_area(self) -> bool:
        return self.input_scale.currentIndex() == 1
    
    @property
    def normalize_span(self) -> bool:
        return self.input_scale.currentIndex() == 2
    
    def update_zrot(self, value: bool=False) -> None:
        self.settings.zrot = not self.settings.zrot
        self.input_zrot.setChecked(self.settings.zrot)
        self.changed.emit()
    
    def update_shape(self, shape: ParametricShape) -> None:
        self.input_area.set_value(shape.area, propagate=True)
        self.input_aspect_ratio.set_value(shape.aspect_ratio, propagate=True)
        self.input_sweep.set_value(shape.get_sweep(), propagate=True)


class ShapeWizard(GliderSelectionWizard):
    def __init__(self, app: MainWindow, project: GliderProject):
        super().__init__(app=app, project=project)
        self.shape_backup = self.shape.copy()
        self.shape_input = ShapeInput(self.project)
        self.distribution_input = RibDistInput(self.project.glider.shape)
        self.distribution_input.on_change.append(lambda x, y: self.shape_input.redraw())
        #self.canvas_controls = CanvasControls(self.shape_input, vertical=True)
        self.main_widget.addWidget(self.distribution_input.get_widget())
        self.main_widget.addWidget(self.shape_input.get_widget())

        self.main_widget.setSizes([300, 700])

        self.shape_settings_widget = ShapeSettingsWidget(self.project.glider.shape)
        self.settings = self.shape_settings_widget.settings

        self.right_widget_layout.insertWidget(0, self.shape_settings_widget)
        #self.right_widget.layout().insertWidget(0, self.canvas_controls)
        self._selection_changed()

        self.shape_input.on_change.append(self.shape_settings_widget.update_shape)
        self.shape_input.on_change.append(self._selection_changed)

        self.shape_settings_widget.changed.connect(self.apply_settings)
    
    @property
    def shape(self) -> ParametricShape:
        return self.project.glider.shape

    def set_sweep(self, value: float) -> None:
        self.shape.set_sweep(value)
        self._update()
    
    def apply_settings(self) -> None:
        settings = self.shape_settings_widget.settings
        self.shape_input.config.apply_zrot = settings.zrot

        shape: ParametricShape = self.shape
        shape.set_area(settings.area)
        shape.set_aspect_ratio(settings.aspect_ratio)
        shape.cell_num = settings.cell_count

        if self.settings.sweep != settings.sweep:
            self.shape.set_sweep(settings.sweep)
        
        self.settings = dataclasses.replace(settings)
        self._update()

    def _update(self) -> None:
        self.shape_input.front.set_controlpoints(self.shape.front_curve.controlpoints.nodes)
        self.shape_input.back.set_controlpoints(self.shape.back_curve.controlpoints.nodes)
        self.shape_settings_widget.update_shape(self.shape)
        self.shape_input.redraw()

    def selection_changed(self, selected: list[tuple[GliderProject, Color]]) -> None:
        self.shape_input.draw_shapes(selected, normalize_area=self.shape_settings_widget.normalize_area, normalize_span=self.shape_settings_widget.normalize_span)
        self.distribution_input.draw_shapes(selected)

    def apply(self, update: bool=True) -> None:
        logging.info(f"new shape: {self.shape_backup.area} -> {self.shape.area}")
        shape = self.shape.copy()
        self.project.glider.shape = self.shape_backup

        if self.settings.scale_lines:
            # scale everything before putting the new shape
            # (which has an updated area already)
            self.project.glider.set_area(shape.area)

        self.project.glider.shape = shape
        self.project.glider.rescale_curves()

        #self.project.glider.apply_shape_and_arc(self.project.glider_3d)
        #self.project.glider_3d.lineset.recalc()
        super().apply(True)


