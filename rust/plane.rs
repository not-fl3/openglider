use nalgebra::{Matrix3, Vector3};
use pyo3::prelude::*;

use crate::vector::{PolyLine2D, PolyLine3D, Transformation, Vector2D, Vector3D};

#[derive(FromPyObject)]
enum PlaneVectorInput {
    Vector(Vector3D),
    Values(Vec<f64>),
}

impl PlaneVectorInput {
    fn into_vector(self) -> PyResult<Vector3D> {
        match self {
            Self::Vector(vector) => Ok(vector),
            Self::Values(values) => Vector3D::from_components(&values),
        }
    }
}

#[derive(FromPyObject)]
enum PlaneInitInput {
    Transformation(Transformation),
    Vector(PlaneVectorInput),
}

#[derive(FromPyObject)]
enum PlaneProjectInput {
    Point(PlaneVectorInput),
    PolyLine(PolyLine3D),
}

#[pyclass]
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
    #[pyo3(signature = (arg0, arg1 = None, arg2 = None))]
    fn new(arg0: PlaneInitInput, arg1: Option<PlaneVectorInput>, arg2: Option<PlaneVectorInput>) -> PyResult<Self> {
        match arg0 {
            PlaneInitInput::Transformation(transformation) => {
                if arg1.is_some() || arg2.is_some() {
                    return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                        "when arg0 is a Transformation, arg1 and arg2 must be omitted",
                    ));
                }

                let x_vector = transformation.apply_vector3(Vector3D { x: 1.0, y: 0.0, z: 0.0 });
                let y_vector = transformation.apply_vector3(Vector3D { x: 0.0, y: 1.0, z: 0.0 });
                let p0 = transformation.apply_vector3(Vector3D::zero());
                let normvector = x_vector.cross(&y_vector).normalized();
                Ok(Self {
                    x_vector,
                    y_vector,
                    normvector,
                    p0,
                    transformation,
                })
            }
            PlaneInitInput::Vector(x_vector) => {
                let x_vector = x_vector.into_vector()?;
                let y_vector = arg1
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyTypeError, _>("expected three vectors"))?
                    .into_vector()?;
                let p0 = arg2
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyTypeError, _>("expected three vectors"))?
                    .into_vector()?;
                let normvector = x_vector.cross(&y_vector).normalized();
                Ok(Self {
                    x_vector,
                    y_vector,
                    normvector,
                    p0,
                    transformation: Transformation::new(),
                })
            }
        }
    }

    fn project(&self, value: PlaneProjectInput, py: Python<'_>) -> PyResult<Py<PyAny>> {
        match value {
            PlaneProjectInput::Point(point) => {
                Py::new(py, self.project_vector(point.into_vector()?))
                    .map(|value| value.into_bound(py).into_any().unbind())
            }
            PlaneProjectInput::PolyLine(polyline) => {
                Py::new(py, self.project_polyline(polyline))
                    .map(|value| value.into_bound(py).into_any().unbind())
            }
        }
    }

    fn project_vector(&self, point: Vector3D) -> Vector2D {
        let matrix = self.basis_matrix();
        let inverse = matrix.try_inverse().unwrap_or_else(Matrix3::identity);
        let diff = Vector3::new(point.x - self.p0.x, point.y - self.p0.y, point.z - self.p0.z);
        let result = inverse * diff;
        Vector2D { x: result.x, y: result.y }
    }

    fn project_polyline(&self, polyline: PolyLine3D) -> PolyLine2D {
        PolyLine2D {
            nodes: polyline.nodes.into_iter().map(|node| self.project_vector(node)).collect(),
        }
    }
}

#[pymodule(submodule, name = "plane")]
pub(crate) mod plane_mod {
    #[pymodule_export]
    use super::Plane;
}
