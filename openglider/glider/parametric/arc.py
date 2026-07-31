from __future__ import annotations

import copy
import math
from typing import Any

import openglider.rs
import numpy as np

from openglider.utils.types import SymmetricCurveType
from openglider.vector.polygon import CirclePart


class SplineArc:
    """
    Arc defined by a symmetric spline curve.

    This is the *compiled* representation every consumer uses (via ``.curve``)
    and the base class for the parametric arc variants (``LeparaglidingArc``,
    ``ExplicitArc``). Those subclasses carry an editable source (vault params /
    per-cell angles) and derive the same ``.curve`` from it.
    """
    num_interpolation_points = 100
    _x_tolerance = 1e-8

    def __init__(self, curve: SymmetricCurveType) -> None:
        self.curve = curve

    def __json__(self) -> dict[str, Any]:
        return {"curve": self.curve}

    def copy(self) -> SplineArc:
        return copy.deepcopy(self)

    @staticmethod
    def has_center_cell(x_values: list[float]) -> bool:
        return abs(x_values[0]) > SplineArc._x_tolerance

    def get_arc_positions(self, x_values: list[float]) -> openglider.rs.vector.PolyLine2D:
        """
        calculate y/z positions vor the arc-curve, given a shape's rib-x-values

        :param x_values:
        :return: [p0, p1,...]
        """
        # Symmetric-Bezier-> start from 0.5
        positions = []

        x_values = [0.0 if abs(x) <= self._x_tolerance else abs(x) for x in x_values]

        arc_curve = self.curve.get_sequence(self.num_interpolation_points)
        arc_curve_length = arc_curve.get_length()
        scale_factor = arc_curve_length / x_values[-1]
        _positions = [arc_curve.walk(0, x * scale_factor) for x in x_values]
        positions = [arc_curve.get(p) for p in _positions]

        if not self.has_center_cell(x_values):
            scale_center = openglider.rs.vector.Vector2D([0, 1])
        else:
            scale_center = openglider.rs.vector.Vector2D([-1, 1])

        positions[0] = positions[0] * scale_center

        return openglider.rs.vector.PolyLine2D(positions)

    def get_cell_angles(self, x_values: list[float], rad: bool=True) -> list[float]:
        """
        Calculate cell rotation angles given a shape's rib-x-values
        :param x_values:
        :return: [rib_angles]
        """
        arc_positions = self.get_arc_positions(x_values)
        arc_positions_lst = list(arc_positions)
        cell_angles = []


        for l, r in zip(arc_positions_lst[:-1], arc_positions_lst[1:]):
            d = r - l
            angle = np.arctan2(-d[1], d[0])
            if rad:
                cell_angles.append(angle)
            else:
                cell_angles.append(angle * 180 / np.pi)

        if self.has_center_cell(x_values):
            # center cell is always straight
            cell_angles[0] = 0.

        return cell_angles

    @classmethod
    def from_cell_angles(cls, angles: list[float], x_values: list[float], rad: bool=True) -> SplineArc:
        last_pos = openglider.rs.vector.Vector2D([0,0])
        last_x = 0.
        nodes = []
        for i, x in enumerate(x_values):
            angle = angles[i]
            l = x - last_x
            d = openglider.rs.vector.Vector2D([math.cos(angle), -math.sin(angle)])
            last_pos = last_pos + d * l
            last_x = x

            nodes.append(last_pos)

        right_curve = openglider.rs.vector.PolyLine2D(nodes)
        left_curve = right_curve.mirror()

        curve = openglider.rs.vector.PolyLine2D(left_curve.nodes[:-1] + right_curve.nodes)

        spline = openglider.rs.spline.SymmetricBSplineCurve.fit(curve, 8) # type: ignore

        return SplineArc(spline)

    # ── curve compilation from per-cell angles ──────────────────────
    #
    # The generators reproduce the analytical arc shapes from the LE Paragliding
    # pre-processor. Their math produces a per-cell angle list (one value per
    # cell, centre outward, centre cell = 0). ``_fit_curve`` converts such a list
    # into this codebase's spline representation by walking the right half and
    # fitting a SymmetricBSplineCurve.

    @staticmethod
    def _fit_curve(
        all_angles_rad: list[float], x_values: list[float], num_cp: int | None = None
    ) -> SymmetricCurveType:
        """Walk per-cell angles into right-half [y, z] positions and fit a
        symmetric BSpline; returns the fitted curve.

        :param all_angles_rad: one angle per cell (centre outward, incl. centre cell)
        :param x_values: shape rib-x-values (may start negative for a centre cell)
        """
        x_abs = [abs(x) for x in x_values]
        # Start at the symmetry centre so the fitted right half is anchored at
        # the origin (matters most for gliders without a centre cell, where the
        # centre rib sits exactly at x=0; it roughly halves the fit error).
        positions: list[list[float]] = [[0.0, 0.0]]
        y = z = 0.0
        for i, angle in enumerate(all_angles_rad):
            d = x_abs[i + 1] - x_abs[i]
            y += math.cos(angle) * d
            z -= math.sin(angle) * d
            positions.append([y, z])

        line = openglider.rs.vector.PolyLine2D(positions)

        if num_cp is None:
            num_cp = max(3, min(8, len(positions) - 1))
        num_cp = max(3, min(num_cp, len(positions)))

        # SymmetricBSplineCurve.fit accepts 3 <= num_cp <= len(points); degenerate
        # inputs (e.g. a zero-span centre cell duplicate) can still reject the
        # upper end, so decrement until a fit succeeds.
        spline = None
        for n in range(num_cp, 2, -1):
            try:
                spline = openglider.rs.spline.SymmetricBSplineCurve.fit(line, n)  # type: ignore
                break
            except Exception:  # noqa: BLE001 - fall back to fewer control points
                continue
        if spline is None:
            spline = openglider.rs.spline.SymmetricBSplineCurve.fit(line, 3)  # type: ignore

        return spline

    @staticmethod
    def _cell_info(x_values: list[float]) -> tuple[bool, list[float], float, int]:
        """Return (has_center, x_abs, half_span, num_stored)."""
        has_center = x_values[0] != 0
        x_abs = [abs(x) for x in x_values]
        half_span = x_abs[-1]
        num_cells = len(x_values) - 1
        num_stored = num_cells - 1 if has_center else num_cells
        return has_center, x_abs, half_span, num_stored

    @staticmethod
    def _vault_ellipse_angles(
        x_values: list[float],
        a_ratio: float = 0.78,
        b_ratio: float = 0.44,
        x1_ratio: float = 0.53,
        c1_ratio: float = 0.043,
    ) -> list[float]:
        """Per-cell angles (rad, centre outward, incl. centre cell) for a vault
        defined by an ellipse with a cosine tip modification (LE Paragliding
        pre-processor Vault Type 1). Ratios are fractions of the half-span."""
        _has_center, x_abs, half_span, _num_stored = SplineArc._cell_info(x_values)
        num_cells = len(x_values) - 1
        if half_span == 0 or num_cells == 0:
            return [0.0] * max(num_cells, 1)

        a1 = a_ratio * half_span
        b1 = b_ratio * half_span
        x1 = x1_ratio * half_span
        c1 = c1_ratio * half_span

        pi = math.pi
        n_main = 300  # ellipse sampling points
        n_mod = 100  # cosine modification zone points

        vault_x: list[float] = []
        vault_y: list[float] = []
        jcontrol = False

        for i in range(n_main):
            theta1 = (pi / 2.0) * i / n_main
            xq = a1 * math.sin(theta1)
            yq = b1 * math.sqrt(max(1.0 - (xq * xq) / (a1 * a1), 0.0))

            if xq < x1:
                vault_x.append(xq)
                vault_y.append(yq)

            if xq >= x1 and not jcontrol:
                y1 = b1 * math.sqrt(max(1.0 - (x1 * x1) / (a1 * a1), 0.0))
                dy = y1 / n_mod
                for j in range(n_mod):
                    yq_m = y1 - dy * j
                    t_arg = max(1.0 - (yq_m * yq_m) / (b1 * b1), 0.0)
                    cos_arg = (y1 - yq_m) * pi / y1 if y1 > 0 else 0.0
                    xq_m = a1 * math.sqrt(t_arg) + c1 * (1.0 - (math.cos(cos_arg) + 1.0) * 0.5)
                    vault_x.append(xq_m)
                    vault_y.append(yq_m)
                vault_x.append(a1 + c1)
                vault_y.append(0.0)
                jcontrol = True

        return SplineArc._angles_from_vault_contour(vault_x, vault_y, x_abs, half_span)

    @staticmethod
    def _vault_circles_angles(
        x_values: list[float],
        radii: list[float] | None = None,
        arc_angles: list[float] | None = None,
    ) -> list[float]:
        """Per-cell angles (rad, centre outward, incl. centre cell) for a vault
        of successive tangent circles (LE Paragliding pre-processor Vault Type 2).
        Radius units are arbitrary — only their ratios matter."""
        _has_center, x_abs, half_span, _num_stored = SplineArc._cell_info(x_values)
        num_cells = len(x_values) - 1
        if half_span == 0 or num_cells == 0:
            return [0.0] * max(num_cells, 1)

        if radii is None:
            radii = [640.56, 480.47, 229.50, 99.26]
        if arc_angles is None:
            arc_angles = [20.35, 21.367, 18.925, 28.349]

        abs_radii = [r * half_span for r in radii]
        n_circles = min(len(abs_radii), len(arc_angles))

        pi = math.pi
        pts_per_circle = 100

        centers_x = [0.0] * n_circles
        centers_y = [0.0] * n_circles
        cumulative_angle = 0.0
        for i in range(1, n_circles):
            cumulative_angle += arc_angles[i - 1]
            dx = (abs_radii[i - 1] - abs_radii[i]) * math.sin(cumulative_angle * pi / 180.0)
            dy = (abs_radii[i - 1] - abs_radii[i]) * math.cos(cumulative_angle * pi / 180.0)
            centers_x[i] = centers_x[i - 1] + dx
            centers_y[i] = centers_y[i - 1] + dy

        vault_x: list[float] = []
        vault_y: list[float] = []
        start_angle = 0.0
        for ci in range(n_circles):
            end_angle = start_angle + arc_angles[ci]
            step = arc_angles[ci] / pts_per_circle
            angle = start_angle
            while angle < end_angle - step * 0.5:
                vault_x.append(centers_x[ci] + abs_radii[ci] * math.sin(angle * pi / 180.0))
                vault_y.append(centers_y[ci] + abs_radii[ci] * math.cos(angle * pi / 180.0))
                angle += step
            start_angle = end_angle

        final_angle = sum(arc_angles[:n_circles])
        vault_x.append(centers_x[n_circles - 1] + abs_radii[n_circles - 1] * math.sin(final_angle * pi / 180.0))
        vault_y.append(centers_y[n_circles - 1] + abs_radii[n_circles - 1] * math.cos(final_angle * pi / 180.0))

        # Translate so the tip is at y=0
        if vault_y:
            tip_y = vault_y[-1]
            vault_y = [vy - tip_y for vy in vault_y]

        return SplineArc._angles_from_vault_contour(vault_x, vault_y, x_abs, half_span)

    @staticmethod
    def _angles_from_vault_contour(
        vault_x: list[float], vault_y: list[float], x_abs: list[float], half_span: float
    ) -> list[float]:
        """Rescale a vault contour to the half-span and derive per-cell angles
        (radians, centre outward) by interpolating rib positions along it."""
        num_cells = len(x_abs) - 1
        if len(vault_x) < 2:
            return [0.0] * num_cells

        arc_lengths = [0.0]
        for k in range(len(vault_x) - 1):
            seg = math.sqrt((vault_x[k + 1] - vault_x[k]) ** 2 + (vault_y[k + 1] - vault_y[k]) ** 2)
            arc_lengths.append(arc_lengths[-1] + seg)

        total_length = arc_lengths[-1]
        if total_length <= 0:
            return [0.0] * num_cells

        scale = half_span / total_length
        vault_x = [v * scale for v in vault_x]
        vault_y = [v * scale for v in vault_y]
        arc_lengths = [a * scale for a in arc_lengths]

        def interp_vault(arc_dist: float) -> tuple[float, float]:
            if arc_dist <= 0:
                return vault_x[0], vault_y[0]
            if arc_dist >= arc_lengths[-1]:
                return vault_x[-1], vault_y[-1]
            for k in range(len(arc_lengths) - 1):
                if arc_lengths[k] <= arc_dist <= arc_lengths[k + 1]:
                    seg_len = arc_lengths[k + 1] - arc_lengths[k]
                    if seg_len <= 0:
                        return vault_x[k], vault_y[k]
                    frac = (arc_dist - arc_lengths[k]) / seg_len
                    vx = vault_x[k] + frac * (vault_x[k + 1] - vault_x[k])
                    vy = vault_y[k] + frac * (vault_y[k + 1] - vault_y[k])
                    return vx, vy
            return vault_x[-1], vault_y[-1]

        rib_projected: list[float] = []
        rib_height: list[float] = []
        for x_val in x_abs:
            vx, vy = interp_vault(x_val)
            rib_projected.append(vx)
            rib_height.append(vy)

        angles: list[float] = []
        for i in range(len(x_abs) - 1):
            drop = rib_height[i] - rib_height[i + 1]
            dy = rib_projected[i + 1] - rib_projected[i]
            angles.append(math.atan2(drop, dy) if dy > 0 else 0.0)
        return angles

    # ── generator entry points ──────────────────────────────────────

    @classmethod
    def from_vault_ellipse(
        cls, x_values: list[float], a_ratio: float = 0.78, b_ratio: float = 0.44,
        x1_ratio: float = 0.53, c1_ratio: float = 0.043,
    ) -> LeparaglidingArc:
        return LeparaglidingArc.generate(
            x_values, "vault_ellipse",
            a_ratio=a_ratio, b_ratio=b_ratio, x1_ratio=x1_ratio, c1_ratio=c1_ratio,
        )

    @classmethod
    def from_vault_circles(
        cls, x_values: list[float], radii: list[float] | None = None,
        arc_angles: list[float] | None = None,
    ) -> LeparaglidingArc:
        return LeparaglidingArc.generate(
            x_values, "vault_circles",
            radii=radii if radii is not None else [640.56, 480.47, 229.50, 99.26],
            arc_angles=arc_angles if arc_angles is not None else [20.35, 21.367, 18.925, 28.349],
        )

    def resample_spline(self, x_values: list[float], num_cp: int) -> SplineArc:
        """Refit the current arc with ``num_cp`` control points (fewer = smoother).

        Reads the current per-cell angles and rebuilds a plain spline arc.
        """
        angles = self.get_cell_angles(x_values, rad=True)
        return SplineArc(SplineArc._fit_curve(angles, x_values, num_cp=num_cp))

    def get_rib_angles(self, x_values: list[float]) -> list[float]:
        """
        Calculate rib rotation angles given a shape's rib-x-values
        :param x_values:
        :return: [cell_angles]
        """
        cell_angles = self.get_cell_angles(x_values)
        rib_angles = []

        for cell_left, cell_right in zip(cell_angles[:-1], cell_angles[1:]):
            # rotation of the rib is the median of the left and right cell's rotation
            rib_angles.append((cell_left + cell_right)/2)

        # stabi rib -> same rotation as the last cell
        rib_angles.append(cell_angles[-1])

        if not self.has_center_cell(x_values):
            # center rib -> straight
            rib_angles.insert(0, 0.)
        else:
            rib_angles.insert(0, -rib_angles[0])

        return rib_angles

    def get_flattening(self, x_values: list[float]) -> float:
        arc_curve = self.get_arc_positions(x_values)
        span_projected = arc_curve.nodes[-1][0]
        return span_projected / arc_curve.get_length()

    def get_circle(self, n: int=50) -> openglider.rs.vector.PolyLine2D:
        p1, p2 = self.curve.get_sequence(1)
        p3 = p1 * openglider.rs.vector.Vector2D([-1, 1])
        return CirclePart(p1, p2, p3).get_sequence(n)


    def rescale(self, x_values: list[float]) -> None:
        positions = self.get_arc_positions(x_values)
        diff = openglider.rs.vector.Vector2D([0, -positions.nodes[0][1]])
        self.curve.controlpoints = openglider.rs.vector.PolyLine2D([p + diff for p in self.curve.controlpoints.nodes])

        arc_curve: openglider.rs.vector.PolyLine2D = self.curve.get_sequence(self.num_interpolation_points)
        arc_curve_length = arc_curve.get_length()
        scale_factor = x_values[-1] / arc_curve_length

        self.curve.controlpoints = openglider.rs.vector.PolyLine2D([p * scale_factor for p in self.curve.controlpoints.nodes])


class LeparaglidingArc(SplineArc):
    """Arc generated from LE-Paragliding vault parameters.

    Stores the ``mode`` (``vault_ellipse`` / ``vault_circles``) and its ``params``
    as the editable source; the ``.curve`` is derived (and kept, so consumers and
    JSON stay self-contained).
    """

    def __init__(self, curve: SymmetricCurveType, mode: str, params: dict[str, Any]) -> None:
        super().__init__(curve)
        self.mode = mode
        self.params = dict(params)

    def __json__(self) -> dict[str, Any]:
        return {"curve": self.curve, "mode": self.mode, "params": self.params}

    @classmethod
    def generate(cls, x_values: list[float], mode: str, **params: Any) -> LeparaglidingArc:
        """Compute the vault curve for the given shape rib-x-values + params."""
        if mode == "vault_ellipse":
            angles = SplineArc._vault_ellipse_angles(x_values, **params)
        elif mode == "vault_circles":
            angles = SplineArc._vault_circles_angles(x_values, **params)
        else:
            raise ValueError(f"unknown leparagliding arc mode: {mode!r}")
        curve = SplineArc._fit_curve(angles, x_values)
        return cls(curve, mode, params)


class ExplicitArc(SplineArc):
    """Arc defined by explicit per-cell angles.

    ``cell_angles`` are degrees for the right half, excluding the centre cell
    (matching the openglider-lines representation). The ``.curve`` is derived.
    """

    def __init__(self, curve: SymmetricCurveType, cell_angles: list[float]) -> None:
        super().__init__(curve)
        self.cell_angles = list(cell_angles)

    def __json__(self) -> dict[str, Any]:
        return {"curve": self.curve, "cell_angles": self.cell_angles}

    @classmethod
    def from_angles(cls, cell_angles: list[float], x_values: list[float]) -> ExplicitArc:
        """Build from right-half, centre-excluded angles in degrees."""
        has_center = SplineArc.has_center_cell(x_values)
        all_deg = ([0.0] + list(cell_angles)) if has_center else list(cell_angles)
        all_rad = [a * math.pi / 180.0 for a in all_deg]
        curve = SplineArc._fit_curve(all_rad, x_values)
        return cls(curve, cell_angles)

    @classmethod
    def from_current(cls, arc: SplineArc, x_values: list[float]) -> ExplicitArc:
        """Snapshot an existing arc's per-cell angles into an ExplicitArc."""
        all_deg = arc.get_cell_angles(x_values, rad=False)
        has_center = SplineArc.has_center_cell(x_values)
        cell_angles = [float(a) for a in (all_deg[1:] if has_center else all_deg)]
        return cls(arc.curve.copy(), cell_angles)


# Backward-compat alias: existing imports and old JSON (`_type: ArcCurve`).
ArcCurve = SplineArc
