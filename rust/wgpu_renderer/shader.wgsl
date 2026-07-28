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
    // Compute smooth normals from position derivatives for smooth shading across facets.
    let dpx = dpdx(input.position);
    let dpy = dpdy(input.position);
    let cross_prod = cross(dpx, dpy);
    let smooth_normal = select(input.normal, normalize(cross_prod), length(cross_prod) > 0.001);
    
    let light_dir = normalize(vec3<f32>(0.4, 1.0, 0.3));
    let view_dir = normalize(vec3<f32>(0.0, 0.0, 1.0));
    let n = mix(smooth_normal, input.normal, 0.35);  // Blend smooth normals with original for better results
    
    // Use wrapped diffuse to soften hard transitions between polygon facets.
    let ndotl = abs(dot(n, light_dir));
    let diffuse = pow((ndotl + 0.35) / 1.35, 0.75);

    // Add stronger reflective/specular response for a more vivid look.
    let reflected = reflect(-light_dir, n);
    let specular = pow(max(dot(reflected, view_dir), 0.0), 28.0);
    let fresnel = pow(1.0 - abs(dot(n, view_dir)), 2.2);

    // Slightly stronger saturation boost to avoid pastel/faded appearance.
    let luma = dot(input.color, vec3<f32>(0.2126, 0.7152, 0.0722));
    let saturated = mix(vec3<f32>(luma, luma, luma), input.color, 1.30);

    let base = saturated * (0.42 + 0.58 * diffuse);
    let highlight = vec3<f32>(1.0, 1.0, 1.0) * (0.30 * specular + 0.16 * fresnel);
    let color = clamp(base + highlight, vec3<f32>(0.0, 0.0, 0.0), vec3<f32>(1.0, 1.0, 1.0));

    return vec4<f32>(color, 1.0);
}
