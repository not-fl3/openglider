use pyo3::prelude::*;
use pyo3::types::{PyAny, PyList};

use super::signature::*;
use super::vector::*;
use super::polyline::{PolyLine2D};


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
    #[pyo3(signature = (nodes, extrapolate = false))]
    fn new(nodes: InterpolationNodesInput, extrapolate: bool, py: Python<'_>) -> PyResult<Self> {
        match nodes {
            InterpolationNodesInput::Interpolation(interpolation) => {
                let interpolation = interpolation.bind(py).borrow();
                Ok(Self { curve: interpolation.curve.clone(), extrapolate })
            }
            InterpolationNodesInput::PolyLine(polyline) => {
                let polyline = polyline.bind(py).borrow();
                Ok(Self { curve: polyline.clone(), extrapolate })
            }
            InterpolationNodesInput::Points(points) => {
                let mut parsed = Vec::with_capacity(points.len());
                for point in points {
                    parsed.push(point.into_vector()?);
                }
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

    fn add(&self, other: &Interpolation) -> Self {
        // create new nodes
        let mut nodes_new = Vec::new();

        // iterate over self nodes and add the value of other at the same x position
        for node in &self.curve.nodes {
            let x = node.x;
            nodes_new.push(Vector2D {
                x,
                y: node.y + other.get_value(x),
            });
        }

        Self {
            curve: PolyLine2D { nodes: nodes_new },
            extrapolate: self.extrapolate || other.extrapolate,
        }
    }

    fn sub(&self, other: &Interpolation) -> Self {
        Self {
            curve: self.curve.sub(&other.curve),
            extrapolate: self.extrapolate || other.extrapolate,
        }
    }

    fn scale_nodes(&self, factors: Vec<f64>) -> Self {
        Self { curve: self.curve.scale_nodes(factors), extrapolate: self.extrapolate }
    }

    fn reverse(&self) -> Self {
        Self { curve: self.curve.reverse(), extrapolate: self.extrapolate }
    }

    fn mix(&self, other: &Interpolation, factor: f64) -> Self {
        Self {
            curve: self.curve.mix(&other.curve, factor),
            extrapolate: self.extrapolate || other.extrapolate,
        }
    }

    fn get_value(&self, value: f64) -> f64 {
        if self.curve.nodes.is_empty() {
            return 0.0;
        }
        if self.curve.nodes.len() == 1 {
            return self.curve.nodes[0].y;
        }
        let xs = &self.curve.nodes;
        if value <= xs[0].x {
            if self.extrapolate {
                let slope = (xs[1].y - xs[0].y) / (xs[1].x - xs[0].x + 1e-18);
                return xs[0].y + slope * (value - xs[0].x);
            }
            return xs[0].y;
        }
        if value >= xs[xs.len() - 1].x {
            if self.extrapolate {
                let last = xs.len() - 1;
                let slope = (xs[last].y - xs[last - 1].y) / (xs[last].x - xs[last - 1].x + 1e-18);
                return xs[last].y + slope * (value - xs[last].x);
            }
            return xs[xs.len() - 1].y;
        }
        for index in 0..xs.len() - 1 {
            let left = xs[index];
            let right = xs[index + 1];
            if (left.x..=right.x).contains(&value) {
                let fraction = (value - left.x) / (right.x - left.x + 1e-18);
                return left.y * (1.0 - fraction) + right.y * fraction;
            }
        }
        0.0
    }

    fn __mul__(&self, factor: f64) -> Self {
        Self {
            curve: PolyLine2D {
                nodes: self.curve.nodes.iter().map(|node| Vector2D { x: node.x, y: node.y * factor }).collect(),
            },
            extrapolate: self.extrapolate,
        }
    }

    fn __add__(&self, other: &Interpolation) -> Self { self.add(other) }
    fn __sub__(&self, other: &Interpolation) -> Self { self.sub(other) }
}