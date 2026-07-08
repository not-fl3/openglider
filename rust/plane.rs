use nalgebra::{Matrix3, Vector3};
use pyo3::prelude::*;
use pyo3::types::PyAny;

use crate::vector::{PolyLine2D, PolyLine3D, Transformation, Vector2D, Vector3D};

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
    fn new(arg0: &Bound<'_, PyAny>, arg1: Option<Vector3D>, arg2: Option<Vector3D>) -> PyResult<Self> {
        if arg1.is_none() && arg2.is_none() {
            let transformation = arg0.extract::<Transformation>()?;
            let x_vector = transformation.apply_vector3(Vector3D { x: 1.0, y: 0.0, z: 0.0 });
            let y_vector = transformation.apply_vector3(Vector3D { x: 0.0, y: 1.0, z: 0.0 });
            let p0 = transformation.apply_vector3(Vector3D::zero());
            let normvector = x_vector.cross(&y_vector).normalized();
            return Ok(Self {
                x_vector,
                y_vector,
                normvector,
                p0,
                transformation,
            });
        }

        let x_vector = arg0.extract::<Vector3D>()?;
        let y_vector = arg1.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyTypeError, _>("expected three vectors"))?;
        let p0 = arg2.ok_or_else(|| PyErr::new::<pyo3::exceptions::PyTypeError, _>("expected three vectors"))?;
        let normvector = x_vector.cross(&y_vector).normalized();
        Ok(Self {
            x_vector,
            y_vector,
            normvector,
            p0,
            transformation: Transformation::new(),
        })
    }

    fn project(&self, value: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(point) = value.extract::<Vector3D>() {
            return Py::new(py, self.project_vector(point)).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(polyline) = value.extract::<PolyLine3D>() {
            return Py::new(py, self.project_polyline(polyline)).map(|value| value.into_bound(py).into_any().unbind());
        }
        Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>("project expects Vector3D or PolyLine3D"))
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
