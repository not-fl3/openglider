use nalgebra::{Matrix3, Vector3};
use pyo3::prelude::*;

use crate::vector::{PolyLine2D, PolyLine3D, Transformation, Vector2D, Vector3D, VectorOps};

#[derive(FromPyObject)]
enum PlaneProjectInput {
    Point(Vector3D),
    PolyLine(Py<PolyLine3D>),
}

#[pyclass(from_py_object)]
#[derive(Clone, Debug)]
pub struct Plane {
    #[pyo3(get)]
    pub x_vector: Vector3D,
    #[pyo3(get)]
    pub y_vector: Vector3D,
    #[pyo3(get)]
    pub normvector: Vector3D,
    #[pyo3(get)]
    pub p0: Vector3D,
    #[pyo3(get)]
    pub transformation: Transformation,
}

impl Plane {
    fn unit_x() -> Vector3D {
        Vector3D { x: 1.0, y: 0.0, z: 0.0 }
    }

    fn unit_y() -> Vector3D {
        Vector3D { x: 0.0, y: 1.0, z: 0.0 }
    }

    fn unit_z() -> Vector3D {
        Vector3D { x: 0.0, y: 0.0, z: 1.0 }
    }

    fn matrix_from_basis(p0: Vector3D, x_vector: Vector3D, y_vector: Vector3D, normvector: Vector3D) -> [[f64; 4]; 4] {
        let mut matrix = [[0.0; 4]; 4];
        matrix[3][3] = 1.0;

        matrix[0][0] = x_vector.x;
        matrix[1][0] = x_vector.y;
        matrix[2][0] = x_vector.z;

        matrix[0][1] = y_vector.x;
        matrix[1][1] = y_vector.y;
        matrix[2][1] = y_vector.z;

        matrix[0][2] = normvector.x;
        matrix[1][2] = normvector.y;
        matrix[2][2] = normvector.z;

        matrix[3][0] = p0.x;
        matrix[3][1] = p0.y;
        matrix[3][2] = p0.z;

        matrix
    }

    fn basis_matrix(&self) -> Matrix3<f64> {
        Matrix3::from_columns(&[
            Vector3::new(self.x_vector.x, self.x_vector.y, self.x_vector.z),
            Vector3::new(self.y_vector.x, self.y_vector.y, self.y_vector.z),
            Vector3::new(self.normvector.x, self.normvector.y, self.normvector.z),
        ])
    }
}

#[pymethods]
impl Plane {
    #[new]
    #[pyo3(signature = (p0, x_vector, y_vector))]
    fn new(p0: Vector3D, x_vector: Vector3D, y_vector: Vector3D) -> PyResult<Self> {
        let normvector = x_vector.cross(&y_vector);
        let matrix = Self::matrix_from_basis(p0, x_vector, y_vector, normvector);

        Ok(Self {
            x_vector,
            y_vector,
            normvector,
            p0,
            transformation: Transformation::from_values(matrix),
        })
    }

    #[staticmethod]
    fn from_transformation(transformation: Transformation) -> Self {
        let p0 = transformation.apply_vector3(Vector3D::zero());
        let x_vector = transformation.apply_vector3(Self::unit_x()).sub(p0);
        let y_vector = transformation.apply_vector3(Self::unit_y()).sub(p0);
        let normvector = transformation.apply_vector3(Self::unit_z()).sub(p0);

        Self {
            x_vector,
            y_vector,
            normvector,
            p0,
            transformation,
        }
    }

    fn project(&self, value: PlaneProjectInput, py: Python<'_>) -> PyResult<Py<PyAny>> {
        match value {
            PlaneProjectInput::Point(point) => {
                Py::new(py, self.project_vector(&point))
                    .map(|value| value.into_bound(py).into_any().unbind())
            }
            PlaneProjectInput::PolyLine(polyline) => {
                let polyline = polyline.bind(py).borrow();
                Py::new(py, self.project_polyline(&polyline))
                    .map(|value| value.into_bound(py).into_any().unbind())
            }
        }
    }

    fn project_vector(&self, point: &Vector3D) -> Vector2D {
        let diff = point.sub(self.p0);
        let diff = Vector3::new(diff.x, diff.y, diff.z);
        let inverse = self.basis_matrix().try_inverse().unwrap_or_else(Matrix3::identity);
        let result = inverse * diff;
        Vector2D { x: result.x, y: result.y }
    }

    fn project_polyline(&self, polyline: &PolyLine3D) -> PolyLine2D {
        PolyLine2D {
            nodes: polyline.nodes.iter().map(|node| self.project_vector(node)).collect(),
        }
    }
}

#[pymodule(submodule, name = "plane")]
pub(crate) mod plane_mod {
    #[pymodule_export]
    use super::Plane;
}
