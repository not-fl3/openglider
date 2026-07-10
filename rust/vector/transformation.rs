use nalgebra::{Matrix4, Vector4};
use pyo3::prelude::*;

use crate::vector::vector::{Vector2D, Vector3D};
use crate::vector::polyline::{PolyLine2D, PolyLine3D};
use crate::vector::signature::*;


#[pyclass(from_py_object)]
#[derive(Clone, Copy, Debug, Default)]
pub struct Rotation2D {
    angle: f64,
}

#[pymethods]
impl Rotation2D {
    #[new]
    fn new(angle: f64) -> Self {
        Self { angle }
    }

    fn apply(&self, vector: Vector2DInput) -> PyResult<Vector2D> {
        let vector = vector.into_vector()?;
        let (sin_angle, cos_angle) = self.angle.sin_cos();
        Ok(Vector2D {
            x: vector.x * cos_angle - vector.y * sin_angle,
            y: vector.x * sin_angle + vector.y * cos_angle,
        })
    }
}

#[pyclass(from_py_object)]
#[derive(Clone, Copy, Debug)]
pub struct Transformation {
    #[pyo3(get)]
    pub matrix: [[f64; 4]; 4],
    matrix4: Matrix4<f64>,
}

impl Transformation {
    fn matrix4_from_values(values: &[[f64; 4]; 4]) -> Matrix4<f64> {
        Matrix4::from_row_slice(&[
            values[0][0], values[0][1], values[0][2], values[0][3],
            values[1][0], values[1][1], values[1][2], values[1][3],
            values[2][0], values[2][1], values[2][2], values[2][3],
            values[3][0], values[3][1], values[3][2], values[3][3],
        ])
    }

    fn as_matrix4(&self) -> &Matrix4<f64> {
        &self.matrix4
    }

    fn from_matrix4(matrix: Matrix4<f64>) -> Self {
        let mut values = [[0.0; 4]; 4];
        for row in 0..4 {
            for col in 0..4 {
                values[row][col] = matrix[(row, col)];
            }
        }
        Self {
            matrix: values,
            matrix4: matrix,
        }
    }

    pub(crate) fn from_values(matrix: [[f64; 4]; 4]) -> Self {
        let matrix4 = Self::matrix4_from_values(&matrix);
        Self { matrix, matrix4 }
    }

    fn apply_polyline2(&self, polyline: &PolyLine2D) -> PolyLine3D {
        let matrix = self.as_matrix4();
        PolyLine3D {
            nodes: polyline
                .nodes
                .iter()
                .map(|node| Self::apply_vector3_with_matrix(matrix, node.to_3d()))
                .collect(),
        }
    }

    fn apply_polyline3(&self, polyline: &PolyLine3D) -> PolyLine3D {
        let matrix = self.as_matrix4();
        PolyLine3D {
            nodes: polyline
                .nodes
                .iter()
                .map(|node| Self::apply_vector3_with_matrix(matrix, *node))
                .collect(),
        }
    }

    fn apply_vector3_with_matrix(matrix: &Matrix4<f64>, vector: Vector3D) -> Vector3D {
        let result = matrix * Vector4::new(vector.x, vector.y, vector.z, 1.0);
        Vector3D {
            x: result.x,
            y: result.y,
            z: result.z,
        }
    }
}

#[pymethods]
impl Transformation {
    #[new]
    pub(crate) fn new() -> Self {
        Self::from_values([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ])
    }

    #[staticmethod]
    fn rotation(angle: f64, axis: Vector3DInput) -> PyResult<Self> {
        let axis = axis.into_vector()?.normalized();
        let (sin_angle, cos_angle) = angle.sin_cos();
        let one_minus = 1.0 - cos_angle;
        let matrix = Matrix4::new(
            cos_angle + axis.x * axis.x * one_minus,
            axis.x * axis.y * one_minus - axis.z * sin_angle,
            axis.x * axis.z * one_minus + axis.y * sin_angle,
            0.0,
            axis.y * axis.x * one_minus + axis.z * sin_angle,
            cos_angle + axis.y * axis.y * one_minus,
            axis.y * axis.z * one_minus - axis.x * sin_angle,
            0.0,
            axis.z * axis.x * one_minus - axis.y * sin_angle,
            axis.z * axis.y * one_minus + axis.x * sin_angle,
            cos_angle + axis.z * axis.z * one_minus,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        );
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn translation(vector: VectorXD) -> PyResult<Self> {
        let mut matrix = Matrix4::identity();
        let vector = vector.into_vector_3d()?;
        matrix[(0, 3)] = vector.x;
        matrix[(1, 3)] = vector.y;
        matrix[(2, 3)] = vector.z;
        
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn reflection(normal: Vector3DInput) -> PyResult<Self> {
        let normal = normal.into_vector()?.normalized();
        let nx = normal.x;
        let ny = normal.y;
        let nz = normal.z;
        let matrix = Matrix4::new(
            1.0 - 2.0 * nx * nx,
            -2.0 * nx * ny,
            -2.0 * nx * nz,
            0.0,
            -2.0 * ny * nx,
            1.0 - 2.0 * ny * ny,
            -2.0 * ny * nz,
            0.0,
            -2.0 * nz * nx,
            -2.0 * nz * ny,
            1.0 - 2.0 * nz * nz,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        );
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn scale(scale: f64) -> Self {
        let mut matrix = Matrix4::identity();
        matrix[(0, 0)] = scale;
        matrix[(1, 1)] = scale;
        matrix[(2, 2)] = scale;
        Self::from_matrix4(matrix)
    }

    fn chain(&self, other: &Transformation) -> Self {
        // Euklid composes transforms in left-to-right application order:
        // (A * B).apply(v) == B.apply(A.apply(v)).
        // With column-vector math this is represented as M = B * A.
        Self::from_matrix4(other.as_matrix4() * self.as_matrix4())
    }

    fn __mul__(&self, other: &Transformation) -> Self {
        self.chain(other)
    }

    fn copy(&self) -> Self {
        *self
    }

    fn apply(&self, vector: VectorXD) -> PyResult<Vector3D> {
        Ok(Self::apply_vector3_with_matrix(self.as_matrix4(), vector.into_vector_3d()?))
    }

    fn apply_polyline(&self, polyline: PolyLineXD, py: Python<'_>) -> PolyLine3D {
        match polyline {
            PolyLineXD::PolyLine2(polyline) => {
                let polyline = polyline.bind(py).borrow();
                self.apply_polyline2(&polyline)
            }
            PolyLineXD::PolyLine3(polyline) => {
                let polyline = polyline.bind(py).borrow();
                self.apply_polyline3(&polyline)
            }
        }
    }

    pub(crate) fn apply_vector3(&self, vector: Vector3D) -> Vector3D {
        Self::apply_vector3_with_matrix(self.as_matrix4(), vector)
    }

}
