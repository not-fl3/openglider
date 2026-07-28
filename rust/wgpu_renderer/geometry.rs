use crate::mesh::Mesh;

use super::Vertex;

fn triangle_normal(a: [f32; 3], b: [f32; 3], c: [f32; 3]) -> [f32; 3] {
    let ux = b[0] - a[0];
    let uy = b[1] - a[1];
    let uz = b[2] - a[2];
    let vx = c[0] - a[0];
    let vy = c[1] - a[1];
    let vz = c[2] - a[2];

    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    let length = (nx * nx + ny * ny + nz * nz).sqrt().max(1e-6);
    [nx / length, ny / length, nz / length]
}

pub(crate) fn mesh_to_vertices(mesh: &Mesh) -> (Vec<Vertex>, Vec<Vertex>) {
    let mut fill_vertices = Vec::new();
    let mut line_vertices = Vec::new();

    for object in &mesh.objects {
        let color = [
            object.color.0 as f32 / 255.0,
            object.color.1 as f32 / 255.0,
            object.color.2 as f32 / 255.0,
        ];

        for line in &object.lines {
            if let (Some(a), Some(b)) = (mesh.points.get(line.a), mesh.points.get(line.b)) {
                line_vertices.push(Vertex {
                    position: [a.x as f32, a.y as f32, a.z as f32],
                    color,
                    normal: [0.0, 0.0, 1.0],
                });
                line_vertices.push(Vertex {
                    position: [b.x as f32, b.y as f32, b.z as f32],
                    color,
                    normal: [0.0, 0.0, 1.0],
                });
            }
        }

        for triangle in &object.triangles {
            let p0 = mesh.points.get(triangle.a);
            let p1 = mesh.points.get(triangle.b);
            let p2 = mesh.points.get(triangle.c);
            if let (Some(p0), Some(p1), Some(p2)) = (p0, p1, p2) {
                let a = [p0.x as f32, p0.y as f32, p0.z as f32];
                let b = [p1.x as f32, p1.y as f32, p1.z as f32];
                let c = [p2.x as f32, p2.y as f32, p2.z as f32];
                let normal = triangle_normal(a, b, c);
                fill_vertices.push(Vertex {
                    position: a,
                    color,
                    normal,
                });
                fill_vertices.push(Vertex {
                    position: b,
                    color,
                    normal,
                });
                fill_vertices.push(Vertex {
                    position: c,
                    color,
                    normal,
                });
            }
        }

        for quad in &object.quads {
            let faces = [(quad.a, quad.b, quad.c), (quad.a, quad.c, quad.d)];
            for (a, b, c) in faces {
                let p0 = mesh.points.get(a);
                let p1 = mesh.points.get(b);
                let p2 = mesh.points.get(c);
                if let (Some(p0), Some(p1), Some(p2)) = (p0, p1, p2) {
                    let pa = [p0.x as f32, p0.y as f32, p0.z as f32];
                    let pb = [p1.x as f32, p1.y as f32, p1.z as f32];
                    let pc = [p2.x as f32, p2.y as f32, p2.z as f32];
                    let normal = triangle_normal(pa, pb, pc);
                    fill_vertices.push(Vertex {
                        position: pa,
                        color,
                        normal,
                    });
                    fill_vertices.push(Vertex {
                        position: pb,
                        color,
                        normal,
                    });
                    fill_vertices.push(Vertex {
                        position: pc,
                        color,
                        normal,
                    });
                }
            }
        }
    }

    (fill_vertices, line_vertices)
}
