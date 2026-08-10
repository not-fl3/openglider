use anyhow::{anyhow, Context, Result};
use pyo3_introspection::{introspect_cdylib, module_stub_files};
use std::path::Path;
use std::{env, fs};

fn main() -> Result<()> {
    let [_, binary_path, module_name, output_path] = env::args()
        .collect::<Vec<_>>()
        .try_into()
        .map_err(|_| {
            anyhow!(
                "pyo3_stub_gen takes three arguments: the extension path, module name, and output directory"
            )
        })?;

    let module = introspect_cdylib(&binary_path, &module_name)
        .with_context(|| format!("Failed to introspect module {binary_path}"))?;
    let stub_files = module_stub_files(&module);

    for (relative_path, content) in stub_files {
        let file_path = Path::new(&output_path).join(relative_path);
        if let Some(parent) = file_path.parent() {
            fs::create_dir_all(parent)
                .with_context(|| format!("Failed to create output directory {}", parent.display()))?;
        }
        fs::write(&file_path, content)
            .with_context(|| format!("Failed to write stub {}", file_path.display()))?;
    }

    Ok(())
}
