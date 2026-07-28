use bytemuck::{Pod, Zeroable};
use nalgebra::{Matrix4, Orthographic3, Perspective3, Point3, Vector3};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use raw_window_handle::{
    AppKitDisplayHandle, AppKitWindowHandle, RawDisplayHandle, RawWindowHandle,
    WaylandDisplayHandle, WaylandWindowHandle, Win32WindowHandle, WindowsDisplayHandle,
    XcbDisplayHandle, XcbWindowHandle, XlibDisplayHandle, XlibWindowHandle,
};
use wgpu::util::DeviceExt;
use std::num::{NonZeroIsize, NonZeroU32};

#[cfg(target_os = "linux")]
use x11_dl::xlib;

mod camera;
mod geometry;

use camera::{matrix_to_uniform, ProjectionMode};
use geometry::mesh_to_vertices;

use crate::mesh::Mesh;

#[repr(C)]
#[derive(Clone, Copy, Debug, Pod, Zeroable)]
struct Vertex {
    position: [f32; 3],
    color: [f32; 3],
    normal: [f32; 3],
}

impl Vertex {
    fn layout<'a>() -> wgpu::VertexBufferLayout<'a> {
        wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<Vertex>() as u64,
            step_mode: wgpu::VertexStepMode::Vertex,
            attributes: &[
                wgpu::VertexAttribute {
                    offset: 0,
                    shader_location: 0,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: std::mem::size_of::<[f32; 3]>() as u64,
                    shader_location: 1,
                    format: wgpu::VertexFormat::Float32x3,
                },
                wgpu::VertexAttribute {
                    offset: std::mem::size_of::<[f32; 6]>() as u64,
                    shader_location: 2,
                    format: wgpu::VertexFormat::Float32x3,
                },
            ],
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
struct CameraUniform {
    mvp: [[f32; 4]; 4],
}

#[derive(Clone, Copy)]
struct CameraState {
    yaw: f32,
    pitch: f32,
    distance: f32,
    target: [f32; 3],
}

impl Default for CameraState {
    fn default() -> Self {
        Self {
            yaw: -1.2,
            pitch: 0.3,
            distance: 20.0,
            target: [0.0, 0.0, 0.0],
        }
    }
}

struct DepthResources {
    _texture: wgpu::Texture,
    view: wgpu::TextureView,
}

impl DepthResources {
    fn new(device: &wgpu::Device, width: u32, height: u32) -> Self {
        let size = wgpu::Extent3d {
            width: width.max(1),
            height: height.max(1),
            depth_or_array_layers: 1,
        };

        let texture = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("openglider.depth"),
            size,
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Depth24Plus,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            view_formats: &[],
        });

        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        Self { _texture: texture, view }
    }
}

struct NativeHandles {
    #[cfg(target_os = "linux")]
    _xlib: Option<xlib::Xlib>,
    raw_display_handle: RawDisplayHandle,
    raw_window_handle: RawWindowHandle,
}

#[cfg(target_os = "linux")]
fn linux_xlib_handles(window_id: u64, display_id: Option<u64>) -> PyResult<NativeHandles> {
    let xlib = xlib::Xlib::open().map_err(|_| PyRuntimeError::new_err("failed to load libX11"))?;
    let display = if let Some(id) = display_id {
        id as *mut xlib::Display
    } else {
        unsafe { (xlib.XOpenDisplay)(std::ptr::null()) }
    };
    if display.is_null() {
        return Err(PyRuntimeError::new_err(
            "failed to open X11 display; this renderer currently requires X11",
        ));
    }

    let display_ptr = display.cast::<std::ffi::c_void>();
    let screen = unsafe { (xlib.XDefaultScreen)(display) };

    let mut display_handle = XlibDisplayHandle::new(None, screen);
    display_handle.display = std::ptr::NonNull::new(display_ptr.cast());

    let mut window_handle = XlibWindowHandle::new(window_id);
    window_handle.visual_id = 0;

    Ok(NativeHandles {
        _xlib: Some(xlib),
        raw_display_handle: RawDisplayHandle::Xlib(display_handle),
        raw_window_handle: RawWindowHandle::Xlib(window_handle),
    })
}

fn make_native_handles(platform: &str, window_id: u64, display_id: Option<u64>) -> PyResult<NativeHandles> {
    match platform {
        "wayland" => {
            let display_ptr = display_id
                .and_then(|value| std::ptr::NonNull::new(value as *mut std::ffi::c_void))
                .ok_or_else(|| PyValueError::new_err("wayland requires non-zero display_id"))?;
            let surface_ptr = std::ptr::NonNull::new(window_id as *mut std::ffi::c_void)
                .ok_or_else(|| PyValueError::new_err("wayland requires non-zero window_id"))?;

            let display_handle = WaylandDisplayHandle::new(display_ptr);
            let window_handle = WaylandWindowHandle::new(surface_ptr);

            Ok(NativeHandles {
                #[cfg(target_os = "linux")]
                _xlib: None,
                raw_display_handle: RawDisplayHandle::Wayland(display_handle),
                raw_window_handle: RawWindowHandle::Wayland(window_handle),
            })
        }
        "xcb" => {
            let connection_ptr = display_id
                .and_then(|value| std::ptr::NonNull::new(value as *mut std::ffi::c_void));
            let window = NonZeroU32::new(window_id as u32)
                .ok_or_else(|| PyValueError::new_err("xcb requires non-zero 32-bit window_id"))?;

            let display_handle = XcbDisplayHandle::new(connection_ptr, 0);
            let window_handle = XcbWindowHandle::new(window);

            Ok(NativeHandles {
                #[cfg(target_os = "linux")]
                _xlib: None,
                raw_display_handle: RawDisplayHandle::Xcb(display_handle),
                raw_window_handle: RawWindowHandle::Xcb(window_handle),
            })
        }
        "x11" => {
            #[cfg(target_os = "linux")]
            {
                linux_xlib_handles(window_id, display_id)
            }

            #[cfg(not(target_os = "linux"))]
            {
                let _ = display_id;
                Err(PyRuntimeError::new_err("x11 surface is only available on Linux"))
            }
        }
        "win32" => {
            let hwnd = NonZeroIsize::new(window_id as isize)
                .ok_or_else(|| PyValueError::new_err("win32 requires non-zero window_id"))?;
            let display_handle = WindowsDisplayHandle::new();
            let window_handle = Win32WindowHandle::new(hwnd);

            Ok(NativeHandles {
                #[cfg(target_os = "linux")]
                _xlib: None,
                raw_display_handle: RawDisplayHandle::Windows(display_handle),
                raw_window_handle: RawWindowHandle::Win32(window_handle),
            })
        }
        "appkit" => {
            let ns_view = std::ptr::NonNull::new(window_id as *mut std::ffi::c_void)
                .ok_or_else(|| PyValueError::new_err("appkit requires non-zero window_id"))?;
            let display_handle = AppKitDisplayHandle::new();
            let window_handle = AppKitWindowHandle::new(ns_view);

            Ok(NativeHandles {
                #[cfg(target_os = "linux")]
                _xlib: None,
                raw_display_handle: RawDisplayHandle::AppKit(display_handle),
                raw_window_handle: RawWindowHandle::AppKit(window_handle),
            })
        }
        other => Err(PyValueError::new_err(format!(
            "unsupported platform '{other}', expected one of: x11, xcb, wayland, win32, appkit"
        ))),
    }
}

const SHADER_SOURCE: &str = include_str!("shader.wgsl");

struct RendererState {
    _instance: wgpu::Instance,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    fill_pipeline: wgpu::RenderPipeline,
    line_pipeline: wgpu::RenderPipeline,
    camera: CameraState,
    projection_mode: ProjectionMode,
    uniform_buffer: wgpu::Buffer,
    uniform_bind_group: wgpu::BindGroup,
    depth: DepthResources,
    fill_vertex_buffer: wgpu::Buffer,
    fill_vertex_count: u32,
    line_vertex_buffer: wgpu::Buffer,
    line_vertex_count: u32,
    width: u32,
    height: u32,
    _native: NativeHandles,
}

impl RendererState {
    fn new(platform: &str, window_id: u64, width: u32, height: u32, display_id: Option<u64>) -> PyResult<Self> {
        let native = make_native_handles(platform, window_id, display_id)?;

        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::default());
        let surface = unsafe {
            instance.create_surface_unsafe(wgpu::SurfaceTargetUnsafe::RawHandle {
                raw_display_handle: native.raw_display_handle,
                raw_window_handle: native.raw_window_handle,
            })
        }
        .map_err(|error| PyRuntimeError::new_err(format!("failed to create wgpu surface: {error}")))?;

        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            force_fallback_adapter: false,
        }))
        .ok_or_else(|| PyRuntimeError::new_err("failed to acquire wgpu adapter"))?;

        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("openglider.wgpu.device"),
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::default(),
            },
            None,
        ))
        .map_err(|error| PyRuntimeError::new_err(format!("failed to create wgpu device: {error}")))?;

        let caps = surface.get_capabilities(&adapter);
        let surface_format = caps
            .formats
            .iter()
            .copied()
            .find(|format| format.is_srgb())
            .unwrap_or_else(|| caps.formats[0]);

        let present_mode = caps
            .present_modes
            .iter()
            .copied()
            .find(|mode| *mode == wgpu::PresentMode::Fifo)
            .unwrap_or(caps.present_modes[0]);

        let alpha_mode = caps.alpha_modes[0];

        let mut config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format: surface_format,
            width: width.max(1),
            height: height.max(1),
            present_mode,
            alpha_mode,
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };

        surface.configure(&device, &config);

        let uniform = CameraUniform {
            mvp: matrix_to_uniform(Matrix4::identity()),
        };
        let uniform_buffer = device.create_buffer_init(&wgpu::util::BufferInitDescriptor {
            label: Some("openglider.camera.uniform"),
            contents: bytemuck::bytes_of(&uniform),
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
        });

        let uniform_bind_group_layout =
            device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
                label: Some("openglider.camera.layout"),
                entries: &[wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::VERTEX,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: wgpu::BufferSize::new(std::mem::size_of::<CameraUniform>() as u64),
                    },
                    count: None,
                }],
            });

        let uniform_bind_group = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("openglider.camera.bindgroup"),
            layout: &uniform_bind_group_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buffer.as_entire_binding(),
            }],
        });

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("openglider.mesh.shader"),
            source: wgpu::ShaderSource::Wgsl(SHADER_SOURCE.into()),
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("openglider.pipeline.layout"),
            bind_group_layouts: &[&uniform_bind_group_layout],
            push_constant_ranges: &[],
        });

        let fill_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("openglider.mesh.pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: "vs_main",
                buffers: &[Vertex::layout()],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: "fs_main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleList,
                strip_index_format: None,
                front_face: wgpu::FrontFace::Ccw,
                cull_mode: None,
                polygon_mode: wgpu::PolygonMode::Fill,
                unclipped_depth: false,
                conservative: false,
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth24Plus,
                depth_write_enabled: true,
                depth_compare: wgpu::CompareFunction::Less,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
        });

        let line_pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("openglider.mesh.line.pipeline"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: "vs_main",
                buffers: &[Vertex::layout()],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: "fs_main",
                targets: &[Some(wgpu::ColorTargetState {
                    format: config.format,
                    blend: Some(wgpu::BlendState::REPLACE),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::LineList,
                strip_index_format: None,
                front_face: wgpu::FrontFace::Ccw,
                cull_mode: None,
                polygon_mode: wgpu::PolygonMode::Fill,
                unclipped_depth: false,
                conservative: false,
            },
            depth_stencil: Some(wgpu::DepthStencilState {
                format: wgpu::TextureFormat::Depth24Plus,
                depth_write_enabled: false,
                depth_compare: wgpu::CompareFunction::LessEqual,
                stencil: wgpu::StencilState::default(),
                bias: wgpu::DepthBiasState::default(),
            }),
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
        });

        let depth = DepthResources::new(&device, config.width, config.height);
        let fill_vertex_buffer = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("openglider.mesh.vertices.empty"),
            size: std::mem::size_of::<Vertex>() as u64,
            usage: wgpu::BufferUsages::VERTEX,
            mapped_at_creation: false,
        });

        let line_vertex_buffer = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("openglider.mesh.lines.empty"),
            size: std::mem::size_of::<Vertex>() as u64,
            usage: wgpu::BufferUsages::VERTEX,
            mapped_at_creation: false,
        });

        config.width = config.width.max(1);
        config.height = config.height.max(1);

        let mut state = Self {
            _instance: instance,
            surface,
            device,
            queue,
            config,
            fill_pipeline,
            line_pipeline,
            camera: CameraState::default(),
            projection_mode: ProjectionMode::Orthographic,
            uniform_buffer,
            uniform_bind_group,
            depth,
            fill_vertex_buffer,
            fill_vertex_count: 0,
            line_vertex_buffer,
            line_vertex_count: 0,
            width,
            height,
            _native: native,
        };

        state.update_camera();
        Ok(state)
    }

    fn update_camera(&mut self) {
        let target = Point3::new(self.camera.target[0], self.camera.target[1], self.camera.target[2]);

        let yaw = self.camera.yaw;
        let pitch = self.camera.pitch;
        let zoom_distance = self.camera.distance.max(0.1);

        // In orthographic mode, treat camera.distance as zoom scale, not as
        // physical camera translation. Keeping the camera far away avoids
        // clipping geometry when users zoom in close.
        let eye_distance = match self.projection_mode {
            ProjectionMode::Perspective => zoom_distance,
            ProjectionMode::Orthographic => 2000.0,
        };

        let eye = Point3::new(
            target.x + eye_distance * pitch.cos() * yaw.cos(),
            target.y + eye_distance * pitch.cos() * yaw.sin(),
            target.z + eye_distance * pitch.sin(),
        );

        let up = Vector3::new(0.0, 0.0, 1.0);
        let view = Matrix4::look_at_rh(&eye, &target, &up);

        let aspect = (self.config.width.max(1) as f32) / (self.config.height.max(1) as f32);
        let projection = match self.projection_mode {
            ProjectionMode::Perspective => {
                // Keep near small and avoid clamping to large values that can
                // clip close geometry too early.
                let near = (zoom_distance * 0.001).clamp(0.0001, 0.1);
                let far = (zoom_distance * 4000.0).max(20_000.0);
                Perspective3::new(aspect, 45f32.to_radians(), near, far).to_homogeneous()
            }
            ProjectionMode::Orthographic => {
                // Ortho zoom is controlled by half extents, not camera motion.
                let half_height = (zoom_distance * 0.5).max(0.05);
                let half_width = half_height * aspect;
                let near = 0.0001;
                let far = 10_000.0;
                Orthographic3::new(
                    -half_width,
                    half_width,
                    -half_height,
                    half_height,
                    near,
                    far,
                )
                .to_homogeneous()
            }
        };

        // Convert OpenGL-style clip space (z in [-1, 1]) to WGPU clip space
        // (z in [0, 1]). This keeps depth testing and perspective consistent.
        let opengl_to_wgpu = Matrix4::new(
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 0.5, 0.5,
            0.0, 0.0, 0.0, 1.0,
        );

        let uniform = CameraUniform {
            mvp: matrix_to_uniform(opengl_to_wgpu * projection * view),
        };
        self.queue
            .write_buffer(&self.uniform_buffer, 0, bytemuck::bytes_of(&uniform));
    }

    fn set_projection(&mut self, mode: &str) -> PyResult<()> {
        self.projection_mode = ProjectionMode::from_str(mode)?;
        self.update_camera();
        Ok(())
    }

    fn resize(&mut self, width: u32, height: u32) {
        self.config.width = width.max(1);
        self.config.height = height.max(1);
        self.width = width;
        self.height = height;
        self.surface.configure(&self.device, &self.config);
        self.depth = DepthResources::new(&self.device, self.config.width, self.config.height);
        self.update_camera();
    }

    fn set_mesh(&mut self, mesh: &Mesh) {
        let (fill_vertices, line_vertices) = mesh_to_vertices(mesh);

        if fill_vertices.is_empty() {
            self.fill_vertex_buffer = self.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("openglider.mesh.vertices.empty"),
                size: std::mem::size_of::<Vertex>() as u64,
                usage: wgpu::BufferUsages::VERTEX,
                mapped_at_creation: false,
            });
            self.fill_vertex_count = 0;
        } else {
            self.fill_vertex_buffer = self
                .device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("openglider.mesh.vertices"),
                    contents: bytemuck::cast_slice(&fill_vertices),
                    usage: wgpu::BufferUsages::VERTEX,
                });
            self.fill_vertex_count = fill_vertices.len() as u32;
        }

        if line_vertices.is_empty() {
            self.line_vertex_buffer = self.device.create_buffer(&wgpu::BufferDescriptor {
                label: Some("openglider.mesh.lines.empty"),
                size: std::mem::size_of::<Vertex>() as u64,
                usage: wgpu::BufferUsages::VERTEX,
                mapped_at_creation: false,
            });
            self.line_vertex_count = 0;
        } else {
            self.line_vertex_buffer = self
                .device
                .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                    label: Some("openglider.mesh.lines"),
                    contents: bytemuck::cast_slice(&line_vertices),
                    usage: wgpu::BufferUsages::VERTEX,
                });
            self.line_vertex_count = line_vertices.len() as u32;
        }
    }

    fn render(&mut self) -> PyResult<()> {
        let frame = match self.surface.get_current_texture() {
            Ok(frame) => frame,
            Err(wgpu::SurfaceError::Lost | wgpu::SurfaceError::Outdated) => {
                self.surface.configure(&self.device, &self.config);
                return Ok(());
            }
            Err(wgpu::SurfaceError::OutOfMemory) => {
                return Err(PyRuntimeError::new_err("wgpu surface out of memory"));
            }
            Err(wgpu::SurfaceError::Timeout) => {
                return Ok(());
            }
        };

        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());

        let mut encoder =
            self.device
                .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                    label: Some("openglider.wgpu.encoder"),
                });

        {
            let mut render_pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("openglider.wgpu.pass"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color {
                            r: 0.12,
                            g: 0.16,
                            b: 0.2,
                            a: 1.0,
                        }),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: Some(wgpu::RenderPassDepthStencilAttachment {
                    view: &self.depth.view,
                    depth_ops: Some(wgpu::Operations {
                        load: wgpu::LoadOp::Clear(1.0),
                        store: wgpu::StoreOp::Store,
                    }),
                    stencil_ops: None,
                }),
                occlusion_query_set: None,
                timestamp_writes: None,
            });

            render_pass.set_bind_group(0, &self.uniform_bind_group, &[]);
            if self.fill_vertex_count > 0 {
                render_pass.set_pipeline(&self.fill_pipeline);
                render_pass.set_vertex_buffer(0, self.fill_vertex_buffer.slice(..));
                render_pass.draw(0..self.fill_vertex_count, 0..1);
            }
            if self.line_vertex_count > 0 {
                render_pass.set_pipeline(&self.line_pipeline);
                render_pass.set_vertex_buffer(0, self.line_vertex_buffer.slice(..));
                render_pass.draw(0..self.line_vertex_count, 0..1);
            }
        }

        self.queue.submit(Some(encoder.finish()));
        frame.present();
        Ok(())
    }
}

#[pyclass(module = "openglider.rs.wgpu", unsendable)]
pub struct NativeWgpuRenderer {
    state: Option<RendererState>,
}

#[pymethods]
impl NativeWgpuRenderer {
    #[new]
    #[pyo3(signature = (platform, window_id, width, height, display_id = None))]
    fn new(platform: &str, window_id: u64, width: u32, height: u32, display_id: Option<u64>) -> PyResult<Self> {
        if window_id == 0 {
            return Err(PyValueError::new_err("window_id must be non-zero"));
        }

        let state = RendererState::new(platform, window_id, width, height, display_id)?;
        Ok(Self { state: Some(state) })
    }

    fn resize(&mut self, width: u32, height: u32) {
        if let Some(state) = self.state.as_mut() {
            state.resize(width, height);
        }
    }

    fn set_mesh(&mut self, mesh: PyRef<'_, Mesh>) {
        if let Some(state) = self.state.as_mut() {
            state.set_mesh(&mesh);
        }
    }

    #[pyo3(signature = (yaw, pitch, distance, target_x, target_y, target_z))]
    fn set_camera(
        &mut self,
        yaw: f32,
        pitch: f32,
        distance: f32,
        target_x: f32,
        target_y: f32,
        target_z: f32,
    ) {
        if let Some(state) = self.state.as_mut() {
            state.camera = CameraState {
                yaw,
                pitch,
                distance,
                target: [target_x, target_y, target_z],
            };
            state.update_camera();
        }
    }

    fn render(&mut self) -> PyResult<()> {
        if let Some(state) = self.state.as_mut() {
            state.render()
        } else {
            Ok(())
        }
    }

    fn set_projection(&mut self, mode: &str) -> PyResult<()> {
        if let Some(state) = self.state.as_mut() {
            state.set_projection(mode)?;
        }
        Ok(())
    }

    fn close(&mut self) {
        self.state = None;
    }
}

impl Drop for NativeWgpuRenderer {
    fn drop(&mut self) {
        self.state = None;
    }
}

#[pymodule(submodule, name = "wgpu")]
pub(crate) mod wgpu_mod {
    #[pymodule_export]
    use super::NativeWgpuRenderer;
}
