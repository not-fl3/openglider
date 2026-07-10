use pyo3::prelude::*;
use pyo3::types::{PyAny, PyList};

use super::signature::*;
use super::vector::*;
use super::polyline::{PolyLine2D, SimpleError};

const X_EPS: f64 = 1e-15;

fn monotonic_direction(nodes: &[Vector2D]) -> Option<bool> {
    for pair in nodes.windows(2) {
        let dx = pair[1].x - pair[0].x;
        if dx > X_EPS {
            return Some(true);
        }
        if dx < -X_EPS {
            return Some(false);
        }
    }
    None
}

fn is_monotonic_x(nodes: &[Vector2D]) -> bool {
    if nodes.len() < 2 {
        return true;
    }

    let Some(increasing) = monotonic_direction(nodes) else {
        // All x are (almost) equal: this is not useful for interpolation.
        return false;
    };

    for pair in nodes.windows(2) {
        let dx = pair[1].x - pair[0].x;
        if increasing && dx < -X_EPS {
            return false;
        }
        if !increasing && dx > X_EPS {
            return false;
        }
    }

    true
}

fn validate_monotonic_x(nodes: &[Vector2D]) -> Result<(), SimpleError> {
    if !is_monotonic_x(nodes) {
        return Err(SimpleError::new(
            "Interpolation input data must be monotonic in x",
        ));
    }
    Ok(())
}

fn first_nonzero_segment(nodes: &[Vector2D], from_start: bool) -> Option<(Vector2D, Vector2D)> {
    if nodes.len() < 2 {
        return None;
    }

    if from_start {
        for pair in nodes.windows(2) {
            if (pair[1].x - pair[0].x).abs() > X_EPS {
                return Some((pair[0], pair[1]));
            }
        }
    } else {
        for index in (0..nodes.len() - 1).rev() {
            let left = nodes[index];
            let right = nodes[index + 1];
            if (right.x - left.x).abs() > X_EPS {
                return Some((left, right));
            }
        }
    }

    None
}

fn no_cut_error(value: f64) -> SimpleError {
    SimpleError::new(format!("Could not cut for x: {}", value))
}

fn validated(interpolation: Interpolation) -> Result<Interpolation, SimpleError> {
    validate_monotonic_x(&interpolation.curve.nodes)?;
    Ok(interpolation)
}


#[pyclass(from_py_object)]
#[derive(Clone, Debug)]
pub struct Interpolation {
    #[pyo3(get)]
    pub curve: PolyLine2D,
    #[pyo3(get, set)]
    pub extrapolate: bool,
}

#[pymethods]
impl Interpolation {
    #[new]
    #[pyo3(signature = (nodes, extrapolate = true, validate = true))]
    fn new(nodes: InterpolationNodesInput, extrapolate: bool, validate: bool, py: Python<'_>) -> PyResult<Self> {
        let validate_nodes = |nodes: &[Vector2D]| -> PyResult<()> {
            if validate {
                validate_monotonic_x(nodes).map_err(Into::into)
            } else {
                Ok(())
            }
        };

        match nodes {
            InterpolationNodesInput::Interpolation(interpolation) => {
                let interpolation = interpolation.bind(py).borrow();
                validate_nodes(&interpolation.curve.nodes)?;
                Ok(Self { curve: interpolation.curve.clone(), extrapolate })
            }
            InterpolationNodesInput::PolyLine(polyline) => {
                let polyline = polyline.bind(py).borrow();
                validate_nodes(&polyline.nodes)?;
                Ok(Self { curve: polyline.clone(), extrapolate })
            }
            InterpolationNodesInput::Points(points) => {
                let mut parsed = Vec::with_capacity(points.len());
                for point in points {
                    parsed.push(point.into_vector()?);
                }
                validate_nodes(&parsed)?;
                Ok(Self { curve: PolyLine2D { nodes: parsed }, extrapolate })
            }
        }
    }

    fn copy(&self) -> Self { self.clone() }

    fn __len__(&self) -> usize { self.curve.nodes.len() }
    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let list = PyList::new(py, self.curve.nodes.clone())?;
        Ok(list.into_any().call_method0("__iter__")?.unbind())
    }
    fn __copy__(&self) -> Self { self.clone() }
    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self { self.clone() }
    fn __json__(&self) -> Vec<Vec<f64>> { self.curve.nodes.iter().map(VectorOps::components).collect() }
    fn tolist(&self) -> Vec<Vec<f64>> { self.curve.nodes.iter().map(VectorOps::components).collect() }

    #[getter]
    fn nodes(&self) -> Vec<Vector2D> { self.curve.nodes.clone() }

    #[pyo3(signature = (value, end = None))]
    fn get(&self, value: f64, end: Option<f64>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        self.curve.get(value, end, py)
    }

    fn get_positions(&self, start: f64, end: f64) -> Vec<f64> {
        self.curve.get_positions(start, end)
    }

    fn get_segments(&self) -> Vec<Vector2D> { self.curve.get_segments() }
    fn get_segment_lengthes(&self) -> Vec<f64> { self.curve.get_segment_lengthes() }
    fn get_tangents(&self) -> Vec<Vector2D> { self.curve.get_tangents() }
    fn get_length(&self) -> f64 { self.curve.get_length() }
    fn walk(&self, start: f64, amount: f64) -> f64 { self.curve.walk(start, amount) }

    fn resample(&self, num_points: usize) -> Self {
        Self { curve: self.curve.resample(num_points), extrapolate: self.extrapolate }
    }

    fn scale(&self, factor: Vector2DScaleInput) -> PyResult<Self> {
        let scaled = self.curve.scale(factor)?;
        validate_monotonic_x(&scaled.nodes).map_err(PyErr::from)?;
        Ok(Self {
            curve: scaled,
            extrapolate: self.extrapolate,
        })
    }

    #[pyo3(name = "move")]
    fn r#move(&self, offset: Vector2DInput) -> PyResult<Self> {
        let moved = self.curve.r#move(offset)?;
        Ok(Self {
            curve: moved,
            extrapolate: self.extrapolate,
        })
    }

    fn add(&self, other: &Interpolation) -> Result<Self, SimpleError> {
        let mut nodes_new = Vec::new();

        for node in &self.curve.nodes {
            let x = node.x;
            nodes_new.push(Vector2D {
                x,
                y: node.y + other.get_value(x)?,
            });
        }

        validated(Self {
            curve: PolyLine2D { nodes: nodes_new },
            extrapolate: self.extrapolate || other.extrapolate,
        })
    }

    fn sub(&self, other: &Interpolation) -> Result<Self, SimpleError> {
        validated(Self {
            curve: self.curve.sub(&other.curve)?,
            extrapolate: self.extrapolate || other.extrapolate,
        })
    }

    fn scale_nodes(&self, factors: Vec<f64>) -> Result<Self, SimpleError> {
        validated(Self { curve: self.curve.scale_nodes(factors)?, extrapolate: self.extrapolate })
    }

    fn reverse(&self) -> Self {
        Self { curve: self.curve.reverse(), extrapolate: self.extrapolate }
    }

    fn mix(&self, other: &Interpolation, factor: f64) -> Result<Self, SimpleError> {
        validated(Self {
            curve: self.curve.mix(&other.curve, factor)?,
            extrapolate: self.extrapolate || other.extrapolate,
        })
    }

    fn get_value(&self, value: f64) -> Result<f64, SimpleError> {
        if self.curve.nodes.len() < 2 {
            return Err(no_cut_error(value));
        }

        let nodes = &self.curve.nodes;
        let Some(increasing) = monotonic_direction(nodes) else {
            return Err(SimpleError::new(
                "Interpolation input data must be monotonic in x",
            ));
        };

        let x_min = nodes.iter().map(|node| node.x).fold(f64::INFINITY, f64::min);
        let x_max = nodes.iter().map(|node| node.x).fold(f64::NEG_INFINITY, f64::max);

        if value < x_min || value > x_max {
            if !self.extrapolate {
                return Err(no_cut_error(value));
            }

            let (left, right) = if value < x_min {
                if increasing {
                    first_nonzero_segment(nodes, true)
                } else {
                    first_nonzero_segment(nodes, false)
                }
            } else {
                if increasing {
                    first_nonzero_segment(nodes, false)
                } else {
                    first_nonzero_segment(nodes, true)
                }
            }
            .ok_or_else(|| SimpleError::new("Interpolation requires at least one non-zero x segment"))?;

            let slope = (right.y - left.y) / (right.x - left.x);
            return Ok(left.y + slope * (value - left.x));
        }

        for index in 0..nodes.len() - 1 {
            let left = nodes[index];
            let right = nodes[index + 1];
            let low = left.x.min(right.x);
            let high = left.x.max(right.x);

            if low <= value && value <= high {
                let dx = right.x - left.x;
                if dx.abs() <= X_EPS {
                    return Ok(left.y);
                }
                let t = (value - left.x) / dx;
                return Ok(left.y * (1.0 - t) + right.y * t);
            }
        }

        Err(no_cut_error(value))
    }

    fn __mul__(&self, factor: f64) -> Self {
        Self {
            curve: PolyLine2D {
                nodes: self.curve.nodes.iter().map(|node| Vector2D { x: node.x, y: node.y * factor }).collect(),
            },
            extrapolate: self.extrapolate,
        }
    }

    fn __add__(&self, other: &Interpolation) -> Result<Self, SimpleError> { self.add(other) }
    fn __sub__(&self, other: &Interpolation) -> Result<Self, SimpleError> { self.sub(other) }
}