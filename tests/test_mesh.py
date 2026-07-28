import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import openglider


from tests.helpers import GliderTestCase

from openglider.mesh import Mesh
from openglider.utils.distribution import Distribution


class TestMesh(GliderTestCase):
    def test_mesh(self) -> None:
        m1 = Mesh.from_indexed(
            [
                openglider.rs.vector.Vector3D([0.0, 0.0, 0.0]),
                openglider.rs.vector.Vector3D([1.0, 0.0, 0.0]),
                openglider.rs.vector.Vector3D([0.0, 1.0, 0.0]),
                openglider.rs.vector.Vector3D([1.0, 1.0, 0.0]),
            ],
            {"a": [((0, 1, 2, 3), {})]},
        )
        m2 = Mesh.from_indexed(
            [
                openglider.rs.vector.Vector3D([0.0, 0.0, 0.0]),
                openglider.rs.vector.Vector3D([1.0, 0.0, 0.0]),
                openglider.rs.vector.Vector3D([1.0, 1.0, 0.0]),
                openglider.rs.vector.Vector3D([0.0, 0.0, 0.0]),
            ],
            {"b": [((0, 1, 2, 3), {})]},
        )
        m3 = m1 + m2
        m3.delete_duplicates()
        self.assertTrue(len(m3.vertices) >= 4)

    def test_glider_mesh(self) -> None:
        dist = Distribution.from_nose_cos_distribution(30, 0.2)

        self.glider.profile_x_values = list(dist)
        m = Mesh(name="glider_mesh")
        for cell in self.glider.cells[1:-1]:
            m += cell.get_mesh(0)
        for rib in self.glider.ribs:
            m += rib.get_mesh()
        m.delete_duplicates()
        m.get_indexed()

    def test_from_obj(self) -> None:
        with TemporaryDirectory() as tmpdir:
            obj_path = Path(tmpdir) / "sample.obj"
            obj_path.write_text(
                """\
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3 4
""",
                encoding="utf-8",
            )

            mesh = Mesh.from_obj(obj_path)

        self.assertEqual(mesh.name, "sample")
        self.assertEqual(len(mesh.polygons["sample"]), 1)
        self.assertEqual(len(mesh.vertices), 4)



if __name__ == '__main__':
    unittest.main(verbosity=2)
