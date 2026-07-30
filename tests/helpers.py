from __future__ import annotations

from pathlib import Path
import os
import unittest

import openglider
import openglider.glider
from openglider.glider import Glider
from openglider.glider.parametric import ParametricGlider
from openglider.glider.project import GliderProject


TESTS_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_ROOT.parent / "openglider"
import_dir = str(TESTS_ROOT / "common")


def get_demowing_path() -> str:
    return str(PACKAGE_ROOT / "demowing.ods")


def load_demowing() -> GliderProject:
    return openglider.load(get_demowing_path())


class GliderTestCase(unittest.TestCase):
    project: GliderProject

    def setUp(self) -> None:
        self.project = load_demowing()

    @property
    def parametric_glider(self) -> ParametricGlider:
        return self.project.glider

    @property
    def glider(self) -> Glider:
        return self.project.get_glider_3d()

    def assertEqualGlider(self, glider1: Glider, glider2: Glider, precision: int=None) -> None:
        self.assertEqual(len(glider1.ribs), len(glider2.ribs))
        self.assertEqual(len(glider1.cells), len(glider2.cells))
        for rib_no, (rib_1, rib_2) in enumerate(zip(glider1.ribs, glider2.ribs)):
            for xyz_1, xyz_2 in zip(rib_1.profile_3d.curve.nodes, rib_2.profile_3d.curve.nodes):
                for i, (_p1, _p2) in enumerate(zip(xyz_1, xyz_2)):
                    self.assertAlmostEqual(_p1, _p2, places=precision, msg=f"Not matching at Rib {rib_no}, Coordinate {i}; {_p1}//{_p2}")

    def assertEqualGlider2D(self, glider1: ParametricGlider, glider2: ParametricGlider) -> None:
        self.assertEqual(glider1.shape.cell_num, glider2.shape.cell_num)
