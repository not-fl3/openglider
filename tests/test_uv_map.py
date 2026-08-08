from __future__ import annotations

from tests.helpers import GliderTestCase

from openglider.glider.uv_map import UVMap, UVMapMirrored, UVMapStacked


class UVMapStackedLayoutTest(GliderTestCase):
    def test_stacked_panel_shape_preserves_shape_curves(self) -> None:
        uv_map = UVMap(self.parametric_glider)
        shape = self.parametric_glider.shape.get_half_shape()
        panel = self.glider.cells[0].panels[0]

        def normalize_x(value: float) -> float:
            if panel.is_lower():
                return max(float(value), 0.0)
            return max(float(-value), 0.0)

        polygon = uv_map._get_panel_shape(0, panel, shape)

        expected = [
            shape.get_point(0, normalize_x(panel.cut_back.x_left)),
            shape.get_point(1, normalize_x(panel.cut_back.x_right)),
            shape.get_point(1, normalize_x(panel.cut_front.x_right)),
            shape.get_point(0, normalize_x(panel.cut_front.x_left)),
        ]

        for actual, target in zip(polygon, expected):
            self.assertAlmostEqual(float(actual[0]), float(target[0]))
            self.assertAlmostEqual(float(actual[1]), float(target[1]))

    def test_stacked_layout_separates_upper_above_lower(self) -> None:
        uv_map = UVMap(self.parametric_glider)
        stacked = uv_map._get_stacked_uv_polys()

        upper_y = []
        lower_y = []
        for (cell_no, panel_idx), polyline in stacked.items():
            panel = self.glider.cells[cell_no].panels[panel_idx]
            ys = [float(point[1]) for point in polyline]
            if panel.is_lower():
                lower_y.extend(ys)
            else:
                upper_y.extend(ys)

        self.assertTrue(upper_y)
        self.assertTrue(lower_y)
        self.assertGreater(min(upper_y), max(lower_y))

    def test_split_classes_exist_and_layouts(self) -> None:
        stacked_map = UVMapStacked(self.parametric_glider)
        mirrored_map = UVMapMirrored(self.parametric_glider)

        stacked_layout = stacked_map.get_layout()
        mirrored_layout = mirrored_map.get_layout()

        self.assertTrue(stacked_layout.parts)
        self.assertTrue(mirrored_layout.parts)

    def test_transform_cell_local_coordinates_returns_normalized_uv(self) -> None:
        uv_map = UVMap(self.parametric_glider)
        u, v = uv_map.transform_cell_local_coordinates(
            cell_no=0,
            panel_idx=0,
            x=0.5,
            y=0.0,
            mode="stacked",
        )

        self.assertGreaterEqual(u, 0.0)
        self.assertLessEqual(u, 1.0)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)

    def test_transform_glider_coordinates_from_panel_stacked(self) -> None:
        uv_map = UVMapStacked(self.parametric_glider)
        panel = self.glider.cells[0].panels[0]
        u, v = uv_map.transform_glider_coordinates(panel=panel, x=0.5, y=0.25)

        self.assertGreaterEqual(u, 0.0)
        self.assertLessEqual(u, 1.0)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)

    def test_transform_glider_coordinates_from_panel_mirrored(self) -> None:
        uv_map = UVMapMirrored(self.parametric_glider)
        panel = self.glider.cells[0].panels[0]
        u, v = uv_map.transform_glider_coordinates(panel=panel, x=0.5, y=-0.25)

        self.assertGreaterEqual(u, 0.0)
        self.assertLessEqual(u, 1.0)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)

    def test_uvmap_facade_transform_glider_coordinates(self) -> None:
        uv_map = UVMap(self.parametric_glider)
        panel = self.glider.cells[0].panels[0]
        us, vs = uv_map.transform_glider_coordinates(panel=panel, x=0.5, y=0.25, mode="stacked")
        um, vm = uv_map.transform_glider_coordinates(panel=panel, x=0.5, y=-0.25, mode="mirrored")

        self.assertGreaterEqual(us, 0.0)
        self.assertLessEqual(us, 1.0)
        self.assertGreaterEqual(vs, 0.0)
        self.assertLessEqual(vs, 1.0)
        self.assertGreaterEqual(um, 0.0)
        self.assertLessEqual(um, 1.0)
        self.assertGreaterEqual(vm, 0.0)
        self.assertLessEqual(vm, 1.0)

    def test_transform_panel_local_coordinates_stacked(self) -> None:
        uv_map = UVMapStacked(self.parametric_glider)
        panel = self.glider.cells[0].panels[0]
        u, v = uv_map.transform_panel_local_coordinates(panel=panel, x=0.5, y=0.0)

        self.assertGreaterEqual(u, 0.0)
        self.assertLessEqual(u, 1.0)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)

    def test_uvmap_facade_transform_panel_local_coordinates(self) -> None:
        uv_map = UVMap(self.parametric_glider)
        panel = self.glider.cells[0].panels[0]
        u, v = uv_map.transform_panel_local_coordinates(panel=panel, x=0.5, y=0.0, mode="stacked")

        self.assertGreaterEqual(u, 0.0)
        self.assertLessEqual(u, 1.0)
        self.assertGreaterEqual(v, 0.0)
        self.assertLessEqual(v, 1.0)
