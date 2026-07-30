"""LE paragliding pre-processor (v1.6) shape parameters.

Replicates the leading-edge / trailing-edge / cell-distribution formulas from
``pre-processor.f`` (Laboratori d'envol).  See ``pre_docs/pre.html`` and
``pre_docs/pre-processor.f`` for the original documentation and source.

Coordinate system (matches the FORTRAN code, plotted as planview):
    x = span position from centre (0..xm)
    y = chord direction; LE at y=0 at centre and increases towards the tip
        as the leading edge sweeps back; TE is at y = chord(0) at centre.

Distances are the same arbitrary unit as the FORTRAN (typically cm), so values
copied verbatim from a leparagliding ``pre-data.txt`` reproduce the exact same
shape.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LeadingEdgeParams:
    """Type 1 leading edge — ellipse with up to two exponential corrections."""

    a1: float = 710.21
    b1: float = 243.11
    x1: float = 375.0
    x2: float = 475.0
    xm: float = 575.5
    c01: float = 48.30
    ex1: float = 2.0
    c02: float = 0.0
    ex2: float = 2.0

    def y_le(self, x: float) -> float:
        """Y position of the leading edge at span x (0..xm).

        Returned in chord coordinates: y=0 at centre, increasing towards the
        tip as the LE sweeps back.
        """
        a1 = self.a1
        b1 = self.b1
        if x < 0:
            x = -x
        if x > a1:
            x = a1

        # ellipse base: yq = b1 * sqrt(1 - (x/a1)^2)
        yq = b1 * math.sqrt(max(1.0 - (x * x) / (a1 * a1), 0.0))

        if x >= self.x1:
            denom1 = (self.xm - self.x1) ** self.ex1
            k1 = self.c01 / denom1 if denom1 > 0 else 0.0
            yq -= k1 * (x - self.x1) ** self.ex1
        if x >= self.x2:
            denom2 = (self.xm - self.x2) ** self.ex2
            k2 = self.c02 / denom2 if denom2 > 0 else 0.0
            yq -= k2 * (x - self.x2) ** self.ex2

        # FORTRAN draws -yq + sepy with sepy = b1, so chord y = b1 - yq
        return b1 - yq

    def scale(self, span_factor: float, chord_factor: float) -> None:
        self.a1 *= span_factor
        self.x1 *= span_factor
        self.x2 *= span_factor
        self.xm *= span_factor
        self.b1 *= chord_factor
        self.c01 *= chord_factor
        self.c02 *= chord_factor


@dataclass
class TrailingEdgeParams:
    """Type 1 trailing edge — ellipse with one exponential correction."""

    a1: float = 903.01
    b1: float = 243.11
    x1: float = 372.50
    xm: float = 575.5
    c0: float = -2.45
    y0: float = 215.20
    exp: float = 2.0

    def y_te(self, x: float, b1_le: float) -> float:
        """Y position of the trailing edge at span x.

        ``b1_le`` is the leading-edge ``b1`` parameter; it's the value the
        FORTRAN uses as the planview origin (sepy in pre-processor.f).
        """
        a1 = self.a1
        b1 = self.b1
        if x < 0:
            x = -x
        if x > a1:
            x = a1

        # yq = -b1 * cos(theta) + y0  with x = a1 sin(theta)
        yq = -b1 * math.sqrt(max(1.0 - (x * x) / (a1 * a1), 0.0)) + self.y0

        if x >= self.x1:
            denom = (self.xm - self.x1) ** self.exp
            k = self.c0 / denom if denom > 0 else 0.0
            yq -= k * (x - self.x1) ** self.exp

        # FORTRAN draws -yq + sepy with sepy = b1_le, so chord y = b1_le - yq
        return b1_le - yq

    def scale(self, span_factor: float, chord_factor: float) -> None:
        self.a1 *= span_factor
        self.x1 *= span_factor
        self.xm *= span_factor
        self.b1 *= chord_factor
        self.y0 *= chord_factor
        self.c0 *= chord_factor


@dataclass
class CellDistribution:
    """Cell distribution (matches pre-data.txt section 4)."""

    # type: 1 = uniform, 2 = linear, 3 = proportional to chord, 4 = explicit
    dist_type: int = 3
    cell_num: int = 45
    # type 2 / type 3 coefficient (0..1)
    coefficient: float = 0.6
    # type 4 explicit per-cell widths (centre to tip, half-wing, in input units)
    explicit_widths: list[float] = field(default_factory=list)


@dataclass
class LeparaglidingShapeParams:
    """All parameters needed to define a leparagliding-style planform."""

    leading_edge: LeadingEdgeParams = field(default_factory=LeadingEdgeParams)
    trailing_edge: TrailingEdgeParams = field(default_factory=TrailingEdgeParams)
    cells: CellDistribution = field(default_factory=CellDistribution)

    def scale(self, span_factor: float, chord_factor: float) -> None:
        """Scale linear dimensions of the planform.

        ``span_factor`` scales x-direction (a1, x*, xm) and ``chord_factor``
        scales y-direction (b1, c0*, y0). Equal factors keep aspect ratio
        constant; differing factors change aspect ratio.
        """
        self.leading_edge.scale(span_factor, chord_factor)
        self.trailing_edge.scale(span_factor, chord_factor)

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------
    def sample_le(self, num: int = 200) -> list[list[float]]:
        """Sample leading edge as a list of [x, y] points from centre to tip."""
        xm = self.leading_edge.xm
        return [
            [xm * i / (num - 1), self.leading_edge.y_le(xm * i / (num - 1))]
            for i in range(num)
        ]

    def sample_te(self, num: int = 200) -> list[list[float]]:
        """Sample trailing edge as a list of [x, y] points from centre to tip."""
        xm = self.leading_edge.xm
        b1_le = self.leading_edge.b1
        return [
            [
                xm * i / (num - 1),
                self.trailing_edge.y_te(xm * i / (num - 1), b1_le),
            ]
            for i in range(num)
        ]

    def chord_at(self, x: float) -> float:
        """Chord length at span x."""
        return self.trailing_edge.y_te(x, self.leading_edge.b1) - self.leading_edge.y_le(x)

    # ------------------------------------------------------------------
    # Cell distribution → openglider half-wing relative widths.
    #
    # ``cell_widths`` in ParametricShape are *coefficients* (1.0 = uniform).
    # For odd cell count the first coefficient is for the centre half-cell.
    # ------------------------------------------------------------------
    def compute_cell_widths(self) -> list[float]:
        cells = self.cells
        ncells = cells.cell_num
        if ncells <= 0:
            return []

        is_odd = ncells % 2 == 1
        # Number of stored coefficients on the half-wing.
        # Odd cell count: 1 centre half-cell + (ncells - 1) / 2 full cells.
        # Even cell count: ncells / 2 full cells.
        num_coeffs = ncells // 2 + (1 if is_odd else 0)

        if cells.dist_type == 1:
            return [1.0] * num_coeffs

        if cells.dist_type == 2:
            return self._linear_widths(ncells, is_odd, cells.coefficient)

        if cells.dist_type == 3:
            return self._chord_proportional_widths(ncells, is_odd, cells.coefficient)

        if cells.dist_type == 4:
            return self._explicit_widths(num_coeffs, cells.explicit_widths)

        raise ValueError(f"Unknown cell distribution type: {cells.dist_type}")

    # FORTRAN type 2: uniform width minus a linear ramp.
    def _linear_widths(
        self, ncells: int, is_odd: bool, coefficient: float
    ) -> list[float]:
        # FORTRAN: xk = 1 - input, clamped to [0, 1].
        xk = max(0.0, min(1.0, 1.0 - coefficient))
        xm = self.leading_edge.xm
        cuw = 2.0 * xm / ncells  # uniform cell width
        xk_cells = 2.0 * xk / ncells

        if is_odd:
            num_coeffs = ncells // 2 + 1
            widths: list[float] = []
            # Position (centre of cell) and corrected width — see pre-processor.f
            for i in range(1, num_coeffs + 1):
                pos = cuw * i - 0.5 * cuw
                w = cuw - xk_cells * pos
                widths.append(max(w, 1e-6))
            # Normalise so coefficient mean == 1.0.
            mean = sum(widths) / len(widths)
            return [w / mean for w in widths]

        num_coeffs = ncells // 2
        widths = []
        for i in range(2, num_coeffs + 2):
            pos = cuw * (i - 1)
            w = cuw - xk_cells * pos
            widths.append(max(w, 1e-6))
        mean = sum(widths) / len(widths)
        return [w / mean for w in widths]

    # FORTRAN type 3: per-cell width scales with local chord.
    def _chord_proportional_widths(
        self, ncells: int, is_odd: bool, coefficient: float
    ) -> list[float]:
        xk = coefficient
        xm = self.leading_edge.xm
        span = 2.0 * xm
        b11 = self.leading_edge.b1
        b1_te = self.trailing_edge.b1
        y0 = self.trailing_edge.y0
        # In FORTRAN, chordmax = b11 + b1_te - y0 — chord at the centre.
        chordmax = b11 + b1_te - y0

        if is_odd:
            num_coeffs = ncells // 2 + 1
            widths = [span / ncells] * num_coeffs

            for _ in range(5):
                # rib x positions: rib(1) = w(1)/2, rib(i) = rib(i-1) + w(i)
                positions = [widths[0] / 2.0]
                for i in range(1, num_coeffs):
                    positions.append(positions[-1] + widths[i])

                new_widths = []
                for x in positions:
                    chord = self.chord_at(x)
                    coefl = ((chordmax - chord) * xk + chord) / chordmax
                    new_widths.append(max(span / ncells * coefl, 1e-6))

                # global rescale so half-span sum (with half centre-cell) == xm
                s = new_widths[0] / 2.0 + sum(new_widths[1:])
                if s <= 0:
                    return [1.0] * num_coeffs
                scale = xm / s
                widths = [w * scale for w in new_widths]

            mean = sum(widths) / len(widths)
            return [w / mean for w in widths]

        num_coeffs = ncells // 2
        widths = [span / ncells] * num_coeffs

        for _ in range(5):
            positions = [widths[0] / 2.0]
            for i in range(1, num_coeffs):
                positions.append(positions[-1] + widths[i])

            new_widths = []
            for x in positions:
                chord = self.chord_at(x)
                coefl = ((chordmax - chord) * xk + chord) / chordmax
                new_widths.append(max(span / ncells * coefl, 1e-6))

            s = sum(new_widths)
            if s <= 0:
                return [1.0] * num_coeffs
            scale = xm / s
            widths = [w * scale for w in new_widths]

        mean = sum(widths) / len(widths)
        return [w / mean for w in widths]

    # FORTRAN type 4: explicit per-cell widths, normalised.
    def _explicit_widths(
        self, num_coeffs: int, raw: list[float]
    ) -> list[float]:
        if not raw:
            return [1.0] * num_coeffs
        widths = list(raw[:num_coeffs])
        if len(widths) < num_coeffs:
            widths.extend([widths[-1]] * (num_coeffs - len(widths)))
        widths = [max(w, 1e-6) for w in widths]
        mean = sum(widths) / len(widths)
        return [w / mean for w in widths]

    # ------------------------------------------------------------------
    # JSON helpers (used by ParametricShape.parametric_params storage).
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "leparagliding",
            "leading_edge": self.leading_edge.__dict__.copy(),
            "trailing_edge": self.trailing_edge.__dict__.copy(),
            "cells": {
                "dist_type": self.cells.dist_type,
                "cell_num": self.cells.cell_num,
                "coefficient": self.cells.coefficient,
                "explicit_widths": list(self.cells.explicit_widths),
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LeparaglidingShapeParams:
        le = LeadingEdgeParams(**data.get("leading_edge", {}))
        te = TrailingEdgeParams(**data.get("trailing_edge", {}))
        cells_data = data.get("cells", {})
        cells = CellDistribution(
            dist_type=int(cells_data.get("dist_type", 3)),
            cell_num=int(cells_data.get("cell_num", 45)),
            coefficient=float(cells_data.get("coefficient", 0.6)),
            explicit_widths=list(cells_data.get("explicit_widths", [])),
        )
        return cls(leading_edge=le, trailing_edge=te, cells=cells)
