use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use spade::{DelaunayTriangulation, HasPosition, Point2, Triangulation};

use crate::vector::{PolyLine2D, Vector2D};

#[derive(Clone, Debug)]
struct IndexedPoint {
    point: Point2<f64>,
    index: usize,
}

impl HasPosition for IndexedPoint {
    type Scalar = f64;

    fn position(&self) -> Point2<Self::Scalar> {
        self.point
    }
}

fn close_ring(nodes: &[Vector2D]) -> Vec<Vector2D> {
    if nodes.len() < 2 {
        return nodes.to_vec();
    }

    let mut ring = nodes.to_vec();
    if ring.first() == ring.last() {
        ring.pop();
    }
    ring
}

fn ring_area(ring: &[Vector2D]) -> f64 {
    if ring.len() < 3 {
        return 0.0;
    }

    let mut area = 0.0;
    for i in 0..ring.len() {
        let current = ring[i];
        let next = ring[(i + 1) % ring.len()];
        area += current.x * next.y - next.x * current.y;
    }
    0.5 * area
}

fn line_intersection_parameter(a: Vector2D, b: Vector2D, normal: Vector2D, threshold: f64) -> Option<f64> {
    let direction = Vector2D {
        x: b.x - a.x,
        y: b.y - a.y,
    };
    let denominator = normal.x * direction.x + normal.y * direction.y;
    if denominator.abs() < 1e-12 {
        return None;
    }

    let numerator = threshold - (normal.x * a.x + normal.y * a.y);
    Some(numerator / denominator)
}

fn segment_half_plane_intersection(
    current: Vector2D,
    next: Vector2D,
    normal: Vector2D,
    threshold: f64,
) -> Option<Vector2D> {
    let t = line_intersection_parameter(current, next, normal, threshold)?;
    if !(0.0..=1.0).contains(&t) {
        return None;
    }

    Some(Vector2D {
        x: current.x + (next.x - current.x) * t,
        y: current.y + (next.y - current.y) * t,
    })
}

fn clip_with_half_plane(polygon: &[Vector2D], normal: Vector2D, threshold: f64) -> Vec<Vector2D> {
    if polygon.is_empty() {
        return Vec::new();
    }

    let mut result = Vec::new();
    let epsilon = 1e-10;

    for i in 0..polygon.len() {
        let current = polygon[i];
        let next = polygon[(i + 1) % polygon.len()];

        let current_value = normal.x * current.x + normal.y * current.y - threshold;
        let next_value = normal.x * next.x + normal.y * next.y - threshold;
        let current_inside = current_value <= epsilon;
        let next_inside = next_value <= epsilon;

        if current_inside && next_inside {
            result.push(next);
            continue;
        }

        if current_inside && !next_inside {
            if let Some(intersection) = segment_half_plane_intersection(current, next, normal, threshold) {
                result.push(intersection);
            }
            continue;
        }

        if !current_inside && next_inside {
            if let Some(intersection) = segment_half_plane_intersection(current, next, normal, threshold) {
                result.push(intersection);
            }
            result.push(next);
        }
    }

    result
}

fn deduplicate_neighbors(points: Vec<Point2<f64>>) -> Vec<Point2<f64>> {
    let mut unique = Vec::with_capacity(points.len());

    for point in points {
        let exists = unique.iter().any(|existing: &Point2<f64>| {
            existing.x.to_bits() == point.x.to_bits() && existing.y.to_bits() == point.y.to_bits()
        });
        if !exists {
            unique.push(point);
        }
    }

    unique
}

fn clipped_voronoi_cell(outline: &[Vector2D], seed: Point2<f64>, neighbors: &[Point2<f64>]) -> Option<PolyLine2D> {
    let mut polygon = outline.to_vec();

    for neighbor in neighbors {
        let normal = Vector2D {
            x: neighbor.x - seed.x,
            y: neighbor.y - seed.y,
        };
        let threshold = 0.5
            * ((neighbor.x * neighbor.x + neighbor.y * neighbor.y)
                - (seed.x * seed.x + seed.y * seed.y));

        polygon = clip_with_half_plane(&polygon, normal, threshold);
        if polygon.len() < 3 {
            return None;
        }
    }

    if polygon.len() < 3 {
        return None;
    }

    Some(PolyLine2D { nodes: polygon })
}

#[pyfunction]
pub(crate) fn voronoi_areas(outline: PolyLine2D, inside: Vec<Vector2D>) -> PyResult<Vec<Option<PolyLine2D>>> {
    let mut outline_ring = close_ring(&outline.nodes);
    if outline_ring.len() < 3 {
        return Err(PyValueError::new_err(
            "outline needs at least 3 distinct points",
        ));
    }

    if ring_area(&outline_ring) < 0.0 {
        outline_ring.reverse();
    }

    if inside.is_empty() {
        return Ok(Vec::new());
    }

    let mut triangulation: DelaunayTriangulation<IndexedPoint> = DelaunayTriangulation::new();
    for (index, point) in inside.iter().enumerate() {
        triangulation
            .insert(IndexedPoint {
                point: Point2::new(point.x, point.y),
                index,
            })
            .map_err(|error| PyValueError::new_err(format!("failed to insert point {index}: {error}")))?;
    }

    let mut result = vec![None; inside.len()];

    if triangulation.num_vertices() == 1 {
        result[0] = Some(PolyLine2D {
            nodes: outline_ring,
        });
        return Ok(result);
    }

    for vertex in triangulation.vertices() {
        let data = vertex.data();
        let seed_index = data.index;
        let seed = data.point;

        let neighbors = vertex
            .out_edges()
            .map(|edge| edge.to().position())
            .collect::<Vec<_>>();
        let neighbors = deduplicate_neighbors(neighbors);

        result[seed_index] = clipped_voronoi_cell(&outline_ring, seed, &neighbors);
    }

    Ok(result)
}

#[pymodule(submodule, name = "voronoi")]
pub(crate) mod voronoi_mod {
    #[pymodule_export]
    use super::voronoi_areas;
}