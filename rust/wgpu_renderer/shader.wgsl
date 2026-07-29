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
    @location(0) @interpolate(linear) color: vec3<f32>,
    @location(1) @interpolate(linear) normal: vec3<f32>,
    @location(2) @interpolate(linear) position: vec3<f32>,
};

@vertex
fn vs_main(input: VertexInput) -> VertexOutput {
    var output: VertexOutput;
    output.clip_position = camera.mvp * vec4<f32>(input.position, 1.0);
    output.color = input.color;
    output.normal = input.normal;
    output.position = input.position;
    return output;
}

@fragment
fn fs_main(input: VertexOutput) -> @location(0) vec4<f32> {
    let light_dir = normalize(vec3<f32>(0.35, 0.8, 0.45));
    let view_dir = normalize(vec3<f32>(0.0, 0.0, 1.0));
    let n = normalize(input.normal);

    let ndotl = abs(dot(n, light_dir));
    let ambient = 0.16;
    let diffuse = 0.24 + 0.76 * pow(ndotl, 0.9);

    let reflected = reflect(-light_dir, n);
    let specular = pow(max(dot(reflected, view_dir), 0.0), 64.0);
    let rim = pow(1.0 - max(dot(n, view_dir), 0.0), 3.2);

    let luma = dot(input.color, vec3<f32>(0.2126, 0.7152, 0.0722));
    let saturated = mix(vec3<f32>(luma, luma, luma), input.color, 1.75);

    let base = saturated * (ambient + diffuse * 1.02);
    let highlight = vec3<f32>(1.0, 0.98, 0.92) * (0.12 * specular + 0.10 * rim);
    let color = clamp(base + highlight, vec3<f32>(0.0, 0.0, 0.0), vec3<f32>(1.0, 1.0, 1.0));

    return vec4<f32>(color, 1.0);
}
