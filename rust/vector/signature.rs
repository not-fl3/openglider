use pyo3::prelude::*;

use crate::vector::vector::{Vector2D, Vector3D};
use crate::vector::polyline::{PolyLine2D, PolyLine3D};
use super::interpolation::*;

#[derive(FromPyObject)]
pub enum Vector2DInput {
    Vector(Vector2D),
    Values(Vec<f64>),
}

impl Vector2DInput {
    pub fn into_vector(self) -> PyResult<Vector2D> {
        match self {
            Self::Vector(vector) => Ok(vector),
            Self::Values(values) => Vector2D::from_components(&values),
        }
    }
}

pub enum Vector2DScale {
    Scalar(f64),
    Vector(Vector2D),
}

#[derive(FromPyObject)]
pub enum Vector2DScaleInput {
    Scalar(f64),
    Vector(Vector2D),
    Values(Vec<f64>),
}

impl Vector2DScaleInput {
    pub fn into_scale(self) -> PyResult<Vector2DScale> {
        match self {
            Self::Scalar(scalar) => Ok(Vector2DScale::Scalar(scalar)),
            Self::Vector(vector) => Ok(Vector2DScale::Vector(vector)),
            Self::Values(values) => Ok(Vector2DScale::Vector(Vector2D::from_components(&values)?)),
        }
    }
}

#[derive(FromPyObject)]
pub enum Vector3DInput {
    Vector(Vector3D),
    Values(Vec<f64>),
}

impl Vector3DInput {
    pub fn into_vector(self) -> PyResult<Vector3D> {
        match self {
            Self::Vector(vector) => Ok(vector),
            Self::Values(values) => Vector3D::from_components(&values),
        }
    }
}

pub enum Vector3DScale {
    Scalar(f64),
    Vector(Vector3D),
}

#[derive(FromPyObject)]
pub enum Vector3DScaleInput {
    Scalar(f64),
    Vector(Vector3D),
    Values(Vec<f64>),
}

impl Vector3DScaleInput {
    pub fn into_scale(self) -> PyResult<Vector3DScale> {
        match self {
            Self::Scalar(scalar) => Ok(Vector3DScale::Scalar(scalar)),
            Self::Vector(vector) => Ok(Vector3DScale::Vector(vector)),
            Self::Values(values) => Ok(Vector3DScale::Vector(Vector3D::from_components(&values)?)),
        }
    }
}

#[derive(FromPyObject)]
pub enum VectorXD {
    Vector2(Vector2D),
    Vector3(Vector3D),
    Values(Vec<f64>),
}
impl VectorXD {
    pub fn into_vector_3d(self) -> PyResult<Vector3D> {
        match self {
            Self::Vector3(vector) => Ok(vector),
            Self::Vector2(vector) => Ok(vector.to_3d()),
            Self::Values(values) => {
                if values.len() == 2  {
                    Ok(Vector3D::from_xyz(values[0], values[1], 0.))
                } else {
                    Vector3D::from_components(&values)
                }
            }
        }
    }
}

#[derive(FromPyObject)]
pub enum PolyLineXD {
    PolyLine2(Py<PolyLine2D>),
    PolyLine3(Py<PolyLine3D>),
}

#[derive(FromPyObject)]
pub enum PolyLine2DCutInput {
    Vector(Vector2DInput),
    PolyLine(Py<PolyLine2D>),
}

#[derive(FromPyObject)]
pub enum InterpolationNodesInput {
    Interpolation(Py<Interpolation>),
    PolyLine(Py<PolyLine2D>),
    Points(Vec<Vector2DInput>),
}