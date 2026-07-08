use pyo3::prelude::*;
use pyo3::types::PyModule;

use crate::vector::Vector3D;

#[pyfunction]
fn find_duplicates(points: Vec<Vector3D>, max_distance: f64) -> Vec<(usize, usize)> {
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

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();
    let submodule = PyModule::new(py, "mesh")?;
    submodule.add_function(wrap_pyfunction!(find_duplicates, &submodule)?)?;
    m.add_submodule(&submodule)?;

    // Keep top-level helper for backward compatibility while also exposing euklid-style rs.mesh.
    m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;
    Ok(())
}
