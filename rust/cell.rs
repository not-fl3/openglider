use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::vector::{polyline_get, polyline_length, PolyLine2D, PolyLine3D, Vector2D, Vector3D, VectorOps};

fn get_point(
    p1: Vector2D,
    p2: Vector2D,
    l_0: f64,
    l_l: f64,
    l_r: f64,
    left: bool,
) -> Vector2D {
    let lx = (l_0.powi(2) + l_l.powi(2) - l_r.powi(2)) / (2.0 * l_0);
    let ly_sq = l_l.powi(2) - lx.powi(2);
    let ly = if ly_sq > 0.0 { ly_sq.sqrt() } else { 0.0 };
    let diff = p2.sub(p1).normalized();
    let diff_y = if left {
        Vector2D::from_xy(-diff.y, diff.x)
    } else {
        Vector2D::from_xy(diff.y, -diff.x)
    };

    p1.add(diff.scale(lx)).add(diff_y.scale(ly))
}

#[pyfunction]
#[pyo3(signature = (
    prof1,
    prof2,
    x_values_left,
    x_values_right,
    normvectors,
    ballooning_phi,
    ballooning_radius,
    y_value,
    ballooning = true,
    arc_argument = true,
    close_trailing_edge = false
))]
pub fn basic_cell_midrib(
    prof1: &PolyLine3D,
    prof2: &PolyLine3D,
    x_values_left: Vec<f64>,
    x_values_right: Vec<f64>,
    normvectors: &PolyLine3D,
    ballooning_phi: Vec<f64>,
    ballooning_radius: Vec<Option<f64>>,
    y_value: f64,
    ballooning: bool,
    arc_argument: bool,
    close_trailing_edge: bool,
) -> PyResult<(PolyLine3D, Vec<f64>)> {
    let node_len = [
        prof1.nodes.len(),
        prof2.nodes.len(),
        x_values_left.len(),
        x_values_right.len(),
        normvectors.nodes.len(),
        ballooning_phi.len(),
        ballooning_radius.len(),
    ]
    .into_iter()
    .min()
    .unwrap_or(0);

    if node_len == 0 {
        return Err(PyValueError::new_err("basic_cell_midrib requires non-empty profile data"));
    }

    let mut x_values = Vec::with_capacity(node_len);
    let mut nodes = Vec::with_capacity(node_len);

    for index in 0..node_len {
        let p1 = prof1.nodes[index];
        let p2 = prof2.nodes[index];
        let x_left = x_values_left[index];
        let x_right = x_values_right[index];
        x_values.push(x_left + y_value * (x_right - x_left));

        let mut distance = y_value;
        let mut height = 0.0;

        if ballooning {
            if close_trailing_edge && (index == 0 || index + 1 == node_len) {
                distance = y_value;
            } else if let Some(radius) = ballooning_radius[index] {
                let phi = ballooning_phi[index];
                if arc_argument {
                    let psi = phi * 2.0 * y_value;
                    distance = 0.5 - 0.5 * (phi - psi).sin() / phi.sin();
                    height = ((phi - psi).cos() - phi.cos()) * radius;
                } else {
                    let argument = ((2.0 * y_value - 1.0) * phi.sin()).clamp(-1.0, 1.0);
                    distance = y_value;
                    height = (argument.asin().cos() - phi.cos()) * radius;
                }
            }
        }

        let diff = p2.sub(p1);
        nodes.push(
            p1.add(diff.scale(distance))
                .add(normvectors.nodes[index].scale(height)),
        );
    }

    Ok((PolyLine3D { nodes }, x_values))
}

#[pyfunction]
#[pyo3(signature = (midribs, num_inner = None))]
pub fn flatten_midribs(
    midribs: Vec<PolyLine3D>,
    num_inner: Option<usize>,
) -> PyResult<(Vec<PolyLine2D>, (PolyLine2D, PolyLine2D))> {
    if midribs.is_empty() {
        return Err(PyValueError::new_err("flatten_midribs requires at least one midrib"));
    }

    let left_nodes = midribs[0].nodes.len();
    let right_nodes = midribs[midribs.len() - 1].nodes.len();
    let numpoints = left_nodes.min(right_nodes);
    if numpoints == 0 {
        return Err(PyValueError::new_err("flatten_midribs requires non-empty midribs"));
    }

    let sample_count = midribs.len();
    let sample_denominator = sample_count.saturating_sub(1).max(1) as f64;
    let get_length = |ik1: f64, ik2: f64| -> f64 {
        let points: Vec<Vector3D> = midribs
            .iter()
            .enumerate()
            .map(|(index, rib)| {
                let x = ik1 + index as f64 / sample_denominator * (ik2 - ik1);
                polyline_get(&rib.nodes, x)
            })
            .collect();
        polyline_length(&points)
    };

    let mut left_bal = vec![Vector2D::from_xy(0.0, 0.0)];
    let mut right_bal = vec![Vector2D::from_xy(get_length(0.0, 0.0), 0.0)];

    for index in 0..numpoints.saturating_sub(1) {
        let p1 = *left_bal.last().unwrap();
        let p2 = *right_bal.last().unwrap();

        let d_l = midribs[0].nodes[index].distance(midribs[0].nodes[index + 1]);
        let d_r = midribs[sample_count - 1].nodes[index].distance(midribs[sample_count - 1].nodes[index + 1]);
        let l_0 = get_length(index as f64, index as f64);
        let cross_length = get_length(index as f64, index as f64 + 1.0);
        let next_length = get_length(index as f64 + 1.0, index as f64 + 1.0);

        let pr_2 = get_point(p2, p1, l_0, d_r, cross_length, false);
        let pl_2 = get_point(p1, pr_2, cross_length, d_l, next_length, true);

        left_bal.push(pl_2);
        right_bal.push(pr_2);
    }

    let left = PolyLine2D { nodes: left_bal };
    let right = PolyLine2D { nodes: right_bal };

    let inner_count = num_inner.unwrap_or(sample_count + 2);
    let inner = if inner_count <= 1 {
        vec![left.clone()]
    } else {
        (0..inner_count)
            .map(|index| {
                let factor = index as f64 / (inner_count - 1) as f64;
                let nodes = left
                    .nodes
                    .iter()
                    .zip(right.nodes.iter())
                    .map(|(left_node, right_node)| left_node.scale(1.0 - factor).add(right_node.scale(factor)))
                    .collect();
                PolyLine2D { nodes }
            })
            .collect()
    };

    Ok((inner, (left, right)))
}