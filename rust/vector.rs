use nalgebra::{Matrix4, Vector4};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyList, PyModule};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

pub(crate) fn values_from_any(any: &Bound<'_, PyAny>) -> PyResult<Vec<f64>> {
    any.extract::<Vec<f64>>()
        .map_err(|_| PyTypeError::new_err("expected a sequence of floats"))
}

pub(crate) fn extract_vector2d(any: &Bound<'_, PyAny>) -> PyResult<Vector2D> {
    if let Ok(value) = any.extract::<Vector2D>() {
        return Ok(value);
    }
    Vector2D::from_components(&values_from_any(any)?)
}

pub(crate) fn extract_vector3d(any: &Bound<'_, PyAny>) -> PyResult<Vector3D> {
    if let Ok(value) = any.extract::<Vector3D>() {
        return Ok(value);
    }
    Vector3D::from_components(&values_from_any(any)?)
}

trait VectorOps: Sized + Copy + Clone {
    const DIMENSION: usize;

    fn zero() -> Self;
    fn from_components(values: &[f64]) -> PyResult<Self>;
    fn components(&self) -> Vec<f64>;
    fn get_item(&self, index: usize) -> PyResult<f64>;
    fn set_item(&mut self, index: usize, value: f64) -> PyResult<()>;
    fn add(self, other: Self) -> Self;
    fn sub(self, other: Self) -> Self;
    fn mul(self, other: Self) -> Self;
    fn scale(self, factor: f64) -> Self;
    fn dot(self, other: Self) -> f64;
    fn repr(&self) -> String;

    fn length(self) -> f64 {
        self.dot(self).sqrt()
    }

    fn distance(self, other: Self) -> f64 {
        self.sub(other).length()
    }

    fn normalized(self) -> Self {
        let length = self.length();
        if length == 0.0 {
            Self::zero()
        } else {
            self.scale(1.0 / length)
        }
    }

    fn hash_value(&self) -> u64 {
        let mut hasher = DefaultHasher::new();
        for value in self.components() {
            value.to_bits().hash(&mut hasher);
        }
        hasher.finish()
    }
}

#[pyclass]
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Vector2D {
    #[pyo3(get, set)]
    pub x: f64,
    #[pyo3(get, set)]
    pub y: f64,
}

impl Vector2D {
    pub(crate) fn zero() -> Self {
        <Self as VectorOps>::zero()
    }

    pub(crate) fn from_components(values: &[f64]) -> PyResult<Self> {
        <Self as VectorOps>::from_components(values)
    }

    fn from_xy(x: f64, y: f64) -> Self {
        Self { x, y }
    }

    fn to_3d(self) -> Vector3D {
        Vector3D { x: self.x, y: self.y, z: 0.0 }
    }
}

impl VectorOps for Vector2D {
    const DIMENSION: usize = 2;

    fn zero() -> Self {
        Self { x: 0.0, y: 0.0 }
    }

    fn from_components(values: &[f64]) -> PyResult<Self> {
        if values.len() != Self::DIMENSION {
            return Err(PyValueError::new_err("expected 2 values"));
        }
        Ok(Self::from_xy(values[0], values[1]))
    }

    fn components(&self) -> Vec<f64> {
        vec![self.x, self.y]
    }

    fn get_item(&self, index: usize) -> PyResult<f64> {
        match index {
            0 => Ok(self.x),
            1 => Ok(self.y),
            _ => Err(PyValueError::new_err("index out of range")),
        }
    }

    fn set_item(&mut self, index: usize, value: f64) -> PyResult<()> {
        match index {
            0 => self.x = value,
            1 => self.y = value,
            _ => return Err(PyValueError::new_err("index out of range")),
        }
        Ok(())
    }

    fn add(self, other: Self) -> Self {
        Self { x: self.x + other.x, y: self.y + other.y }
    }

    fn sub(self, other: Self) -> Self {
        Self { x: self.x - other.x, y: self.y - other.y }
    }

    fn mul(self, other: Self) -> Self {
        Self { x: self.x * other.x, y: self.y * other.y }
    }

    fn scale(self, factor: f64) -> Self {
        Self { x: self.x * factor, y: self.y * factor }
    }

    fn dot(self, other: Self) -> f64 {
        self.x * other.x + self.y * other.y
    }

    fn repr(&self) -> String {
        format!("Vector2D([{:.12}, {:.12}])", self.x, self.y)
    }
}

#[pymethods]
impl Vector2D {
    #[new]
    #[pyo3(signature = (values = None))]
    fn new(values: Option<Vec<f64>>) -> PyResult<Self> {
        match values {
            Some(values) => Self::from_components(&values),
            None => Ok(Self::zero()),
        }
    }

    fn __len__(&self) -> usize {
        Self::DIMENSION
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let list = PyList::new(py, self.components())?;
        Ok(list.into_any().call_method0("__iter__")?.unbind())
    }

    fn __getitem__(&self, index: isize) -> PyResult<f64> {
        if index < 0 || index as usize >= Self::DIMENSION {
            return Err(PyValueError::new_err("index out of range"));
        }
        self.get_item(index as usize)
    }

    fn __setitem__(&mut self, index: usize, value: f64) -> PyResult<()> {
        self.set_item(index, value)
    }

    fn __copy__(&self) -> Self {
        *self
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self {
        *self
    }

    fn __json__(&self) -> Vec<f64> {
        self.components()
    }

    fn __repr__(&self) -> String {
        self.repr()
    }

    fn __str__(&self) -> String {
        self.repr()
    }

    fn __hash__(&self) -> u64 {
        self.hash_value()
    }

    fn __eq__(&self, other: &Vector2D) -> bool {
        self == other
    }

    fn __lt__(&self, other: &Vector2D) -> bool {
        self.length() < other.length()
    }

    fn __le__(&self, other: &Vector2D) -> bool {
        self.length() <= other.length()
    }

    fn __gt__(&self, other: &Vector2D) -> bool {
        self.length() > other.length()
    }

    fn __ge__(&self, other: &Vector2D) -> bool {
        self.length() >= other.length()
    }

    fn __add__(&self, other: &Vector2D) -> Self {
        self.add(*other)
    }

    fn __sub__(&self, other: &Vector2D) -> Self {
        self.sub(*other)
    }

    fn __mul__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(vector) = extract_vector2d(other) {
            return Py::new(py, self.mul(vector)).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(scalar) = other.extract::<f64>() {
            return Py::new(py, self.scale(scalar)).map(|value| value.into_bound(py).into_any().unbind());
        }
        Err(PyTypeError::new_err("expected Vector2D or float"))
    }

    fn __truediv__(&self, factor: f64) -> Self {
        self.scale(1.0 / factor)
    }

    fn dot(&self, other: &Vector2D) -> f64 {
        VectorOps::dot(*self, *other)
    }

    fn length(&self) -> f64 {
        VectorOps::length(*self)
    }

    pub(crate) fn distance(&self, other: &Vector2D) -> f64 {
        VectorOps::distance(*self, *other)
    }

    pub(crate) fn normalized(&self) -> Self {
        VectorOps::normalized(*self)
    }

    fn copy(&self) -> Self {
        *self
    }

    fn cross(&self, other: &Vector2D) -> f64 {
        self.x * other.y - self.y * other.x
    }

    fn angle(&self) -> f64 {
        self.y.atan2(self.x)
    }
}

#[pyclass]
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Vector3D {
    #[pyo3(get, set)]
    pub x: f64,
    #[pyo3(get, set)]
    pub y: f64,
    #[pyo3(get, set)]
    pub z: f64,
}

impl Vector3D {
    pub(crate) fn zero() -> Self {
        <Self as VectorOps>::zero()
    }

    pub(crate) fn from_components(values: &[f64]) -> PyResult<Self> {
        <Self as VectorOps>::from_components(values)
    }

    fn from_xyz(x: f64, y: f64, z: f64) -> Self {
        Self { x, y, z }
    }

    fn to_2d(self) -> Vector2D {
        Vector2D { x: self.x, y: self.y }
    }
}

impl VectorOps for Vector3D {
    const DIMENSION: usize = 3;

    fn zero() -> Self {
        Self { x: 0.0, y: 0.0, z: 0.0 }
    }

    fn from_components(values: &[f64]) -> PyResult<Self> {
        if values.len() != Self::DIMENSION {
            return Err(PyValueError::new_err("expected 3 values"));
        }
        Ok(Self::from_xyz(values[0], values[1], values[2]))
    }

    fn components(&self) -> Vec<f64> {
        vec![self.x, self.y, self.z]
    }

    fn get_item(&self, index: usize) -> PyResult<f64> {
        match index {
            0 => Ok(self.x),
            1 => Ok(self.y),
            2 => Ok(self.z),
            _ => Err(PyValueError::new_err("index out of range")),
        }
    }

    fn set_item(&mut self, index: usize, value: f64) -> PyResult<()> {
        match index {
            0 => self.x = value,
            1 => self.y = value,
            2 => self.z = value,
            _ => return Err(PyValueError::new_err("index out of range")),
        }
        Ok(())
    }

    fn add(self, other: Self) -> Self {
        Self { x: self.x + other.x, y: self.y + other.y, z: self.z + other.z }
    }

    fn sub(self, other: Self) -> Self {
        Self { x: self.x - other.x, y: self.y - other.y, z: self.z - other.z }
    }

    fn mul(self, other: Self) -> Self {
        Self { x: self.x * other.x, y: self.y * other.y, z: self.z * other.z }
    }

    fn scale(self, factor: f64) -> Self {
        Self { x: self.x * factor, y: self.y * factor, z: self.z * factor }
    }

    fn dot(self, other: Self) -> f64 {
        self.x * other.x + self.y * other.y + self.z * other.z
    }

    fn repr(&self) -> String {
        format!("Vector3D([{:.12}, {:.12}, {:.12}])", self.x, self.y, self.z)
    }
}

#[pymethods]
impl Vector3D {
    #[new]
    #[pyo3(signature = (values = None))]
    fn new(values: Option<Vec<f64>>) -> PyResult<Self> {
        match values {
            Some(values) => Self::from_components(&values),
            None => Ok(Self::zero()),
        }
    }

    fn __len__(&self) -> usize {
        Self::DIMENSION
    }

    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let list = PyList::new(py, self.components())?;
        Ok(list.into_any().call_method0("__iter__")?.unbind())
    }

    fn __getitem__(&self, index: isize) -> PyResult<f64> {
        if index < 0 || index as usize >= Self::DIMENSION {
            return Err(PyValueError::new_err("index out of range"));
        }
        self.get_item(index as usize)
    }

    fn __setitem__(&mut self, index: usize, value: f64) -> PyResult<()> {
        self.set_item(index, value)
    }

    fn __copy__(&self) -> Self {
        *self
    }

    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self {
        *self
    }

    fn __json__(&self) -> Vec<f64> {
        self.components()
    }

    fn __repr__(&self) -> String {
        self.repr()
    }

    fn __str__(&self) -> String {
        self.repr()
    }

    fn __hash__(&self) -> u64 {
        self.hash_value()
    }

    fn __eq__(&self, other: &Vector3D) -> bool {
        self == other
    }

    fn __lt__(&self, other: &Vector3D) -> bool {
        self.length() < other.length()
    }

    fn __le__(&self, other: &Vector3D) -> bool {
        self.length() <= other.length()
    }

    fn __gt__(&self, other: &Vector3D) -> bool {
        self.length() > other.length()
    }

    fn __ge__(&self, other: &Vector3D) -> bool {
        self.length() >= other.length()
    }

    fn __add__(&self, other: &Vector3D) -> Self {
        self.add(*other)
    }

    fn __sub__(&self, other: &Vector3D) -> Self {
        self.sub(*other)
    }

    fn __mul__(&self, other: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(vector) = extract_vector3d(other) {
            return Py::new(py, self.mul(vector)).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(scalar) = other.extract::<f64>() {
            return Py::new(py, self.scale(scalar)).map(|value| value.into_bound(py).into_any().unbind());
        }
        Err(PyTypeError::new_err("expected Vector3D or float"))
    }

    fn __truediv__(&self, factor: f64) -> Self {
        self.scale(1.0 / factor)
    }

    fn dot(&self, other: &Vector3D) -> f64 {
        VectorOps::dot(*self, *other)
    }

    fn length(&self) -> f64 {
        VectorOps::length(*self)
    }

    pub(crate) fn distance(&self, other: &Vector3D) -> f64 {
        VectorOps::distance(*self, *other)
    }

    pub(crate) fn normalized(&self) -> Self {
        VectorOps::normalized(*self)
    }

    fn copy(&self) -> Self {
        *self
    }

    pub(crate) fn cross(&self, other: &Vector3D) -> Self {
        Self {
            x: self.y * other.z - self.z * other.y,
            y: self.z * other.x - self.x * other.z,
            z: self.x * other.y - self.y * other.x,
        }
    }
}

#[pyclass]
#[derive(Clone, Copy, Debug)]
pub struct CutResult {
    #[pyo3(get)]
    pub success: bool,
    #[pyo3(get)]
    pub ik_1: f64,
    #[pyo3(get)]
    pub ik_2: f64,
    #[pyo3(get)]
    pub point: Vector2D,
}

fn line_intersection_2d(a1: Vector2D, a2: Vector2D, b1: Vector2D, b2: Vector2D) -> Option<(f64, f64, Vector2D)> {
    let da = a2.sub(a1);
    let db = b2.sub(b1);

    let min_segment_length = 1e-8;
    let da_len_sq = da.dot(da);
    let db_len_sq = db.dot(db);
    if da_len_sq < min_segment_length * min_segment_length || db_len_sq < min_segment_length * min_segment_length {
        return None;
    }

    let det = da.x * db.y - da.y * db.x;
    let parallel_threshold = 1e-10;
    let da_len = da_len_sq.sqrt();
    let db_len = db_len_sq.sqrt();
    if da_len == 0.0 || db_len == 0.0 {
        return None;
    }
    let cross_normalized = det / (da_len * db_len);
    if cross_normalized.abs() < parallel_threshold {
        return None;
    }

    let diff = b1.sub(a1);
    let t = (diff.x * db.y - diff.y * db.x) / det;
    let u = (diff.x * da.y - diff.y * da.x) / det;
    Some((t, u, a1.add(da.scale(t))))
}

#[pyfunction]
fn cut_2d(
    l1_p1: &Bound<'_, PyAny>,
    l1_p2: &Bound<'_, PyAny>,
    l2_p1: &Bound<'_, PyAny>,
    l2_p2: &Bound<'_, PyAny>,
) -> PyResult<CutResult> {
    let l1_p1 = extract_vector2d(l1_p1)?;
    let l1_p2 = extract_vector2d(l1_p2)?;
    let l2_p1 = extract_vector2d(l2_p1)?;
    let l2_p2 = extract_vector2d(l2_p2)?;

    Ok(if let Some((ik_1, ik_2, point)) = line_intersection_2d(l1_p1, l1_p2, l2_p1, l2_p2) {
        CutResult { success: true, ik_1, ik_2, point }
    } else {
        CutResult { success: false, ik_1: 0.0, ik_2: 0.0, point: Vector2D::zero() }
    })
}

#[pyfunction(name = "cut")]
fn cut(
    l1_p1: &Bound<'_, PyAny>,
    l1_p2: &Bound<'_, PyAny>,
    l2_p1: &Bound<'_, PyAny>,
    l2_p2: &Bound<'_, PyAny>,
) -> PyResult<CutResult> {
    cut_2d(l1_p1, l1_p2, l2_p1, l2_p2)
}

#[pyclass]
#[derive(Clone, Copy, Debug, Default)]
pub struct Rotation2D {
    angle: f64,
}

#[pymethods]
impl Rotation2D {
    #[new]
    fn new(angle: f64) -> Self {
        Self { angle }
    }

    fn apply(&self, vector: &Bound<'_, PyAny>) -> PyResult<Vector2D> {
        let vector = extract_vector2d(vector)?;
        let (sin_angle, cos_angle) = self.angle.sin_cos();
        Ok(Vector2D {
            x: vector.x * cos_angle - vector.y * sin_angle,
            y: vector.x * sin_angle + vector.y * cos_angle,
        })
    }
}

#[pyclass]
#[derive(Clone, Copy, Debug)]
pub struct Transformation {
    #[pyo3(get)]
    pub matrix: [[f64; 4]; 4],
}

impl Transformation {
    fn as_matrix4(&self) -> Matrix4<f64> {
        Matrix4::from_row_slice(&[
            self.matrix[0][0], self.matrix[0][1], self.matrix[0][2], self.matrix[0][3],
            self.matrix[1][0], self.matrix[1][1], self.matrix[1][2], self.matrix[1][3],
            self.matrix[2][0], self.matrix[2][1], self.matrix[2][2], self.matrix[2][3],
            self.matrix[3][0], self.matrix[3][1], self.matrix[3][2], self.matrix[3][3],
        ])
    }

    fn from_matrix4(matrix: Matrix4<f64>) -> Self {
        let mut values = [[0.0; 4]; 4];
        for row in 0..4 {
            for col in 0..4 {
                values[row][col] = matrix[(row, col)];
            }
        }
        Self { matrix: values }
    }
}

#[pymethods]
impl Transformation {
    #[new]
    pub(crate) fn new() -> Self {
        Self {
            matrix: [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
        }
    }

    #[staticmethod]
    fn rotation(angle: f64, axis: &Bound<'_, PyAny>) -> PyResult<Self> {
        let axis = extract_vector3d(axis)?.normalized();
        let (sin_angle, cos_angle) = angle.sin_cos();
        let one_minus = 1.0 - cos_angle;
        let matrix = Matrix4::new(
            cos_angle + axis.x * axis.x * one_minus,
            axis.x * axis.y * one_minus - axis.z * sin_angle,
            axis.x * axis.z * one_minus + axis.y * sin_angle,
            0.0,
            axis.y * axis.x * one_minus + axis.z * sin_angle,
            cos_angle + axis.y * axis.y * one_minus,
            axis.y * axis.z * one_minus - axis.x * sin_angle,
            0.0,
            axis.z * axis.x * one_minus - axis.y * sin_angle,
            axis.z * axis.y * one_minus + axis.x * sin_angle,
            cos_angle + axis.z * axis.z * one_minus,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        );
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn translation(vector: &Bound<'_, PyAny>) -> PyResult<Self> {
        let mut matrix = Self::new().as_matrix4();
        if let Ok(vector) = extract_vector3d(vector) {
            matrix[(0, 3)] = vector.x;
            matrix[(1, 3)] = vector.y;
            matrix[(2, 3)] = vector.z;
            return Ok(Self::from_matrix4(matrix));
        }
        let vector = extract_vector2d(vector)?;
        matrix[(0, 3)] = vector.x;
        matrix[(1, 3)] = vector.y;
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn reflection(normal: &Bound<'_, PyAny>) -> PyResult<Self> {
        let normal = extract_vector3d(normal)?.normalized();
        let nx = normal.x;
        let ny = normal.y;
        let nz = normal.z;
        let matrix = Matrix4::new(
            1.0 - 2.0 * nx * nx,
            -2.0 * nx * ny,
            -2.0 * nx * nz,
            0.0,
            -2.0 * ny * nx,
            1.0 - 2.0 * ny * ny,
            -2.0 * ny * nz,
            0.0,
            -2.0 * nz * nx,
            -2.0 * nz * ny,
            1.0 - 2.0 * nz * nz,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        );
        Ok(Self::from_matrix4(matrix))
    }

    #[staticmethod]
    fn scale(scale: f64) -> Self {
        let mut matrix = Self::new().as_matrix4();
        matrix[(0, 0)] = scale;
        matrix[(1, 1)] = scale;
        matrix[(2, 2)] = scale;
        Self::from_matrix4(matrix)
    }

    fn chain(&self, other: &Transformation) -> Self {
        // Euklid composes transforms in left-to-right application order:
        // (A * B).apply(v) == B.apply(A.apply(v)).
        // With column-vector math this is represented as M = B * A.
        Self::from_matrix4(other.as_matrix4() * self.as_matrix4())
    }

    fn __mul__(&self, other: &Transformation) -> Self {
        self.chain(other)
    }

    fn copy(&self) -> Self {
        *self
    }

    fn apply(&self, value: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(vector) = extract_vector3d(value) {
            return Py::new(py, self.apply_vector3(vector)).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(vector) = extract_vector2d(value) {
            return Py::new(py, self.apply_vector3(vector.to_3d())).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(polyline) = value.extract::<PolyLine2D>() {
            return Py::new(py, self.apply_polyline2(polyline)).map(|value| value.into_bound(py).into_any().unbind());
        }
        if let Ok(polyline) = value.extract::<PolyLine3D>() {
            return Py::new(py, self.apply_polyline3(polyline)).map(|value| value.into_bound(py).into_any().unbind());
        }

        // Compatibility path for polyline-like objects from other modules/versions.
        // First try an explicit `.nodes` attribute, then generic iterable extraction.
        if let Ok(nodes_obj) = value.getattr("nodes") {
            if let Ok(nodes_any) = nodes_obj.extract::<Vec<Py<PyAny>>>() {
                let mut transformed = Vec::with_capacity(nodes_any.len());
                for node in nodes_any {
                    let node = node.bind(py).as_any();
                    if let Ok(vector) = extract_vector3d(node) {
                        transformed.push(self.apply_vector3(vector));
                    } else {
                        transformed.push(self.apply_vector2(extract_vector2d(node)?).to_3d());
                    }
                }
                return Py::new(py, PolyLine3D { nodes: transformed })
                    .map(|value| value.into_bound(py).into_any().unbind());
            }
        }

        if let Ok(points) = value.extract::<Vec<Py<PyAny>>>() {
            let mut transformed = Vec::with_capacity(points.len());
            for point in points {
                let point = point.bind(py).as_any();
                if let Ok(vector) = extract_vector3d(point) {
                    transformed.push(self.apply_vector3(vector));
                } else {
                    transformed.push(self.apply_vector2(extract_vector2d(point)?).to_3d());
                }
            }
            return Py::new(py, PolyLine3D { nodes: transformed })
                .map(|value| value.into_bound(py).into_any().unbind());
        }

        Err(PyTypeError::new_err("unsupported value for Transformation.apply"))
    }

    pub(crate) fn apply_vector3(&self, vector: Vector3D) -> Vector3D {
        let matrix = self.as_matrix4();
        let result = matrix * Vector4::new(vector.x, vector.y, vector.z, 1.0);
        Vector3D { x: result.x, y: result.y, z: result.z }
    }

    fn apply_vector2(&self, vector: Vector2D) -> Vector2D {
        let matrix = self.as_matrix4();
        let result = matrix * Vector4::new(vector.x, vector.y, 0.0, 1.0);
        Vector2D { x: result.x, y: result.y }
    }

    fn apply_polyline2(&self, polyline: PolyLine2D) -> PolyLine3D {
        PolyLine3D {
            nodes: polyline.nodes.into_iter().map(|node| self.apply_vector3(node.to_3d())).collect(),
        }
    }

    fn apply_polyline3(&self, polyline: PolyLine3D) -> PolyLine3D {
        PolyLine3D {
            nodes: polyline.nodes.into_iter().map(|node| self.apply_vector3(node)).collect(),
        }
    }
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PolyLine2D {
    #[pyo3(get)]
    pub nodes: Vec<Vector2D>,
}

#[pyclass]
#[derive(Clone, Debug)]
pub struct PolyLine3D {
    #[pyo3(get)]
    pub nodes: Vec<Vector3D>,
}

pub(crate) fn polyline_resample<V: VectorOps>(nodes: &[V], num_points: usize) -> Vec<V> {
    if nodes.is_empty() || num_points == 0 {
        return Vec::new();
    }
    if nodes.len() == 1 || num_points == 1 {
        return vec![nodes[0]];
    }

    let lengths: Vec<f64> = nodes.windows(2).map(|pair| pair[0].distance(pair[1])).collect();
    let total: f64 = lengths.iter().sum();
    if total == 0.0 {
        return vec![nodes[0]; num_points];
    }

    let step = total / (num_points - 1) as f64;
    let mut result = Vec::with_capacity(num_points);
    result.push(nodes[0]);

    let mut target_distance = step;
    let mut segment_index = 0usize;
    let mut accumulated = 0.0;
    while result.len() + 1 < num_points {
        while segment_index < lengths.len() && accumulated + lengths[segment_index] < target_distance {
            accumulated += lengths[segment_index];
            segment_index += 1;
        }
        if segment_index >= lengths.len() {
            break;
        }
        let segment_length = lengths[segment_index];
        let fraction = if segment_length == 0.0 { 0.0 } else { (target_distance - accumulated) / segment_length };
        let p1 = nodes[segment_index];
        let p2 = nodes[segment_index + 1];
        result.push(p1.scale(1.0 - fraction).add(p2.scale(fraction)));
        target_distance += step;
    }

    while result.len() + 1 < num_points {
        result.push(*nodes.last().unwrap());
    }
    result.push(*nodes.last().unwrap());
    result
}

pub(crate) fn polyline_get<V: VectorOps>(nodes: &[V], ik: f64) -> V {
    if nodes.is_empty() {
        return V::zero();
    }
    if nodes.len() == 1 {
        return nodes[0];
    }

    let mut i = (ik as isize).max(0) as usize;
    if (ik - i as f64).abs() < 1e-10 && ik >= 0.0 && (i as f64) < nodes.len() as f64 {
        return nodes[i];
    }

    let diff = if i >= nodes.len() - 1 {
        i = nodes.len() - 1;
        nodes[i].sub(nodes[i - 1])
    } else {
        nodes[i + 1].sub(nodes[i])
    };

    let k = ik - i as f64;
    nodes[i].add(diff.scale(k))
}

fn polyline_length<V: VectorOps>(nodes: &[V]) -> f64 {
    nodes.windows(2).map(|pair| pair[0].distance(pair[1])).sum()
}

fn polyline_segments<V: VectorOps>(nodes: &[V]) -> Vec<V> {
    nodes.windows(2).map(|pair| pair[1].sub(pair[0])).collect()
}

fn polyline_tangents<V: VectorOps>(nodes: &[V]) -> Vec<V> {
    polyline_segments(nodes).into_iter().map(VectorOps::normalized).collect()
}

fn polyline_scale_nodes<V: VectorOps>(nodes: &[V], factors: &[f64]) -> Vec<V> {
    nodes.iter().zip(factors.iter().copied()).map(|(node, factor)| node.scale(factor)).collect()
}

fn polyline2d_fix_errors(nodes: &[Vector2D]) -> Vec<Vector2D> {
    const TOLERANCE: f64 = 1e-5;
    const SMALL_D: f64 = 1e-10;

    if nodes.len() <= 4 {
        return nodes.to_vec();
    }

    for index in 0..nodes.len().saturating_sub(3) {
        let new_list_start = index + 2;
        let line2_nodes = &nodes[new_list_start..];

        let cuts = polyline2d_cut_line(line2_nodes, nodes[index], nodes[index + 1]);
        for (ik_1, ik_2) in cuts.into_iter().rev() {
            let line2_max = line2_nodes.len() as f64 - 1.0 - SMALL_D;
            if (0.0..line2_max).contains(&ik_1) && (0.0..1.0).contains(&ik_2) {
                let mut new_nodes = Vec::with_capacity(nodes.len());
                new_nodes.extend_from_slice(&nodes[..=index]);
                new_nodes.push(polyline_get(line2_nodes, ik_1));

                let mut start_2 = ik_1 as usize + 1;
                if (ik_1 - start_2 as f64).abs() < TOLERANCE {
                    start_2 += 1;
                }

                if start_2 < line2_nodes.len() {
                    new_nodes.extend_from_slice(&line2_nodes[start_2..]);
                }

                return polyline2d_fix_errors(&new_nodes);
            }
        }
    }

    let mut cleaned = Vec::with_capacity(nodes.len());
    cleaned.push(nodes[0]);

    for pair in nodes.windows(2) {
        if pair[0].distance(pair[1]) > TOLERANCE {
            cleaned.push(pair[1]);
        }
    }

    cleaned
}

fn polyline2d_cut_line(nodes: &[Vector2D], p1: Vector2D, p2: Vector2D) -> Vec<(f64, f64)> {
    let mut intersections = Vec::new();
    let tolerance = 1e-5;
    if nodes.len() < 2 {
        return intersections;
    }

    let mut last_ik_1 = 0.0;
    let mut last_ik_2 = 0.0;
    let mut last_success = false;
    let mut last_cut = line_intersection_2d(nodes[0], nodes[1], p1, p2);

    if let Some((ik_1, ik_2, _)) = last_cut {
        last_success = true;
        last_ik_1 = ik_1;
        last_ik_2 = ik_2;
        if ik_1 <= tolerance {
            intersections.push((ik_1, ik_2));
        }
    }

    for index in 0..nodes.len().saturating_sub(1) {
        let cut = line_intersection_2d(nodes[index], nodes[index + 1], p1, p2);
        if let Some((ik_1, ik_2, _)) = cut {
            if tolerance < ik_1 && ik_1 <= 1.0 - tolerance {
                intersections.push((index as f64 + ik_1, ik_2));
            } else if -tolerance < ik_1 && ik_1 <= tolerance && last_success && 1.0 - tolerance < last_ik_1 && last_ik_1 <= 1.0 + tolerance {
                intersections.push((index as f64, last_ik_2));
            }
            last_success = true;
            last_ik_1 = ik_1;
            last_ik_2 = ik_2;
            last_cut = Some((ik_1, ik_2, Vector2D::zero()));
        } else {
            last_success = false;
            last_cut = None;
        }
    }

    if let Some((ik_1, ik_2, _)) = last_cut {
        if ik_1 > 1.0 - tolerance {
            intersections.push((ik_1 + nodes.len() as f64 - 2.0, ik_2));
        }
    }

    intersections
}

fn polyline_get_positions(node_count: usize, ik_start: f64, ik_end: f64) -> Vec<f64> {
    if node_count < 2 {
        return vec![ik_start, ik_end];
    }

    let mut result = Vec::new();
    let mut direction = 1_i32;
    let mut forward = true;
    if ik_end < ik_start {
        direction = -1;
        forward = false;
    }

    result.push(ik_start);

    let mut ik = ik_start as i32;
    ik = ik.clamp(0, (node_count as i32) - 2);

    if forward {
        ik += 1;
    }

    if (ik_start - ik as f64).abs() < 1e-8 {
        ik += direction;
    }

    while (direction as f64) * (ik_end - ik as f64) > 1e-8 && 0 < ik && ik < (node_count as i32) - 1 {
        result.push(ik as f64);
        ik += direction;
    }

    result.push(ik_end);
    result
}

fn polyline_walk<V: VectorOps>(nodes: &[V], start: f64, amount: f64) -> f64 {
    if nodes.len() < 2 {
        return start;
    }

    if amount.abs() < 1e-5 {
        return start;
    }

    let direction: i32 = if amount < 0.0 { -1 } else { 1 };
    let mut next_value = start as i32;
    if direction > 0 {
        next_value += 1;
    }
    if start < 0.0 {
        next_value -= 1;
    }

    if (start - next_value as f64).abs() < 1e-5 {
        next_value += direction;
    }

    let mut remaining = amount.abs();
    let mut start_cursor = start;

    let mut current_segment_length = polyline_get(nodes, next_value as f64).distance(polyline_get(nodes, start_cursor));
    remaining -= current_segment_length;

    while remaining > 0.0 {
        if next_value > nodes.len() as i32 && direction > 0 {
            break;
        }
        if next_value < 0 && direction < 0 {
            break;
        }

        start_cursor = next_value as f64;
        next_value += direction;
        current_segment_length = polyline_get(nodes, next_value as f64).distance(polyline_get(nodes, start_cursor));
        remaining -= current_segment_length;
    }

    if current_segment_length <= 1e-15 {
        return next_value as f64;
    }

    next_value as f64 + (direction as f64) * remaining * ((next_value as f64 - start_cursor).abs()) / current_segment_length
}

#[pymethods]
impl PolyLine2D {
    #[new]
    #[pyo3(signature = (nodes = None))]
    fn new(py: Python<'_>, nodes: Option<Vec<Py<PyAny>>>) -> PyResult<Self> {
        let mut parsed = Vec::new();
        if let Some(nodes) = nodes {
            for node in nodes {
                parsed.push(extract_vector2d(node.bind(py).as_any())?);
            }
        }
        Ok(Self { nodes: parsed })
    }

    fn __len__(&self) -> usize { self.nodes.len() }
    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let list = PyList::new(py, self.nodes.clone())?;
        Ok(list.into_any().call_method0("__iter__")?.unbind())
    }
    fn __copy__(&self) -> Self { self.clone() }
    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self { self.clone() }
    fn copy(&self) -> Self { self.clone() }

    fn __repr__(&self) -> String {
        let mut result = String::from("PolyLine2D[\n");
        for node in &self.nodes {
            result.push_str("  ");
            result.push_str(&node.repr());
            result.push_str(",\n");
        }
        if !self.nodes.is_empty() {
            result.truncate(result.len().saturating_sub(2));
            result.push('\n');
        }
        result.push(']');
        result
    }

    fn __json__(&self) -> Vec<Vec<f64>> { self.nodes.iter().map(VectorOps::components).collect() }
    fn tolist(&self) -> Vec<Vec<f64>> { self.nodes.iter().map(VectorOps::components).collect() }

    #[pyo3(signature = (value, end = None))]
    fn get(&self, value: f64, end: Option<f64>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Some(end) = end {
            let mut nodes = Vec::new();
            for position in polyline_get_positions(self.nodes.len(), value, end) {
                nodes.push(polyline_get(&self.nodes, position));
            }
            return Py::new(py, Self { nodes }).map(|value| value.into_bound(py).into_any().unbind());
        }
        Py::new(py, polyline_get(&self.nodes, value)).map(|value| value.into_bound(py).into_any().unbind())
    }

    fn get_positions(&self, start: f64, end: f64) -> Vec<f64> {
        polyline_get_positions(self.nodes.len(), start, end)
    }

    fn get_segments(&self) -> Vec<Vector2D> { polyline_segments(&self.nodes) }
    fn get_segment_lengthes(&self) -> Vec<f64> { self.nodes.windows(2).map(|pair| pair[0].distance(pair[1])).collect() }
    fn get_tangents(&self) -> Vec<Vector2D> { polyline_tangents(&self.nodes) }
    fn get_length(&self) -> f64 { polyline_length(&self.nodes) }

    fn walk(&self, start: f64, amount: f64) -> f64 {
        polyline_walk(&self.nodes, start, amount)
    }

    fn resample(&self, num_points: usize) -> Self { Self { nodes: polyline_resample(&self.nodes, num_points) } }

    fn scale(&self, factor: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(scalar) = factor.extract::<f64>() {
            return Py::new(py, Self { nodes: self.nodes.iter().map(|node| node.scale(scalar)).collect() }).map(|value| value.into_bound(py).into_any().unbind());
        }
        let vector = extract_vector2d(factor)?;
        Py::new(py, Self { nodes: self.nodes.iter().map(|node| node.mul(vector)).collect() }).map(|value| value.into_bound(py).into_any().unbind())
    }

    #[pyo3(name = "move")]
    fn r#move(&self, offset: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let offset = extract_vector2d(offset)?;
        Py::new(py, Self { nodes: self.nodes.iter().copied().map(|node| node.add(offset)).collect() }).map(|value| value.into_bound(py).into_any().unbind())
    }

    fn add(&self, other: &PolyLine2D) -> Self {
        let len = self.nodes.len().min(other.nodes.len());
        Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.add(right)).collect() }
    }

    fn sub(&self, other: &PolyLine2D) -> Self {
        let len = self.nodes.len().min(other.nodes.len());
        Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.sub(right)).collect() }
    }

    fn scale_nodes(&self, factors: Vec<f64>) -> Self { Self { nodes: polyline_scale_nodes(&self.nodes, &factors) } }
    fn reverse(&self) -> Self { let mut nodes = self.nodes.clone(); nodes.reverse(); Self { nodes } }
    fn mix(&self, other: &PolyLine2D, factor: f64) -> Self {
        let len = self.nodes.len().min(other.nodes.len());
        let factor = factor.clamp(0.0, 1.0);
        Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.scale(1.0 - factor).add(right.scale(factor))).collect() }
    }
    fn __add__(&self, other: &PolyLine2D) -> Self { self.add(other) }
    fn __sub__(&self, other: &PolyLine2D) -> Self { self.sub(other) }
    fn __mul__(&self, factor: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> { self.scale(factor, py) }

    fn segment_normals(&self) -> Self {
        let nodes = self.nodes.windows(2).map(|pair| {
            let segment = pair[1].sub(pair[0]).normalized();
            Vector2D { x: segment.y, y: -segment.x }
        }).collect();
        Self { nodes }
    }

    fn normvectors(&self) -> Self {
        let segments = self.get_segments();
        if segments.is_empty() {
            return Self { nodes: Vec::new() };
        }

        let segment_normals = self.segment_normals().nodes;
        let mut norms = Vec::with_capacity(self.nodes.len());
        norms.push(segment_normals[0]);

        for index in 0..segment_normals.len().saturating_sub(1) {
            let normal = segment_normals[index].add(segment_normals[index + 1]);
            if normal.length() > 1e-12 {
                norms.push(normal.normalized());
            } else {
                let segment_index = index.saturating_sub(1);
                norms.push(segments[segment_index].normalized());
            }
        }

        norms.push(*segment_normals.last().unwrap());
        Self { nodes: norms }
    }

    #[pyo3(signature = (amount, simple = false))]
    fn offset(&self, amount: f64, simple: bool) -> Self {
        const EPSILON: f64 = 1e-10;
        const MITER_LIMIT: f64 = 10.0;

        let nodes = polyline2d_fix_errors(&self.nodes);

        if nodes.len() < 2 {
            return self.clone();
        }

        let clean_line = Self { nodes };

        if simple {
            let normals = clean_line.normvectors().nodes;
            let nodes = clean_line
                .nodes
                .iter()
                .copied()
                .zip(normals)
                .map(|(point, normal)| point.add(normal.scale(amount)))
                .collect();
            return Self { nodes };
        }

        let segments = clean_line.get_segments();
        let segments_normalized: Vec<Vector2D> = segments.iter().copied().map(|segment| segment.normalized()).collect();
        let segment_normals = clean_line.segment_normals().nodes;

        let mut offset_segments: Vec<(Vector2D, Vector2D)> = Vec::with_capacity(clean_line.nodes.len().saturating_sub(1));
        for index in 0..clean_line.nodes.len() - 1 {
            let normal = segment_normals[index];
            offset_segments.push((
                clean_line.nodes[index].add(normal.scale(amount)),
                clean_line.nodes[index + 1].add(normal.scale(amount)),
            ));
        }

        let mut result = Vec::with_capacity(clean_line.nodes.len() + clean_line.nodes.len().saturating_sub(2));
        result.push(clean_line.nodes[0].add(segment_normals[0].scale(amount)));

        for index in 0..clean_line.nodes.len() - 2 {
            let segment_1 = segments_normalized[index];
            let segment_2 = segments_normalized[index + 1];
            let cos_angle = segment_1.dot(segment_2);

            if cos_angle > 0.999 || segment_1.length() < EPSILON || segment_2.length() < EPSILON {
                let average = offset_segments[index].1.add(offset_segments[index + 1].0).scale(0.5);
                result.push(average);
                continue;
            }

            let intersection = line_intersection_2d(
                offset_segments[index].0,
                offset_segments[index].1,
                offset_segments[index + 1].0,
                offset_segments[index + 1].1,
            );

            if let Some((ik_1, ik_2, point)) = intersection {
                let reasonable_intersection = (ik_1 > 0.5 && ik_1 < 1.5) && (ik_2 > -0.5 && ik_2 < 0.5);

                if reasonable_intersection {
                    let original_vertex = clean_line.nodes[index + 1];
                    let miter_distance = point.sub(original_vertex).length();
                    let max_miter_distance = amount.abs() * MITER_LIMIT;

                    if miter_distance <= max_miter_distance {
                        result.push(point);
                    } else {
                        result.push(offset_segments[index].1);
                        result.push(offset_segments[index + 1].0);
                    }
                } else {
                    result.push(offset_segments[index].1);
                    result.push(offset_segments[index + 1].0);
                }
            } else {
                result.push(offset_segments[index].1);
                result.push(offset_segments[index + 1].0);
            }
        }

        result.push(clean_line.nodes[clean_line.nodes.len() - 1].add(segment_normals[segment_normals.len() - 1].scale(amount)));
        Self { nodes: result }
    }

    #[pyo3(signature = (other, arg2 = None, nearest_ik = None))]
    fn cut(&self, other: &Bound<'_, PyAny>, arg2: Option<&Bound<'_, PyAny>>, nearest_ik: Option<f64>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let mut nearest = nearest_ik;
        if nearest.is_none() {
            if let Some(arg2) = arg2 {
                if let Ok(value) = arg2.extract::<f64>() {
                    nearest = Some(value);
                }
            }
        }

        let finalize_result = |mut intersections: Vec<(f64, f64)>| -> PyResult<Py<PyAny>> {
            if let Some(nearest_ik) = nearest {
                intersections.sort_by(|left, right| (left.0 - nearest_ik).abs().partial_cmp(&(right.0 - nearest_ik).abs()).unwrap_or(std::cmp::Ordering::Equal));
                if let Some(cut) = intersections.first() {
                    return Ok((cut.0, cut.1).into_pyobject(py)?.into_any().unbind());
                }
                return Err(PyRuntimeError::new_err("No cut found!"));
            }

            Ok(intersections.into_pyobject(py)?.into_any().unbind())
        };

        if let Ok(vector) = extract_vector2d(other) {
            let intersections = if let Some(arg2) = arg2 {
                if let Ok(vector2) = extract_vector2d(arg2) {
                    polyline2d_cut_line(&self.nodes, vector, vector2)
                } else {
                    polyline2d_cut_line(&self.nodes, vector, vector.add(Vector2D { x: 1.0, y: 0.0 }))
                }
            } else {
                polyline2d_cut_line(&self.nodes, vector, vector.add(Vector2D { x: 1.0, y: 0.0 }))
            };

            return finalize_result(intersections);
        }

        let other = other.extract::<PolyLine2D>()?;
        let tolerance = 1e-5;
        let mut intersections = Vec::new();
        for index_b in 0..other.nodes.len().saturating_sub(1) {
            let cuts = polyline2d_cut_line(&self.nodes, other.nodes[index_b], other.nodes[index_b + 1]);
            for cut in cuts {
                if -tolerance < cut.1 && cut.1 < 1.0 + tolerance && -tolerance < cut.0 && cut.0 < self.nodes.len() as f64 - 1.0 + tolerance {
                    intersections.push((cut.0, index_b as f64 + cut.1));
                }
            }
        }
        finalize_result(intersections)
    }

    fn bool_union(&self, other: &PolyLine2D) -> Vec<PolyLine2D> { vec![self.clone(), other.clone()] }
    fn fix_errors(&self) -> Self {
        Self {
            nodes: polyline2d_fix_errors(&self.nodes),
        }
    }
    fn close(&self) -> Self {
        let mut nodes = self.nodes.clone();
        if !nodes.is_empty() && nodes.first() != nodes.last() {
            nodes.push(*nodes.first().unwrap());
        }
        Self { nodes }
    }

    fn get_area(&self) -> f64 {
        if self.nodes.len() < 3 {
            return 0.0;
        }
        let mut area = 0.0;
        for index in 0..self.nodes.len() {
            let next = (index + 1) % self.nodes.len();
            area += self.nodes[index].x * self.nodes[next].y - self.nodes[next].x * self.nodes[index].y;
        }
        0.5 * area
    }

    fn boundary(&self) -> Vec<Vector2D> { self.nodes.clone() }

    fn contains(&self, point: &Bound<'_, PyAny>) -> PyResult<bool> {
        let point = extract_vector2d(point)?;
        if self.nodes.len() < 3 {
            return Ok(false);
        }
        let mut inside = false;
        let mut previous = self.nodes.last().copied().unwrap();
        for current in &self.nodes {
            let intersects = ((current.y > point.y) != (previous.y > point.y))
                && (point.x < (previous.x - current.x) * (point.y - current.y) / (previous.y - current.y + 1e-18) + current.x);
            if intersects {
                inside = !inside;
            }
            previous = *current;
        }
        Ok(inside)
    }

    #[pyo3(signature = (p1 = None, p2 = None))]
    fn mirror(&self, p1: Option<&Bound<'_, PyAny>>, p2: Option<&Bound<'_, PyAny>>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let (a, b) = match (p1, p2) {
            (Some(a), Some(b)) => (extract_vector2d(a)?, extract_vector2d(b)?),
            _ => (Vector2D { x: 0.0, y: 0.0 }, Vector2D { x: 0.0, y: 1.0 }),
        };
        let direction = b.sub(a).normalized();
        let nodes = self.nodes.iter().copied().map(|point| {
            let ap = point.sub(a);
            let projection = direction.scale(ap.dot(direction));
            let perpendicular = ap.sub(projection);
            a.add(projection).sub(perpendicular)
        }).collect();
        Py::new(py, Self { nodes }).map(|value| value.into_bound(py).into_any().unbind())
    }

    #[pyo3(signature = (angle, p1 = None))]
    fn rotate(&self, angle: f64, p1: Option<&Bound<'_, PyAny>>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let center = match p1 {
            Some(point) => extract_vector2d(point)?,
            None => Vector2D::zero(),
        };
        let (sin_angle, cos_angle) = angle.sin_cos();
        let nodes = self.nodes.iter().copied().map(|point| {
            let point = point.sub(center);
            Vector2D {
                x: point.x * cos_angle - point.y * sin_angle + center.x,
                y: point.x * sin_angle + point.y * cos_angle + center.y,
            }
        }).collect();
        Py::new(py, Self { nodes }).map(|value| value.into_bound(py).into_any().unbind())
    }

    fn to_3d(&self) -> PolyLine3D {
        PolyLine3D { nodes: self.nodes.iter().copied().map(Vector2D::to_3d).collect() }
    }

    fn __getitem__(&self, index: usize) -> PyResult<Vector2D> {
        self.nodes.get(index).copied().ok_or_else(|| PyValueError::new_err("index out of range"))
    }
}

#[pymethods]
impl PolyLine3D {
    #[new]
    #[pyo3(signature = (nodes = None))]
    fn new(py: Python<'_>, nodes: Option<Vec<Py<PyAny>>>) -> PyResult<Self> {
        let mut parsed = Vec::new();
        if let Some(nodes) = nodes {
            for node in nodes {
                parsed.push(extract_vector3d(node.bind(py).as_any())?);
            }
        }
        Ok(Self { nodes: parsed })
    }

    fn __len__(&self) -> usize { self.nodes.len() }
    fn __iter__(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let list = PyList::new(py, self.nodes.clone())?;
        Ok(list.into_any().call_method0("__iter__")?.unbind())
    }
    fn __copy__(&self) -> Self { self.clone() }
    fn __deepcopy__(&self, _memo: &Bound<'_, PyAny>) -> Self { self.clone() }
    fn copy(&self) -> Self { self.clone() }

    fn __repr__(&self) -> String {
        let mut result = String::from("PolyLine3D[\n");
        for node in &self.nodes {
            result.push_str("  ");
            result.push_str(&node.repr());
            result.push_str(",\n");
        }
        if !self.nodes.is_empty() {
            result.truncate(result.len().saturating_sub(2));
            result.push('\n');
        }
        result.push(']');
        result
    }

    fn __json__(&self) -> Vec<Vec<f64>> { self.nodes.iter().map(VectorOps::components).collect() }
    fn tolist(&self) -> Vec<Vec<f64>> { self.nodes.iter().map(VectorOps::components).collect() }

    #[pyo3(signature = (value, end = None))]
    fn get(&self, value: f64, end: Option<f64>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Some(end) = end {
            let mut nodes = Vec::new();
            for position in polyline_get_positions(self.nodes.len(), value, end) {
                nodes.push(polyline_get(&self.nodes, position));
            }
            return Py::new(py, Self { nodes }).map(|value| value.into_bound(py).into_any().unbind());
        }
        Py::new(py, polyline_get(&self.nodes, value)).map(|value| value.into_bound(py).into_any().unbind())
    }

    fn get_length(&self) -> f64 { polyline_length(&self.nodes) }
    fn get_positions(&self, start: f64, end: f64) -> Vec<f64> {
        polyline_get_positions(self.nodes.len(), start, end)
    }
    fn get_segments(&self) -> Vec<Vector3D> { polyline_segments(&self.nodes) }
    fn get_segment_lengthes(&self) -> Vec<f64> { self.nodes.windows(2).map(|pair| pair[0].distance(pair[1])).collect() }
    fn get_tangents(&self) -> Vec<Vector3D> { polyline_tangents(&self.nodes) }
    fn walk(&self, start: f64, amount: f64) -> f64 {
        polyline_walk(&self.nodes, start, amount)
    }
    fn resample(&self, num_points: usize) -> Self { Self { nodes: polyline_resample(&self.nodes, num_points) } }
    fn reverse(&self) -> Self { let mut nodes = self.nodes.clone(); nodes.reverse(); Self { nodes } }
    fn scale(&self, factor: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        if let Ok(scalar) = factor.extract::<f64>() {
            return Py::new(py, Self { nodes: self.nodes.iter().map(|node| node.scale(scalar)).collect() }).map(|value| value.into_bound(py).into_any().unbind());
        }
        let vector = extract_vector3d(factor)?;
        Py::new(py, Self { nodes: self.nodes.iter().map(|node| node.mul(vector)).collect() }).map(|value| value.into_bound(py).into_any().unbind())
    }
    #[pyo3(name = "move")]
    fn r#move(&self, offset: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let offset = extract_vector3d(offset)?;
        Py::new(py, Self { nodes: self.nodes.iter().copied().map(|node| node.add(offset)).collect() }).map(|value| value.into_bound(py).into_any().unbind())
    }
    fn add(&self, other: &Self) -> Self { let len = self.nodes.len().min(other.nodes.len()); Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.add(right)).collect() } }
    fn sub(&self, other: &Self) -> Self { let len = self.nodes.len().min(other.nodes.len()); Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.sub(right)).collect() } }
    fn mix(&self, other: &PolyLine3D, factor: f64) -> Self {
        let len = self.nodes.len().min(other.nodes.len());
        let factor = factor.clamp(0.0, 1.0);
        Self { nodes: self.nodes[..len].iter().copied().zip(other.nodes[..len].iter().copied()).map(|(left, right)| left.scale(1.0 - factor).add(right.scale(factor))).collect() }
    }
    fn scale_nodes(&self, factors: Vec<f64>) -> Self { Self { nodes: polyline_scale_nodes(&self.nodes, &factors) } }
    fn __add__(&self, other: &Self) -> Self { self.add(other) }
    fn __sub__(&self, other: &Self) -> Self { self.sub(other) }
    fn __mul__(&self, factor: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> { self.scale(factor, py) }
    fn __getitem__(&self, index: usize) -> PyResult<Vector3D> { self.nodes.get(index).copied().ok_or_else(|| PyValueError::new_err("index out of range")) }
}

#[pyclass]
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
    fn new(py: Python<'_>, nodes: &Bound<'_, PyAny>, extrapolate: bool) -> PyResult<Self> {
        if let Ok(interpolation) = nodes.extract::<Interpolation>() {
            return Ok(Self { curve: interpolation.curve, extrapolate });
        }

        if let Ok(polyline) = nodes.extract::<PolyLine2D>() {
            return Ok(Self { curve: polyline, extrapolate });
        }

        let source = if let Ok(value) = nodes.getattr("nodes") {
            value
        } else {
            nodes.clone()
        };

        let points = source.extract::<Vec<Py<PyAny>>>()?;
        let mut parsed = Vec::with_capacity(points.len());
        for point in points {
            parsed.push(extract_vector2d(point.bind(py).as_any())?);
        }
        Ok(Self { curve: PolyLine2D { nodes: parsed }, extrapolate })
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

    fn scale(&self, factor: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let scaled = self.curve.scale(factor, py)?;
        let scaled = scaled.bind(py);
        if let Ok(polyline) = scaled.extract::<PolyLine2D>() {
            return Py::new(py, Self { curve: polyline, extrapolate: self.extrapolate }).map(|value| value.into_bound(py).into_any().unbind());
        }
        Err(PyTypeError::new_err("failed to scale interpolation"))
    }

    #[pyo3(name = "move")]
    fn r#move(&self, offset: &Bound<'_, PyAny>, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let moved = self.curve.r#move(offset, py)?;
        let moved = moved.bind(py);
        if let Ok(polyline) = moved.extract::<PolyLine2D>() {
            return Py::new(py, Self { curve: polyline, extrapolate: self.extrapolate }).map(|value| value.into_bound(py).into_any().unbind());
        }
        Err(PyTypeError::new_err("failed to move interpolation"))
    }

    fn add(&self, other: &Interpolation) -> Self {
        Self {
            curve: self.curve.add(&other.curve),
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

macro_rules! register_polyline_classes {
    ($m:expr) => {
        $m.add_class::<PolyLine2D>()?;
        $m.add_class::<PolyLine3D>()?;
        $m.add_class::<Interpolation>()?;
    };
}

#[pymodule(submodule, name = "vector")]
pub(crate) mod vector_mod {
    #[pymodule_export]
    use super::CutResult;
    #[pymodule_export]
    use super::Interpolation;
    #[pymodule_export]
    use super::PolyLine2D;
    #[pymodule_export]
    use super::PolyLine3D;
    #[pymodule_export]
    use super::Rotation2D;
    #[pymodule_export]
    use super::Transformation;
    #[pymodule_export]
    use super::Vector2D;
    #[pymodule_export]
    use super::Vector3D;
    #[pymodule_export]
    use super::cut;
    #[pymodule_export]
    use super::cut_2d;
}
