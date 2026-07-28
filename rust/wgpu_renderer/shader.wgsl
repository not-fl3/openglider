struct Camera {
    mvp: mat4x4<f32>,
};

@group(0) @binding(0)
var<uniform> camera: Camera;

struct VertexInput {
    @location(0) position: vec3<f32>,
    @location(1) color: vec3<f32>,
    @location(2) normal: vec3<f32>,
};

struct VertexOutput {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) color: vec3<f32>,
    @location(1) normal: vec3<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    output.clip_position = camera.mvp * vec4<f32>(input.position, 1.0);
    output.color = input.color;
    output.normal = input.normal;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let light_dir = normalize(vec3<f32>(0.4, 1.0, 0.3));
    let n = normalize(input.normal);
    // Double-sided lighting: front and back faces receive similar shading.
    let diffuse = abs(dot(n, light_dir));

    // Keep brightness controlled while preserving color contrast.
    let shade = 0.55 + 0.30 * pow(diffuse, 0.8);

    // Mild saturation boost to avoid pastel/faded appearance.
    let luma = dot(input.color, vec3<f32>(0.2126, 0.7152, 0.0722));
    let saturated = mix(vec3<f32>(luma, luma, luma), input.color, 1.22);

    let color = clamp(saturated * shade, vec3<f32>(0.0, 0.0, 0.0), vec3<f32>(1.0, 1.0, 1.0));
    return vec4<f32>(color, 1.0);
}
