use pyo3::prelude::*;

use crate::vector::Vector3D;

#[pyfunction]
pub(crate) fn find_duplicates(points: Vec<Vector3D>, max_distance: f64) -> Vec<(usize, usize)> {
    let mut duplicates = Vec::new();
    for first_index in 0..points.len() {
        for second_index in first_index + 1..points.len() {
            if points[first_index].distance(&points[second_index]) <= max_distance {
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
}
