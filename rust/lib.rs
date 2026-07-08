use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

mod mesh;
mod plane;
mod spline;
mod vector;

#[pyfunction]
#[pyo3(signature = (a, b, c))]
fn triangle_area(a: f64, b: f64, c: f64) -> PyResult<f64> {
    let semi_perimeter = (a + b + c) / 2.0;
    let area_squared = semi_perimeter
        * (semi_perimeter - a)
        * (semi_perimeter - b)
        * (semi_perimeter - c);

    if area_squared.is_sign_negative() {
        return Err(PyValueError::new_err("invalid triangle side lengths"));
    }

    Ok(area_squared.sqrt())
}

#[pyfunction]
fn version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pymodule]
fn rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(triangle_area, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;

    vector::register(m)?;
    spline::register(m)?;
    plane::register(m)?;
    mesh::register(m)?;

    Ok(())
}