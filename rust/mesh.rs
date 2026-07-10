use pyo3::prelude::*;
use spade::{ConstrainedDelaunayTriangulation, Point2, RefinementParameters, Triangulation};
use std::collections::HashMap;

use crate::vector::{PolyLine2D, Vector2D, Vector3D};

#[pyclass(skip_from_py_object)]
#[derive(Clone, Debug)]
pub struct Triangulation2D {
    #[pyo3(get)]
    pub nodes: Vec<Vector2D>,
    #[pyo3(get)]
    pub triangles: Vec<(usize, usize, usize)>,
}

fn close_ring(nodes: &[Vector2D]) -> Vec<Vector2D> {
    if nodes.is_empty() {
        return Vec::new();
    }

    let mut ring = nodes.to_vec();
    if let (Some(first), Some(last)) = (ring.first().copied(), ring.last().copied()) {
        if first != last {
            ring.push(first);
        }
    }
    ring
}

fn ring_area(ring: &[Vector2D]) -> f64 {
    if ring.len() < 3 {
        return 0.0;
    }

    let mut area = 0.0;
    for pair in ring.windows(2) {
        area += pair[0].x * pair[1].y - pair[1].x * pair[0].y;
    }
    0.5 * area
}

fn point_in_ring(point: Vector2D, ring: &[Vector2D]) -> bool {
    if ring.len() < 4 {
        return false;
    }

    let mut inside = false;
    for pair in ring.windows(2) {
        let a = pair[0];
        let b = pair[1];
        let intersects = (a.y > point.y) != (b.y > point.y)
            && point.x < (b.x - a.x) * (point.y - a.y) / (b.y - a.y) + a.x;
        if intersects {
            inside = !inside;
        }
    }
    inside
}

fn classify_triangle(center: Vector2D, outline: &[Vector2D], holes: &[Vec<Vector2D>]) -> bool {
    if !point_in_ring(center, outline) {
        return false;
    }
    for hole in holes {
        if point_in_ring(center, hole) {
            return false;
        }
    }
    true
}

fn triangle_area_2d(a: Point2<f64>, b: Point2<f64>, c: Point2<f64>) -> f64 {
    ((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)).abs() * 0.5
}

fn add_ring_constraints(
    ring: &[Vector2D],
    cdt: &mut ConstrainedDelaunayTriangulation<Point2<f64>>,
    handles: &mut HashMap<(u64, u64), spade::handles::FixedVertexHandle>,
) -> PyResult<()> {
    if ring.len() < 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "each ring needs at least 3 distinct points",
        ));
    }

    let mut ring_handles = Vec::with_capacity(ring.len() - 1);
    for point in &ring[..ring.len() - 1] {
        let key = (point.x.to_bits(), point.y.to_bits());
        let handle = if let Some(existing) = handles.get(&key) {
            *existing
        } else {
            let inserted = cdt
                .insert(Point2::new(point.x, point.y))
                .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))?;
            handles.insert(key, inserted);
            inserted
        };
        ring_handles.push(handle);
    }

    for edge in ring_handles.windows(2) {
        cdt.add_constraint(edge[0], edge[1]);
    }
    cdt.add_constraint(*ring_handles.last().unwrap(), ring_handles[0]);

    Ok(())
}

#[pyfunction(signature = (outline, holes, min_area = None, max_area = None))]
pub(crate) fn triangulate_with_holes(
    outline: PolyLine2D,
    holes: Vec<PolyLine2D>,
    min_area: Option<f64>,
    max_area: Option<f64>,
) -> PyResult<Triangulation2D> {
    let outline_ring = close_ring(&outline.nodes);
    if outline_ring.len() < 4 {
        return Err(pyo3::exceptions::PyValueError::new_err(
            "outline needs at least 3 distinct points",
        ));
    }

    let mut hole_rings = Vec::with_capacity(holes.len());
    for hole in holes {
        let ring = close_ring(&hole.nodes);
        if ring.len() < 4 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "each hole needs at least 3 distinct points",
            ));
        }
        hole_rings.push(ring);
    }

    let mut cdt: ConstrainedDelaunayTriangulation<Point2<f64>> = ConstrainedDelaunayTriangulation::new();
    let mut handle_by_point: HashMap<(u64, u64), spade::handles::FixedVertexHandle> = HashMap::new();

    add_ring_constraints(&outline_ring, &mut cdt, &mut handle_by_point)?;
    for hole in &hole_rings {
        add_ring_constraints(hole, &mut cdt, &mut handle_by_point)?;
    }

    if let Some(value) = min_area {
        if value <= 0.0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "min_area must be > 0",
            ));
        }
    }

    if let Some(value) = max_area {
        if value <= 0.0 {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "max_area must be > 0",
            ));
        }
    }

    if let (Some(min_area), Some(max_area)) = (min_area, max_area) {
        if min_area > max_area {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "min_area must be <= max_area",
            ));
        }
    }

    if max_area.is_some() {
        let mut refinement = RefinementParameters::<f64>::new()
            .exclude_outer_faces(true)
            .keep_constraint_edges();

        if let Some(min_area) = min_area {
            refinement = refinement.with_min_required_area(min_area);
        }
        if let Some(max_area) = max_area {
            refinement = refinement.with_max_allowed_area(max_area);
        }

        let result = cdt.refine(refinement);
        if !result.refinement_complete {
            return Err(pyo3::exceptions::PyRuntimeError::new_err(
                "spade refinement did not complete; consider relaxing area limits",
            ));
        }
    }

    let mut node_index_by_handle = HashMap::new();
    let mut nodes = Vec::with_capacity(cdt.num_vertices());
    for (index, vertex) in cdt.vertices().enumerate() {
        let handle = vertex.fix();
        let pos = vertex.position();
        node_index_by_handle.insert(handle, index);
        nodes.push(Vector2D { x: pos.x, y: pos.y });
    }

    let mut triangles = Vec::new();
    for face in cdt.inner_faces() {
        let verts = face.vertices();
        let p0 = verts[0].position();
        let p1 = verts[1].position();
        let p2 = verts[2].position();
        let center = Vector2D {
            x: (p0.x + p1.x + p2.x) / 3.0,
            y: (p0.y + p1.y + p2.y) / 3.0,
        };

        if let Some(min_area) = min_area {
            if triangle_area_2d(p0, p1, p2) < min_area {
                continue;
            }
        }

        if !classify_triangle(center, &outline_ring, &hole_rings) {
            continue;
        }

        let i0 = *node_index_by_handle.get(&verts[0].fix()).unwrap();
        let i1 = *node_index_by_handle.get(&verts[1].fix()).unwrap();
        let i2 = *node_index_by_handle.get(&verts[2].fix()).unwrap();
        triangles.push((i0, i1, i2));
    }

    if ring_area(&outline_ring) < 0.0 {
        triangles.iter_mut().for_each(|(a, b, _)| std::mem::swap(a, b));
    }

    Ok(Triangulation2D { nodes, triangles })
}

#[pyfunction]
pub(crate) fn find_duplicates(points: Vec<Vector3D>, max_distance: f64) -> Vec<(usize, usize)> {
    let mut duplicates = Vec::new();
    for first_index in 0..points.len() {
        for second_index in first_index + 1..points.len() {
            if points[first_index].distance(&points[second_index]) < max_distance {
                duplicates.push((first_index, second_index));
            }
        }
    }
    duplicates
}

#[pymodule(submodule, name = "mesh")]
pub(crate) mod mesh_mod {
    #[pymodule_export]
    use super::find_duplicates;
    #[pymodule_export]
    use super::triangulate_with_holes;
    #[pymodule_export]
    use super::Triangulation2D;
}
