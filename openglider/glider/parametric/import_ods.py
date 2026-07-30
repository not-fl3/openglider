from __future__ import annotations

import warnings
import logging
import math
import numbers
from typing import TYPE_CHECKING, Any
from packaging.version import Version

import openglider.rs
from openglider.airfoil import Profile2D

from openglider.glider.parametric.arc import ArcCurve
from openglider.glider.parametric.config import ParametricGliderConfig, SewingAllowanceConfig
from openglider.glider.parametric.leparagliding import LeparaglidingShapeParams
from openglider.glider.parametric.shape import ParametricShape
from openglider.glider.parametric.table import GliderTables
from openglider.glider.parametric.table.attachment_points import AttachmentPointTable, CellAttachmentPointTable
from openglider.glider.parametric.table.ballooning import BallooningTable, transpose_columns
from openglider.glider.parametric.table.cell.ballooning import BallooningModifierTable
from openglider.glider.parametric.table.cell.cuts import CutTable
from openglider.glider.parametric.table.cell.diagonals import DiagonalTable, StrapTable
from openglider.glider.parametric.table.cell.miniribs import MiniRibTable
from openglider.glider.parametric.table.curve import CurveTable
from openglider.glider.parametric.table.lines import LineSetTable
from openglider.glider.parametric.table.material import CellClothTable, RibClothTable
from openglider.glider.parametric.table.rib.holes import HolesTable
from openglider.glider.parametric.table.rib.profile import ProfileModifierTable
from openglider.glider.parametric.table.rib.rib import SingleSkinTable
from openglider.glider.parametric.table.rigidfoil import CellRigidTable, RibRigidTable
from openglider.utils import linspace
from openglider.utils.dataclass import BaseModel
from openglider.utils.table import Table
from openglider.utils.types import SymmetricCurveType

if TYPE_CHECKING:
    from openglider.glider.parametric import ParametricGlider

logger = logging.getLogger(__name__)

class TableNames:
    cell_sheet = "Cell Elements"
    rib_sheet = "Rib Elements"
    parametric_data = "Parametric"


def _parse_leparagliding_column(table: Table, column: int) -> dict[str, Any]:
    """Parse the key/value rows of a 'leparagliding'-typed Parametric column.

    Keys are in ``column``, values in ``column + 1``; comma-separated strings
    become lists of floats.
    """
    result: dict[str, Any] = {}
    for row in range(1, table.num_rows):
        key = table[row, column]
        if key is None:
            continue
        key_s = str(key).strip()
        if not key_s or key_s.startswith("*"):
            continue
        raw = table[row, column + 1]
        if isinstance(raw, str) and "," in raw:
            try:
                result[key_s] = [float(v) for v in raw.split(",")]
            except ValueError:
                result[key_s] = raw
        else:
            result[key_s] = raw
    return result


def _shape_from_leparagliding(flat: dict[str, Any], cell_num: int, config: ParametricGliderConfig) -> ParametricShape:
    """Regenerate a ParametricShape from flattened leparagliding params."""
    le_keys = ("a1", "b1", "x1", "x2", "xm", "c01", "ex1", "c02", "ex2")
    te_keys = ("a1", "b1", "x1", "c0", "y0", "exp")

    def _f(k: str, default: float = 0.0) -> float:
        v = flat.get(k, default)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    explicit_raw = flat.get("cell_explicit_widths")
    if isinstance(explicit_raw, list):
        explicit = [float(v) for v in explicit_raw]
    elif isinstance(explicit_raw, (int, float)):
        explicit = [float(explicit_raw)]
    else:
        explicit = []

    params = LeparaglidingShapeParams.from_dict({
        "mode": str(flat.get("mode", "leparagliding")),
        "leading_edge": {k: _f(f"le_{k}") for k in le_keys},
        "trailing_edge": {**{k: _f(f"te_{k}") for k in te_keys}, "xm": _f("le_xm")},
        "cells": {
            "dist_type": int(_f("cell_dist_type", 3.0)),
            "cell_num": cell_num,
            "coefficient": _f("cell_coefficient", 0.6),
            "explicit_widths": explicit,
        },
    })

    # Base shape with placeholder curves; apply_leparagliding_params rebuilds
    # front/back/rib_distribution from the params (which fully define the shape).
    front = openglider.rs.spline.SymmetricBSplineCurve([[0., 0.], [0.25, -0.1], [0.5, -0.3], [0.75, -0.6], [1., -1.]])
    back = openglider.rs.spline.SymmetricBSplineCurve([[0., -0.1], [0.25, -0.3], [0.5, -0.5], [0.75, -0.8], [1., -1.2]])
    rib_distribution = openglider.rs.spline.BSplineCurve([[0., 0.], [0.5, 0.5], [1., 1.]])
    shape = ParametricShape(front, back, rib_distribution, cell_num, config=config)
    shape.apply_leparagliding_params(params)
    return shape


def _arc_from_leparagliding(flat: dict[str, Any], x_values: list[float]) -> ArcCurve:
    """Regenerate an ArcCurve (vault generator) from flattened params."""
    mode = str(flat.get("mode", ""))

    def _f(k: str, default: float) -> float:
        try:
            return float(flat.get(k, default))
        except (TypeError, ValueError):
            return default

    if mode == "vault_ellipse":
        params: dict[str, Any] = {
            "mode": mode,
            "a_ratio": _f("a_ratio", 0.78),
            "b_ratio": _f("b_ratio", 0.44),
            "x1_ratio": _f("x1_ratio", 0.53),
            "c1_ratio": _f("c1_ratio", 0.043),
        }
        arc = ArcCurve.from_vault_ellipse(
            x_values,
            a_ratio=params["a_ratio"], b_ratio=params["b_ratio"],
            x1_ratio=params["x1_ratio"], c1_ratio=params["c1_ratio"],
        )
    elif mode == "vault_circles":
        radii = flat.get("radii")
        arc_angles = flat.get("arc_angles")
        radii = [float(v) for v in radii] if isinstance(radii, list) else [640.56, 480.47, 229.50, 99.26]
        arc_angles = [float(v) for v in arc_angles] if isinstance(arc_angles, list) else [20.35, 21.367, 18.925, 28.349]
        params = {"mode": mode, "radii": radii, "arc_angles": arc_angles}
        arc = ArcCurve.from_vault_circles(x_values, radii=radii, arc_angles=arc_angles)
    else:
        raise ValueError(f"unknown leparagliding arc mode: {mode!r}")

    arc.arc_generator_params = params
    return arc


def import_ods_2d(cls: type[ParametricGlider], filename: str) -> ParametricGlider:
    logger.info(f"Import file: {filename}")
    tables = Table.load(filename)

    return import_ods_glider(cls, tables)


def import_markdown_2d(cls: type[ParametricGlider], filename: str) -> ParametricGlider:
    logger.info(f"Import markdown file: {filename}")
    tables = Table.load_markdown(filename)
    table_dct: dict[str, Table] = {table.name: table for table in tables}

    return import_markdown_glider(cls, table_dct)


def import_markdown_glider(cls: type[ParametricGlider], tables: list[Table] | dict[str, Table]) -> ParametricGlider:
    if isinstance(tables, list):
        table_dct = {table.name: table for table in tables}
    else:
        table_dct = tables

    if "geometry" not in table_dct:
        raise ValueError("Markdown import requires a geometry table")

    config = ParametricGliderConfig.read_table(table_dct.get(ParametricGliderConfig.table_name, Table()))
    sewing_allowances = SewingAllowanceConfig.read_table(table_dct.get(SewingAllowanceConfig.table_name, Table()))

    profiles = [Profile2D(profile, name).normalized() for name, profile in transpose_columns(table_dct.get("Airfoils", Table()))]
    geometry = get_geometry_explicit(table_dct["geometry"], config)
    geometry_parametric = get_geometry_parametric(table_dct.get(TableNames.parametric_data, Table()), geometry.shape.cell_no, config)
    balloonings = BallooningTable(table=table_dct.get(BallooningTable.table_name, Table()))

    attachment_points_lower = config.get_lower_attachment_points()
    lineset_table = LineSetTable(table=table_dct.get(LineSetTable.table_name, Table()), lower_attachment_points=attachment_points_lower)

    glider_tables = GliderTables()
    glider_tables.curves = CurveTable(table_dct.get("Curves", None), config.version)

    cell_sheet = table_dct.get(TableNames.cell_sheet, Table())
    rib_sheet = table_dct.get(TableNames.rib_sheet, Table())
    migrate_header = cell_sheet[0, 0] is not None and cell_sheet[0, 0] < "V4"

    # Prefer separated markdown tables; fall back to legacy combined sheets.
    glider_tables.cuts = CutTable(table_dct.get("cuts", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.ballooning_modifiers = BallooningModifierTable(table_dct.get("ballooning_modifiers", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.holes = HolesTable(table_dct.get("holes", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.diagonals = DiagonalTable(table_dct.get("diagonals", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.rigidfoils_rib = RibRigidTable(table_dct.get("rigidfoils_rib", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.rigidfoils_cell = CellRigidTable(table_dct.get("rigidfoils_cell", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.straps = StrapTable(table_dct.get("straps", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.material_cells = CellClothTable(table_dct.get("material_cells", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.material_ribs = RibClothTable(table_dct.get("material_ribs", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.miniribs = MiniRibTable(table_dct.get("miniribs", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.rib_modifiers = SingleSkinTable(table_dct.get("rib_modifiers", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.profile_modifiers = ProfileModifierTable(table_dct.get("profile_modifiers", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.attachment_points_rib = AttachmentPointTable(table_dct.get("attachment_points_rib", None) or rib_sheet, migrate_header=migrate_header)
    glider_tables.attachment_points_cell = CellAttachmentPointTable(table_dct.get("attachment_points_cell", None) or cell_sheet, migrate_header=migrate_header)
    glider_tables.lines = lineset_table

    glider_2d = cls(tables=glider_tables,
                         profiles=profiles,
                         balloonings=balloonings.get(),
                         allowances=sewing_allowances,
                         config=config,
                         speed=config.speed,
                         glide=config.glide,
                         **geometry_parametric.model_dump())

    return glider_2d


def import_ods_glider(cls: type[ParametricGlider], tables: list[Table]) -> ParametricGlider:
    table_dct: dict[str, Table] = {
        TableNames.cell_sheet: tables[1],
        TableNames.rib_sheet: tables[2]
    }

    for table in tables[3:]:
        if table.name in table_dct:
            raise ValueError(f"{table.name} already in tables")
        table_dct[table.name] = table

    cell_sheet = tables[1]
    rib_sheet = tables[2]

    config = ParametricGliderConfig.read_table(tables[7])
    sewing_allowances = SewingAllowanceConfig.read_table(table_dct.get(SewingAllowanceConfig.table_name, Table()))


    logger.info(f"Loading file version {config.version}")
    # ------------

    # profiles = [BezierProfile2D(profile) for profile in transpose_columns(sheets[3])]
    profiles = [Profile2D(profile, name).normalized() for name, profile in transpose_columns(tables[3])]

    if config.version > Version("0.0.1"):
        has_center_cell = not tables[0]["C2"] == 0
        cell_no = (tables[0].num_rows - 2) * 2 + has_center_cell
        geometry = get_geometry_parametric(table_dct[TableNames.parametric_data], cell_no, config)
    else:
        geometry = get_geometry_explicit(tables[0], config)
        has_center_cell = geometry.shape.has_center_cell

    balloonings = BallooningTable(table=table_dct[BallooningTable.table_name])

    attachment_points_lower = config.get_lower_attachment_points()
    lineset_table = LineSetTable(table=table_dct[LineSetTable.table_name], lower_attachment_points=attachment_points_lower)

    migrate_header = cell_sheet[0, 0] is not None and cell_sheet[0, 0] < "V4"

    glider_tables = GliderTables()
    glider_tables.curves = CurveTable(table_dct.get("Curves", None), config.version)

    glider_tables.cuts = CutTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.ballooning_modifiers = BallooningModifierTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.holes = HolesTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.diagonals = DiagonalTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.rigidfoils_rib = RibRigidTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.rigidfoils_cell = CellRigidTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.straps = StrapTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.material_cells = CellClothTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.material_ribs = RibClothTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.miniribs = MiniRibTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.rib_modifiers = SingleSkinTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.profile_modifiers = ProfileModifierTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.attachment_points_rib = AttachmentPointTable(rib_sheet, migrate_header=migrate_header)
    glider_tables.attachment_points_cell = CellAttachmentPointTable(cell_sheet, migrate_header=migrate_header)
    glider_tables.lines = lineset_table
    
    glider_2d = cls(tables=glider_tables,
                         profiles=profiles,
                         balloonings=balloonings.get(),
                         allowances=sewing_allowances,
                         config=config,
                         speed=config.speed,
                         glide=config.glide,
                         **geometry.model_dump())

    return glider_2d


class Geometry(BaseModel):
    shape: ParametricShape
    arc: ArcCurve
    aoa: SymmetricCurveType
    profile_merge_curve: SymmetricCurveType
    ballooning_merge_curve: SymmetricCurveType


def get_geometry_explicit(sheet: Table, config: ParametricGliderConfig) -> Geometry:
    # All Lists
    front = []
    back = []
    cell_distribution = []
    aoa = []
    arc = []
    profile_merge = []
    ballooning_merge = []

    y = z = span_last = alpha = 0.
    for i in range(1, sheet.num_rows):
        line = [sheet[i, j] for j in range(sheet.num_columns)]
        if not line[0]:
            break  # skip empty line
        if not all(isinstance(c, numbers.Number) for c in line[:10]):
            raise ValueError(f"Invalid row ({i}): {line}")
        # Index, Choord, Span(x_2d), Front(y_2d=x_3d), d_alpha(next), aoa,
        chord = line[1]
        span = line[2]
        x = line[3]
        y += math.cos(alpha) * (span - span_last)
        z -= math.sin(alpha) * (span - span_last)

        alpha += line[4] * math.pi / 180  # angle after the rib

        aoa.append([span, line[5] * math.pi / 180])
        arc.append([y, z])
        front.append([span, -x])
        back.append([span, -x - chord])
        cell_distribution.append([span, i - 1])

        profile_merge.append([span, line[8]])
        ballooning_merge.append([span, line[9]])

        span_last = span

    def symmetric_fit(data: list[list[float]], bspline: bool=True) -> SymmetricCurveType:
        line = openglider.rs.vector.PolyLine2D(data)
        #not_from_center = int(data[0][0] == 0)
        #mirrored = [[-p[0], p[1]] for p in data[not_from_center:]][::-1] + data
        if bspline:
            return openglider.rs.spline.SymmetricBSplineCurve.fit(line, 3)  # type: ignore
        else:
            return openglider.rs.spline.SymmetricBezierCurve.fit(line, 3)  # type: ignore

    has_center_cell = not front[0][0] == 0
    cell_no = (len(front) - 1) * 2 + has_center_cell

    start = (2 - has_center_cell) / cell_no

    const_arr = [0.] + linspace(start, 1, len(front) - (not has_center_cell))
    rib_pos = [0.] + [p[0] for p in front[not has_center_cell:]]
    rib_pos_int = openglider.rs.vector.Interpolation(list(zip(rib_pos, const_arr)))
    rib_distribution = openglider.rs.vector.PolyLine2D([[i, rib_pos_int.get_value(i)] for i in linspace(0, rib_pos[-1], 30)])

    rib_distribution_curve: openglider.rs.spline.BSplineCurve = openglider.rs.spline.BSplineCurve.fit(rib_distribution, 3)  # type: ignore

    parametric_shape = ParametricShape(
        symmetric_fit(front),
        symmetric_fit(back),
        rib_distribution_curve,
        cell_no,
        config=config
        )
    arc_curve = ArcCurve(symmetric_fit(arc))

    return Geometry(
        shape=parametric_shape,
        arc=arc_curve,
        aoa=symmetric_fit(aoa),
        profile_merge_curve=symmetric_fit(profile_merge, bspline=True),
        ballooning_merge_curve=symmetric_fit(ballooning_merge, bspline=True)
    )


def get_geometry_parametric(table: Table, cell_num: int, config: ParametricGliderConfig) -> Geometry:
    data = {}
    # name -> flattened params, for columns whose type is "leparagliding"
    leparagliding: dict[str, dict[str, Any]] = {}
    curve_types = {
        "front": openglider.rs.spline.SymmetricBSplineCurve,
        "back": openglider.rs.spline.SymmetricBSplineCurve,
        "rib_distribution": openglider.rs.spline.BezierCurve,
        "arc": openglider.rs.spline.SymmetricBSplineCurve,
        "aoa": openglider.rs.spline.SymmetricBSplineCurve,
        "profile_merge_curve": openglider.rs.spline.SymmetricBSplineCurve,
        "ballooning_merge_curve": openglider.rs.spline.SymmetricBSplineCurve
    }

    for column in range(0, table.num_columns, 2):
        key = table[0, column]
        if key is None:
            continue
        type_str = table[0, column+1]
        if type_str == "leparagliding":
            # Parameter column: the curve is regenerated from these below.
            leparagliding[key] = _parse_leparagliding_column(table, column)
            continue
        if key not in curve_types:
            if key == "zrot":
                warnings.warn("zrot is deprecated, use aoa instead", DeprecationWarning)
                continue
            else:
                raise ValueError(f"Invalid curve: {key}")
        points = []

        if type_str is not None:
            curve_type = getattr(openglider.rs.spline, type_str)
        else:
            logger.warning(f"default curve for {key}")
            curve_type = curve_types[key]

        for row in range(1, table.num_rows):
            if table[row, column] is not None:
                points.append([table[row, column], table[row, column+1]])

        data[key] = curve_type(points)

    if "front" in leparagliding:
        # Shape is fully described by the leparagliding params in the front
        # column (back is an empty marker); regenerate front/back/rib_distribution.
        parametric_shape = _shape_from_leparagliding(leparagliding["front"], cell_num, config)
        data.pop("rib_distribution", None)
    else:
        parametric_shape = ParametricShape(
            data.pop("front"),
            data.pop("back"),
            data.pop("rib_distribution"),
            cell_num,
            config=config,
        )

    if "arc" in leparagliding:
        arc_curve = _arc_from_leparagliding(leparagliding["arc"], parametric_shape.rib_x_values)
    else:
        arc_curve = ArcCurve(data.pop("arc"))

    return Geometry(
        shape=parametric_shape,
        arc=arc_curve,
        **data
    )
