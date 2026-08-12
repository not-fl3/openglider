from __future__ import annotations

from tests.helpers import GliderTestCase

from openglider.glider.texture.uv_map import mirrored, stacked


class UVMapStackedLayoutTest(GliderTestCase):
    def test_split_classes_exist_and_layouts(self) -> None:
        stacked_map = stacked(self.parametric_glider)
        mirrored_map = mirrored(self.parametric_glider)

        stacked_layout = stacked_map.get_layout()
        mirrored_layout = mirrored_map.get_layout()

        self.assertTrue(stacked_layout.parts)
        self.assertTrue(mirrored_layout.parts)