from __future__ import annotations

from typing import TYPE_CHECKING, Any
from openglider.utils.colors import Color
import pyqtgraph
import openglider.rs

from openglider.glider.project import GliderProject
from openglider.glider.parametric.arc import ArcCurve, LeparaglidingArc, SplineArc
from openglider.gui.qt import QtWidgets, QtCore
from openglider.gui.views_2d import Canvas, DraggableLine
from openglider.gui.wizzards.base import GliderSelectionWizard
from openglider.gui.views_2d.arc import Arc2D

if TYPE_CHECKING:
    from openglider.gui.app.main_window import MainWindow

class ArcInput(Canvas):
    arcs: list[Arc2D]

    locked_aspect_ratio = True

    def __init__(self, project: GliderProject):
        super().__init__(parent=None)
        self.project = project

        #self.arc, self.x_values = Arc2D.get_normalized_arc(self.project)

        self.arc_2d = Arc2D(self.project, Color(255, 255, 255), 160)

        self.arcs = []
        self.arc_diffs: list[Any] = []
        self.addItem(self.arc_2d)

        self.arc_curve = DraggableLine(self.project.glider.arc.curve.controlpoints.nodes)
        self.normalize_cp()

        self.arc_curve.on_node_move.append(self.on_node_move)
        self.arc_curve.on_node_release.append(self.on_node_release)

        self.addItem(self.arc_curve)
        self.diff_widget = pyqtgraph.PlotWidget()
        self.diff_plot = self.diff_widget.plot()

        self.diff_plot.setData(**self.get_diff(self.project))

    def draw_arcs(self, arcs: list[tuple[GliderProject, Color]], clear: bool=True) -> None:
        if clear:
            for arc in self.arcs:
                self.removeItem(arc)
            self.arcs = []

        for project, color in arcs:
            arc_2d = Arc2D(project, color, 140)
            self.addItem(arc_2d)
            self.arcs.append(arc_2d)

        self.update()


        for arc in self.arc_diffs:
            self.diff_widget.removeItem(arc)
        self.arc_diffs = []

        for project, color in arcs:
            plot = self.diff_widget.plot()
            plot.setPen(*color)

            plot.setData(**self.get_diff(project))
            self.arc_diffs.append(plot)
    
    @staticmethod
    def get_diff(project: GliderProject) -> dict[str, list[float]]:
        x_values = project.glider.shape.rib_x_values
        y_values = project.glider.arc.get_cell_angles(x_values, rad=False)

        y2 = [y1-y2 for y2, y1 in zip(y_values[:-1], y_values[1:])]

        if y_values[0] != 0:
            y2.insert(0, y_values[0])
            x_values = x_values[1:]
        else:
            y2.insert(0, y_values[1])
        
        line = openglider.rs.vector.PolyLine2D(list(zip(x_values, y2)))
        line_normalized = line.scale(openglider.rs.vector.Vector2D([1/x_values[-1], 1]))

        p0 = openglider.rs.vector.Vector2D([0,0]) 
        p1 = openglider.rs.vector.Vector2D([0, 1])

        if hasattr(project.glider.arc.curve, "get_curvature"):
            interpolation = project.glider.arc.curve.get_curvature(100)  # type: ignore
            line_mirrored = openglider.rs.vector.PolyLine2D(interpolation.nodes).mirror(p0, p1).reverse()
        else:
            line_mirrored = line_normalized.mirror(p0, p1).reverse()

        merged = openglider.rs.vector.PolyLine2D(line_mirrored.nodes + line_normalized.nodes)
        
        data = {
            "x": [p[0] for p in merged.nodes],
            "y": [p[1] for p in merged.nodes]
        }

        return data


    def normalize_cp(self) -> None:
        normalized_arc, x_values = self.arc_2d.get_normalized_arc()
        self.arc_curve.set_controlpoints(normalized_arc.curve.controlpoints.nodes)

    def on_node_move(self, curve: DraggableLine, event: Any) -> None:
        node_index = curve.drag_node_index
        curve.data["pos"][node_index][0] = max(0, curve.data["pos"][node_index][0])

        self.project.glider.arc.curve.controlpoints = curve.controlpoints
        self.arc_2d.update_arc()

        self.update()

    def on_node_release(self, curve: DraggableLine, event: Any) -> None:
        self.normalize_cp()
        self.arc_2d.update_arc()
        self.diff_plot.setData(**self.get_diff(self.project))

        self.update()

    def refresh_from_arc(self) -> None:
        """Refresh the display after the arc curve was replaced externally
        (e.g. by the generator panel)."""
        self.arc_2d.update_arc()
        self.normalize_cp()
        self.diff_plot.setData(**self.get_diff(self.project))
        self.update()

    def set_handle_visible(self, visible: bool) -> None:
        """Show or hide the draggable arc control-point overlay."""
        self.arc_curve.setVisible(visible)


class ArcGeneratorPanel(QtWidgets.QWidget):
    """Arc shape generator with three modes: Vault Ellipse, Vault Circles, Spline.

    Each mode produces a fresh arc curve from analytical parameters and writes it
    onto ``project.glider.arc`` (both the curve and ``arc_generator_params``).
    The existing draggable-curve editor then displays the generated arc.
    """

    params_changed = QtCore.Signal()

    MODE_VAULT_ELLIPSE = 0
    MODE_VAULT_CIRCLES = 1
    MODE_SPLINE = 2

    MODE_NAMES = {
        0: "vault_ellipse",
        1: "vault_circles",
        2: "spline",
    }
    NAME_TO_MODE = {v: k for k, v in MODE_NAMES.items()}

    def __init__(self, project: GliderProject):
        super().__init__()
        self.project = project
        self._updating = False
        # Snapshot of the arc angles captured when entering spline mode, so that
        # changing the control-point count always refits from the same source.
        self._spline_source_angles: list[float] | None = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        label = QtWidgets.QLabel("Arc Shape Generator")
        label.setStyleSheet("font-weight: bold;")
        layout.addWidget(label)

        mode_layout = QtWidgets.QHBoxLayout()
        mode_layout.addWidget(QtWidgets.QLabel("Mode:"))
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Vault Ellipse")
        self.mode_combo.addItem("Vault Circles")
        self.mode_combo.addItem("Spline")
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack)

        # ── Mode 0: Vault Ellipse (LE Paragliding Type 1) ──
        m0 = QtWidgets.QWidget()
        m0_layout = QtWidgets.QVBoxLayout(m0)
        m0_layout.setContentsMargins(0, 0, 0, 0)
        m0_desc = QtWidgets.QLabel(
            "Ellipse with cosine tip modification\n"
            "(LE Paragliding pre-processor Vault Type 1)"
        )
        m0_desc.setStyleSheet("color: gray; font-size: 10px;")
        m0_desc.setWordWrap(True)
        m0_layout.addWidget(m0_desc)
        self.ve_a = self._make_slider_row(m0_layout, "a (horiz):", 0.1, 2.0, 0.78, 2)
        self.ve_b = self._make_slider_row(m0_layout, "b (vert):", 0.01, 1.0, 0.44, 2)
        self.ve_x1 = self._make_slider_row(m0_layout, "x1 (mod start):", 0.1, 0.99, 0.53, 2)
        self.ve_c1 = self._make_slider_row(m0_layout, "c1 (mod amp):", 0.0, 0.3, 0.043, 3)
        m0_layout.addStretch()
        self.stack.addWidget(m0)

        # ── Mode 1: Vault Circles (LE Paragliding Type 2) ──
        m1 = QtWidgets.QWidget()
        m1_layout = QtWidgets.QVBoxLayout(m1)
        m1_layout.setContentsMargins(0, 0, 0, 0)
        m1_desc = QtWidgets.QLabel(
            "4 successive tangent circles\n(LE Paragliding pre-processor Vault Type 2)"
        )
        m1_desc.setStyleSheet("color: gray; font-size: 10px;")
        m1_desc.setWordWrap(True)
        m1_layout.addWidget(m1_desc)

        circle_grid = QtWidgets.QGridLayout()
        circle_grid.addWidget(QtWidgets.QLabel(""), 0, 0)
        circle_grid.addWidget(QtWidgets.QLabel("Radius"), 0, 1)
        circle_grid.addWidget(QtWidgets.QLabel("Angle"), 0, 2)

        self.vc_radii: list[QtWidgets.QDoubleSpinBox] = []
        self.vc_angles: list[QtWidgets.QDoubleSpinBox] = []
        default_radii = [640.56, 480.47, 229.50, 99.26]
        default_angles = [20.35, 21.367, 18.925, 28.349]
        for i in range(4):
            circle_grid.addWidget(QtWidgets.QLabel(f"Circle {i + 1}:"), i + 1, 0)

            r_spin = QtWidgets.QDoubleSpinBox()
            r_spin.setRange(0.01, 9999.0)
            r_spin.setDecimals(2)
            r_spin.setSingleStep(1.0)
            r_spin.setValue(default_radii[i])
            r_spin.setFixedWidth(80)
            r_spin.valueChanged.connect(self._on_value_changed)
            circle_grid.addWidget(r_spin, i + 1, 1)
            self.vc_radii.append(r_spin)

            a_spin = QtWidgets.QDoubleSpinBox()
            a_spin.setRange(0.0, 90.0)
            a_spin.setDecimals(3)
            a_spin.setSingleStep(0.1)
            a_spin.setValue(default_angles[i])
            a_spin.setFixedWidth(80)
            a_spin.setSuffix("°")
            a_spin.valueChanged.connect(self._on_value_changed)
            circle_grid.addWidget(a_spin, i + 1, 2)
            self.vc_angles.append(a_spin)

        m1_layout.addLayout(circle_grid)
        m1_layout.addStretch()
        self.stack.addWidget(m1)

        # ── Mode 2: Spline ──
        m2 = QtWidgets.QWidget()
        m2_layout = QtWidgets.QVBoxLayout(m2)
        m2_layout.setContentsMargins(0, 0, 0, 0)
        sp_label = QtWidgets.QLabel(
            "Refits the current arc as a smooth spline.\n"
            "Fewer control points = smoother curve."
        )
        sp_label.setStyleSheet("color: gray; font-size: 10px;")
        sp_label.setWordWrap(True)
        m2_layout.addWidget(sp_label)
        cp_layout = QtWidgets.QHBoxLayout()
        cp_layout.addWidget(QtWidgets.QLabel("Control points:"))
        self.sp_num_cp = QtWidgets.QSpinBox()
        self.sp_num_cp.setRange(3, 20)
        self.sp_num_cp.setValue(4)
        self.sp_num_cp.valueChanged.connect(self._on_spline_changed)
        cp_layout.addWidget(self.sp_num_cp)
        cp_layout.addStretch()
        m2_layout.addLayout(cp_layout)
        m2_layout.addStretch()
        self.stack.addWidget(m2)

        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self._restore_from_params()

    def _make_slider_row(
        self,
        parent_layout: QtWidgets.QVBoxLayout,
        label: str,
        lo: float,
        hi: float,
        default: float,
        decimals: int,
    ) -> QtWidgets.QDoubleSpinBox:
        """Create a label + spinbox + horizontal slider row. Returns the spinbox."""
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label))

        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(decimals)
        spin.setSingleStep(10 ** (-decimals))
        spin.setValue(default)
        spin.setFixedWidth(65)
        row.addWidget(spin)

        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        scale = 10**decimals
        slider.setRange(int(lo * scale), int(hi * scale))
        slider.setValue(int(default * scale))
        row.addWidget(slider)

        parent_layout.addLayout(row)

        slider.valueChanged.connect(lambda v, s=spin, sc=scale: s.setValue(v / sc))
        spin.valueChanged.connect(
            lambda v, sl=slider, sc=scale: (
                sl.blockSignals(True),
                sl.setValue(int(v * sc)),
                sl.blockSignals(False),
            )
        )
        spin.valueChanged.connect(self._on_value_changed)
        return spin

    def _restore_from_params(self) -> None:
        """Restore widget values + mode from the current arc's type, without
        regenerating (the stored arc curve is authoritative)."""
        arc = self.project.glider.arc
        params = arc.params if isinstance(arc, LeparaglidingArc) else None
        mode_idx = self.NAME_TO_MODE.get(arc.mode) if isinstance(arc, LeparaglidingArc) else None
        if mode_idx is None:
            # Plain spline / explicit arc: default to spline mode so the draggable
            # control points stay visible and the loaded arc can be fine-tuned.
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(self.MODE_SPLINE)
            self.stack.setCurrentIndex(self.MODE_SPLINE)
            self.mode_combo.blockSignals(False)
            return

        assert params is not None
        self._updating = True
        if mode_idx == self.MODE_VAULT_ELLIPSE:
            self.ve_a.setValue(float(params.get("a_ratio", 0.78)))
            self.ve_b.setValue(float(params.get("b_ratio", 0.44)))
            self.ve_x1.setValue(float(params.get("x1_ratio", 0.53)))
            self.ve_c1.setValue(float(params.get("c1_ratio", 0.043)))
        elif mode_idx == self.MODE_VAULT_CIRCLES:
            radii = params.get("radii", [640.56, 480.47, 229.50, 99.26])
            angles = params.get("arc_angles", [20.35, 21.367, 18.925, 28.349])
            if isinstance(radii, list) and isinstance(angles, list):
                for i in range(min(4, len(radii), len(self.vc_radii))):
                    self.vc_radii[i].setValue(float(radii[i]))
                for i in range(min(4, len(angles), len(self.vc_angles))):
                    self.vc_angles[i].setValue(float(angles[i]))

        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(mode_idx)
        self.stack.setCurrentIndex(mode_idx)
        self.mode_combo.blockSignals(False)
        self._updating = False

    def _on_mode_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == self.MODE_SPLINE:
            x_values = self.project.glider.shape.rib_x_values
            self._spline_source_angles = list(
                self.project.glider.arc.get_cell_angles(x_values, rad=True)
            )
            self._on_spline_changed()
        else:
            self._spline_source_angles = None
            self._on_value_changed()

    def _on_value_changed(self) -> None:
        if self._updating:
            return
        self._updating = True

        x_values = self.project.glider.shape.rib_x_values
        mode = self.mode_combo.currentIndex()

        if mode == self.MODE_VAULT_ELLIPSE:
            new_arc: SplineArc = ArcCurve.from_vault_ellipse(
                x_values,
                a_ratio=self.ve_a.value(),
                b_ratio=self.ve_b.value(),
                x1_ratio=self.ve_x1.value(),
                c1_ratio=self.ve_c1.value(),
            )
        elif mode == self.MODE_VAULT_CIRCLES:
            radii = [sb.value() for sb in self.vc_radii]
            angles = [sb.value() for sb in self.vc_angles]
            new_arc = ArcCurve.from_vault_circles(x_values, radii=radii, arc_angles=angles)
        else:
            self._updating = False
            return

        self.project.glider.arc = new_arc
        self._updating = False
        self.params_changed.emit()

    def _on_spline_changed(self) -> None:
        if self._updating or self._spline_source_angles is None:
            return
        self._updating = True

        x_values = self.project.glider.shape.rib_x_values
        num_cp = self.sp_num_cp.value()
        curve = SplineArc._fit_curve(self._spline_source_angles, x_values, num_cp=num_cp)
        self.project.glider.arc = SplineArc(curve)
        self._updating = False
        self.params_changed.emit()


class ArcWidget(GliderSelectionWizard):
    def __init__(self, app: MainWindow, project: GliderProject):
        super().__init__(app=app, project=project)
        self.arc_input = ArcInput(self.project)

        self.main_widget.addWidget(self.arc_input.get_widget())
        self.main_widget.addWidget(self.arc_input.diff_widget)

        self.main_widget.setSizes([700, 300])

        self.generator_panel = ArcGeneratorPanel(self.project)
        self.generator_panel.params_changed.connect(self._on_generator_changed)
        self.generator_panel.mode_combo.currentIndexChanged.connect(self._update_handle_visibility)
        self.right_widget_layout.insertWidget(0, self.generator_panel)

        self._update_handle_visibility()
        self._selection_changed()

    def _on_generator_changed(self) -> None:
        self.arc_input.refresh_from_arc()

    def _update_handle_visibility(self) -> None:
        """Draggable arc control points are only meaningful in Spline mode; the
        vault modes define the arc parametrically."""
        is_spline = self.generator_panel.mode_combo.currentIndex() == ArcGeneratorPanel.MODE_SPLINE
        self.arc_input.set_handle_visible(is_spline)

    def selection_changed(self, selected: list[tuple[GliderProject, Color]]) -> None:
        self.arc_input.draw_arcs(selected)

    def apply(self, update: bool=True) -> None:
        glider = self.project.get_glider_3d()
        #self.project.glider.arc.curve.controlpoints = self.arc_input.arc.curve.controlpoints
        self.project.glider.rescale_curves()
        self.project.glider.apply_shape_and_arc(glider)
        glider.lineset.recalc(glider=glider)
        super().apply(False)

