import unittest

from openglider.glider.parametric.shape.leparagliding_shape import (
    LeparaglidingShape,
    LeparaglidingShapeParams,
)
from openglider.glider.parametric.shape.parametric_shape import ParametricShape
from openglider.glider.parametric.shape import PlanformShape
from tests.helpers import GliderTestCase


class GliderTestCase2D(GliderTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shape = self.parametric_glider.shape.get_half_shape()

    def test_slider_cell_widths_are_used_directly(self) -> None:
        shape = self.parametric_glider.shape
        original_distribution = [list(point) for point in shape.rib_distribution.controlpoints.nodes]

        for slider_index in (shape._num_cell_widths - 2, shape._num_cell_widths - 1):
            coefficients = [1.0] * shape._num_cell_widths
            coefficients[slider_index] = 2.0
            shape.apply_cell_widths(coefficients)

            ribs = shape.rib_x_values
            actual_widths = [right - left for left, right in zip(ribs, ribs[1:])]
            if shape.config.has_stabicell:
                actual_widths = actual_widths[:-1]

            scale = actual_widths[0]
            for actual, expected in zip(actual_widths, coefficients):
                self.assertAlmostEqual(actual / scale, expected, places=10)

        self.assertEqual(
            [list(point) for point in shape.rib_distribution.controlpoints.nodes],
            original_distribution,
        )

    def test_leparagliding_shape_is_not_a_parametric_shape(self) -> None:
        source = self.parametric_glider.shape
        shape = LeparaglidingShape(
            LeparaglidingShapeParams(),
            source.config,
            source.cell_num,
            rib_distribution=source.rib_distribution.copy(),
        )

        self.assertIsInstance(shape, PlanformShape)
        self.assertFalse(issubclass(LeparaglidingShape, ParametricShape))
        self.assertNotIsInstance(shape, ParametricShape)
        self.assertFalse(hasattr(shape, "front_curve"))
        self.assertFalse(hasattr(shape, "back_curve"))
        self.assertEqual(len(shape.rib_x_values), len(source.rib_x_values))

        half_shape = shape.get_half_shape()
        first_positive = shape.has_center_cell
        last = -1 if shape.config.has_stabicell else None
        self.assertGreater(len(half_shape.front.nodes[first_positive:last]), 0)
        # Slider normalization can put the tip a few floating-point ulps past xm.
        self.assertIsInstance(shape._edge_at(shape.span / 2 + 5e-10, True), float)
        self.assertIsInstance(shape.copy(), LeparaglidingShape)

    #def test_chords(self) -> None:
        # print(shape)

if __name__ == '__main__':
    unittest.main()
