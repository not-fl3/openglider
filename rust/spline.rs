use pyo3::prelude::*;
use pyo3::types::{PyAny, PyModule};
use nalgebra::{DMatrix, DVector};

use crate::vector::{extract_vector2d, Interpolation, PolyLine2D, Vector2D};

#[derive(Clone, Copy)]
enum CurveBase {
    Bezier,
    BSpline(usize),
}

fn choose(n: usize, k: usize) -> f64 {
    if k > n {
        return 0.0;
    }

    let mut n_value = n;
    let mut ntok = 1.0;
    let mut ktok = 1.0;
    let range = usize::min(k, n - k) + 1;
    for t in 1..range {
        ntok *= n_value as f64;
        ktok *= t as f64;
        n_value = n_value.saturating_sub(1);
    }
    ntok / ktok
}

fn bezier_basis(size: usize, index: usize, x: f64) -> f64 {
    if size == 0 || index >= size {
        return 0.0;
    }
    let coeff = choose(size - 1, index);
    coeff * x.powi(index as i32) * (1.0 - x).powi((size - 1 - index) as i32)
}

fn bspline_knots(size: usize, degree: usize) -> Option<Vec<f64>> {
    if size < 2 {
        return None;
    }
    let total_knots = size + degree + 1;
    let double_degree = 2 * degree;
    if total_knots < double_degree {
        return None;
    }
    let inner_knots = total_knots - double_degree;
    if inner_knots < 2 {
        return None;
    }

    let mut knots = Vec::with_capacity(total_knots);
    for _ in 0..degree {
        knots.push(0.0);
    }
    for i in 0..inner_knots {
        knots.push(i as f64 / (inner_knots - 1) as f64);
    }
    for _ in 0..degree {
        knots.push(1.0);
    }
    Some(knots)
}

fn bspline_basis(knots: &[f64], degree: usize, index: usize, x: f64) -> f64 {
    if index + degree + 1 >= knots.len() {
        return 0.0;
    }

    if degree == 0 {
        if knots[index] < x && x <= knots[index + 1] {
            return 1.0;
        }
        return 0.0;
    }

    if index == 0 && x <= 0.0 {
        return 1.0;
    }

    let mut out = 0.0;

    let t_this = knots[index];
    let t_next = knots[index + 1];
    let t_precog = knots[index + degree];
    let t_horizon = knots[index + degree + 1];

    let bottom_1 = t_precog - t_this;
    if bottom_1 != 0.0 {
        out += (x - t_this) / bottom_1 * bspline_basis(knots, degree - 1, index, x);
    }

    let bottom_2 = t_horizon - t_next;
    if bottom_2 > 1e-8 {
        out += (t_horizon - x) / bottom_2 * bspline_basis(knots, degree - 1, index + 1, x);
    }

    out
}

fn evaluate_curve(nodes: &[Vector2D], base: CurveBase, value: f64) -> Vector2D {
    if nodes.is_empty() {
        return Vector2D::zero();
    }

    let mut result_x = 0.0;
    let mut result_y = 0.0;
    match base {
        CurveBase::Bezier => {
            for (index, point) in nodes.iter().copied().enumerate() {
                let weight = bezier_basis(nodes.len(), index, value);
                result_x += point.x * weight;
                result_y += point.y * weight;
            }
        }
        CurveBase::BSpline(degree) => {
            if let Some(knots) = bspline_knots(nodes.len(), degree) {
                for (index, point) in nodes.iter().copied().enumerate() {
                    let weight = bspline_basis(&knots, degree, index, value);
                    result_x += point.x * weight;
                    result_y += point.y * weight;
                }
            } else {
                return *nodes.last().unwrap_or(&nodes[0]);
            }
        }
    }

    Vector2D { x: result_x, y: result_y }
}

fn basis_value(base: CurveBase, size: usize, index: usize, value: f64) -> f64 {
    match base {
        CurveBase::Bezier => bezier_basis(size, index, value),
        CurveBase::BSpline(degree) => {
            if let Some(knots) = bspline_knots(size, degree) {
                bspline_basis(&knots, degree, index, value)
            } else {
                0.0
            }
        }
    }
}

fn fit_curve_with_base(curve_nodes: &[Vector2D], numpoints: usize, base: CurveBase) -> PyResult<Vec<Vector2D>> {
    if curve_nodes.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("curve is empty"));
    }
    if numpoints < 2 {
        return Err(pyo3::exceptions::PyValueError::new_err("numpoints must be >= 2"));
    }
    if numpoints > curve_nodes.len() {
        return Err(pyo3::exceptions::PyValueError::new_err("numpoints > line_points"));
    }

    if numpoints == 2 {
        return Ok(vec![curve_nodes[0], curve_nodes[curve_nodes.len() - 1]]);
    }

    let rows = curve_nodes.len();
    let cols = numpoints;

    let mut a1 = DMatrix::<f64>::zeros(rows, cols - 2);
    let mut a2 = DMatrix::<f64>::zeros(rows, 2);

    for row in 0..rows {
        let t = if rows > 1 { row as f64 / (rows - 1) as f64 } else { 0.0 };

        for col in 1..cols - 1 {
            a1[(row, col - 1)] = basis_value(base, cols, col, t);
        }

        a2[(row, 0)] = basis_value(base, cols, 0, t);
        a2[(row, 1)] = basis_value(base, cols, cols - 1, t);
    }

    let a1_t = a1.transpose();
    let lhs = &a1_t * &a1;
    let a1_t_a2 = &a1_t * &a2;

    let start = curve_nodes[0];
    let end = curve_nodes[rows - 1];

    let solve_dim = |extract: fn(Vector2D) -> f64| -> PyResult<DVector<f64>> {
        let p1 = DVector::<f64>::from_iterator(rows, curve_nodes.iter().copied().map(extract));
        let p2 = DVector::<f64>::from_vec(vec![extract(start), extract(end)]);
        let rhs = &a1_t * p1 - &a1_t_a2 * p2;
        lhs.clone()
            .lu()
            .solve(&rhs)
            .ok_or_else(|| pyo3::exceptions::PyValueError::new_err("failed to solve spline fit"))
    };

    let x_solution = solve_dim(|point| point.x)?;
    let y_solution = solve_dim(|point| point.y)?;

    let mut nodes_new = Vec::with_capacity(cols);
    nodes_new.push(start);
    for idx in 0..cols - 2 {
        nodes_new.push(Vector2D {
            x: x_solution[idx],
            y: y_solution[idx],
        });
    }
    nodes_new.push(end);

    Ok(nodes_new)
}

fn fit_symmetric_curve_with_base(curve_nodes: &[Vector2D], node_num: usize, base: CurveBase) -> PyResult<Vec<Vector2D>> {
    if curve_nodes.is_empty() {
        return Err(pyo3::exceptions::PyValueError::new_err("curve is empty"));
    }

    let mirrored: Vec<Vector2D> = curve_nodes
        .iter()
        .copied()
        .map(|point| Vector2D { x: -point.x, y: point.y })
        .collect();

    let mut combined = Vec::with_capacity(curve_nodes.len() * 2 + 1);
    combined.push(mirrored[0]);

    let first_delta = Vector2D {
        x: curve_nodes[0].x - mirrored[0].x,
        y: curve_nodes[0].y - mirrored[0].y,
    };
    if (first_delta.x * first_delta.x + first_delta.y * first_delta.y).sqrt() > 1e-6 {
        combined.push(curve_nodes[0]);
    }

    for index in 1..curve_nodes.len() {
        combined.insert(0, mirrored[index]);
        combined.push(curve_nodes[index]);
    }

    let fitted_full = fit_curve_with_base(&combined, 2 * node_num, base)?;
    if fitted_full.len() < 2 * node_num {
        return Err(pyo3::exceptions::PyValueError::new_err("invalid fitted symmetric controlpoint count"));
    }

    Ok(fitted_full[node_num..(2 * node_num)].to_vec())
}

fn sample_curve(nodes: &[Vector2D], base: CurveBase, num: usize) -> Vec<Vector2D> {
    if nodes.is_empty() {
        return Vec::new();
    }
    if num == 0 {
        return Vec::new();
    }
    if num == 1 {
        return vec![evaluate_curve(nodes, base, 0.0)];
    }

    let mut result = Vec::with_capacity(num);
    for i in 0..num {
        let t = i as f64 / (num - 1) as f64;
        result.push(evaluate_curve(nodes, base, t));
    }
    result
}

fn symmetric_nodes(nodes: &[Vector2D]) -> Vec<Vector2D> {
    let mut combined = Vec::with_capacity(nodes.len() * 2);
    for point in nodes.iter().rev() {
        combined.push(Vector2D { x: -point.x, y: point.y });
    }
    combined.extend_from_slice(nodes);
    combined
}

fn segment_vectors(nodes: &[Vector2D]) -> Vec<Vector2D> {
    nodes
        .windows(2)
        .map(|pair| Vector2D {
            x: pair[1].x - pair[0].x,
            y: pair[1].y - pair[0].y,
        })
        .collect()
}

fn derivative_nodes(nodes: &[Vector2D]) -> Vec<Vector2D> {
    let mut segments = segment_vectors(nodes);
    if segments.len() == 1 {
        segments.push(segments[0]);
    }
    segments
}

fn curvature_bspline(nodes: &[Vector2D], degree: usize, num: usize) -> Vec<Vector2D> {
    if num == 0 {
        return Vec::new();
    }

    let d1_nodes = derivative_nodes(nodes);
    if d1_nodes.is_empty() {
        return (0..num)
            .map(|i| Vector2D {
                x: if num > 1 { i as f64 / (num - 1) as f64 } else { 0.0 },
                y: 0.0,
            })
            .collect();
    }

    let d1_degree = if degree > 1 { degree - 1 } else { 1 };
    let d2_nodes = derivative_nodes(&d1_nodes);
    let d2_degree = if d1_degree > 1 { d1_degree - 1 } else { 1 };

    let mut result = Vec::with_capacity(num);
    for i in 0..num {
        let t = if num > 1 { i as f64 / (num - 1) as f64 } else { 0.0 };
        let v = evaluate_curve(&d1_nodes, CurveBase::BSpline(d1_degree), t);
        let a = evaluate_curve(&d2_nodes, CurveBase::BSpline(d2_degree), t);

        let cross = a.x * v.y - a.y * v.x;
        let speed = (v.x * v.x + v.y * v.y).sqrt();
        let kappa = if speed > 1e-12 {
            cross / speed.powi(3)
        } else {
            f64::NAN
        };

        result.push(Vector2D { x: t, y: kappa });
    }

    result
}

fn curvature_for_curve(base: CurveBase, controlpoints: &[Vector2D], num: usize, symmetric: bool) -> Vec<Vector2D> {
    if num == 0 {
        return Vec::new();
    }

    match (base, symmetric) {
        (CurveBase::BSpline(degree), false) => curvature_bspline(controlpoints, degree, num),
        (CurveBase::BSpline(degree), true) => {
            let full_nodes = symmetric_nodes(controlpoints);
            let mut curvature = curvature_bspline(&full_nodes, degree, 2 * num - 1);
            let start = num.saturating_sub(1);
            if start < curvature.len() {
                curvature = curvature[start..].to_vec();
            } else {
                curvature.clear();
            }
            for node in &mut curvature {
                node.x = (node.x - 0.5) * 2.0;
            }
            curvature
        }
        _ => curvature_nodes(&sample_curve(controlpoints, base, num)),
    }
}

fn curvature_nodes(nodes: &[Vector2D]) -> Vec<Vector2D> {
    let mut result = Vec::new();
    if nodes.len() < 3 {
        return result;
    }
    for index in 1..nodes.len() - 1 {
        let previous = nodes[index - 1];
        let current = nodes[index];
        let next = nodes[index + 1];
        let left = Vector2D { x: current.x - previous.x, y: current.y - previous.y };
        let right = Vector2D { x: next.x - current.x, y: next.y - current.y };
        let cross = (left.x * right.y - left.y * right.x).abs();
        let left_length = (left.x * left.x + left.y * left.y).sqrt();
        let right_length = (right.x * right.x + right.y * right.y).sqrt();
        let diagonal = Vector2D { x: left.x + right.x, y: left.y + right.y };
        let diagonal_length = (diagonal.x * diagonal.x + diagonal.y * diagonal.y).sqrt();
        let denom = (left_length * right_length * (diagonal_length + 1e-12)).max(1e-12);
        result.push(Vector2D { x: index as f64, y: cross / denom });
    }
    result
}

macro_rules! define_curve_type {
    ($name:ident, $has_derivate:expr, $base:expr, $symmetric:expr) => {
        #[pyclass]
        #[derive(Clone, Debug)]
        pub struct $name {
            pub controlpoints: PolyLine2D,
            numpoints: usize,
        }

        #[pymethods]
        impl $name {
            #[getter(controlpoints)]
            fn get_controlpoints(&self) -> PolyLine2D {
                self.controlpoints.clone()
            }

            #[setter(controlpoints)]
            fn set_controlpoints(&mut self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<()> {
                if let Ok(polyline) = value.extract::<PolyLine2D>() {
                    self.controlpoints = polyline;
                    return Ok(());
                }

                let points = value.extract::<Vec<Py<PyAny>>>()?;
                let mut parsed = Vec::with_capacity(points.len());
                for point in points {
                    parsed.push(extract_vector2d(point.bind(py).as_any())?);
                }
                self.controlpoints = PolyLine2D { nodes: parsed };
                Ok(())
            }

            #[new]
            fn new(py: Python<'_>, controlpoints: Vec<Py<PyAny>>) -> PyResult<Self> {
                let mut parsed = Vec::with_capacity(controlpoints.len());
                for point in controlpoints {
                    parsed.push(extract_vector2d(point.bind(py).as_any())?);
                }
                Ok(Self { controlpoints: PolyLine2D { nodes: parsed }, numpoints: 100 })
            }

            fn copy(&self) -> Self {
                self.clone()
            }

            fn get(&self, value: f64) -> Vector2D {
                if $symmetric {
                    let nodes = symmetric_nodes(&self.controlpoints.nodes);
                    evaluate_curve(&nodes, $base, 0.5 + value / 2.0)
                } else {
                    evaluate_curve(&self.controlpoints.nodes, $base, value)
                }
            }

            fn get_sequence(&self, num: usize) -> PolyLine2D {
                if $symmetric {
                    let nodes = symmetric_nodes(&self.controlpoints.nodes);
                    let mut sequence = Vec::with_capacity(num.saturating_add(1));
                    if num == 0 {
                        sequence.push(evaluate_curve(&nodes, $base, 0.5));
                    } else {
                        for index in 0..=num {
                            let t = 0.5 + index as f64 / (2.0 * num as f64);
                            sequence.push(evaluate_curve(&nodes, $base, t));
                        }
                    }
                    PolyLine2D { nodes: sequence }
                } else {
                    let mut sequence = Vec::with_capacity(num.saturating_add(1));
                    if num == 0 {
                        sequence.push(evaluate_curve(&self.controlpoints.nodes, $base, 0.0));
                    } else {
                        for index in 0..=num {
                            let t = index as f64 / num as f64;
                            sequence.push(evaluate_curve(&self.controlpoints.nodes, $base, t));
                        }
                    }
                    PolyLine2D { nodes: sequence }
                }
            }

            #[staticmethod]
            fn fit(curve: PolyLine2D, numpoints: usize) -> PyResult<Self> {
                let nodes = if $symmetric {
                    fit_symmetric_curve_with_base(&curve.nodes, numpoints, $base)?
                } else {
                    fit_curve_with_base(&curve.nodes, numpoints, $base)?
                };

                Ok(Self {
                    controlpoints: PolyLine2D { nodes },
                    numpoints,
                })
            }

            fn set_numpoints(&mut self, numpoints: usize) -> PyResult<()> {
                let nodes = self.get_sequence(100).nodes;
                let refitted = Self::fit(PolyLine2D { nodes }, numpoints)?;
                self.controlpoints = refitted.controlpoints;
                self.numpoints = numpoints;
                Ok(())
            }

            fn get_numpoints(&self) -> usize {
                self.controlpoints.nodes.len()
            }

            #[getter(numpoints)]
            fn get_numpoints_property(&self) -> usize {
                self.numpoints
            }

            #[setter(numpoints)]
            fn set_numpoints_property(&mut self, value: usize) -> PyResult<()> {
                self.set_numpoints(value)
            }

            fn get_derivate(&self) -> PyResult<Self> {
                if $has_derivate {
                    Ok(self.clone())
                } else {
                    Err(pyo3::exceptions::PyAttributeError::new_err("get_derivate is only available for BSpline curves"))
                }
            }

            fn get_curvature(&self, num: usize) -> Interpolation {
                Interpolation {
                    curve: PolyLine2D { nodes: curvature_for_curve($base, &self.controlpoints.nodes, num, $symmetric) },
                    extrapolate: true,
                }
            }

            fn __copy__(&self) -> Self {
                self.clone()
            }

            fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self {
                self.clone()
            }
        }
    };
}

define_curve_type!(BezierCurve, false, CurveBase::Bezier, false);
define_curve_type!(LinSplineCurve, true, CurveBase::BSpline(1), false);
define_curve_type!(BSplineCurve, true, CurveBase::BSpline(2), false);
define_curve_type!(CubicBSplineCurve, true, CurveBase::BSpline(3), false);
define_curve_type!(QuadBSplineCurve, true, CurveBase::BSpline(4), false);
define_curve_type!(SymmetricBSplineCurve, false, CurveBase::BSpline(2), true);
define_curve_type!(SymmetricCubicBSplineCurve, false, CurveBase::BSpline(3), true);
define_curve_type!(SymmetricQuadBSplineCurve, false, CurveBase::BSpline(4), true);
define_curve_type!(SymmetricBezierCurve, false, CurveBase::Bezier, true);

#[pymodule(submodule, name = "spline")]
pub(crate) mod spline_mod {
    #[pymodule_export]
    use super::BSplineCurve;
    #[pymodule_export]
    use super::BezierCurve;
    #[pymodule_export]
    use super::CubicBSplineCurve;
    #[pymodule_export]
    use super::LinSplineCurve;
    #[pymodule_export]
    use super::QuadBSplineCurve;
    #[pymodule_export]
    use super::SymmetricBSplineCurve;
    #[pymodule_export]
    use super::SymmetricBezierCurve;
    #[pymodule_export]
    use super::SymmetricCubicBSplineCurve;
    #[pymodule_export]
    use super::SymmetricQuadBSplineCurve;
}
