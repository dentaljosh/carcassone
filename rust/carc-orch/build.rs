//! Compiles the CUDA-stream C++ shim (csrc/cuda_stream_shim.cpp) and links it
//! against libtorch's c10_cuda. tch 0.24 has no stream API; the shim is how each
//! forwarder thread gets its own CUDA stream. See csrc/cuda_stream_shim.cpp.
//!
//! libtorch location: CARC_TORCH_DIR or LIBTORCH env if set, else discovered via
//! python (matching tch's LIBTORCH_USE_PYTORCH=1 mode). The C++ ABI flag must
//! match libtorch (torch 2.11 cu128 here is CXX11_ABI=1); override with
//! CARC_TORCH_CXX11_ABI if a future wheel differs.
use std::path::PathBuf;
use std::process::Command;

fn torch_dir() -> PathBuf {
    for var in ["CARC_TORCH_DIR", "LIBTORCH"] {
        if let Ok(d) = std::env::var(var) {
            if !d.is_empty() {
                return PathBuf::from(d);
            }
        }
    }
    // LIBTORCH_USE_PYTORCH path: ask python where torch lives.
    let py = std::env::var("CARC_PYTHON").unwrap_or_else(|_| "python3".to_string());
    let out = Command::new(&py)
        .args(["-c", "import torch,os;print(os.path.dirname(torch.__file__))"])
        .output()
        .unwrap_or_else(|e| panic!("locate torch via `{py}`: {e}; set CARC_TORCH_DIR"));
    let dir = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if dir.is_empty() {
        panic!(
            "could not locate torch (python stderr: {}); set CARC_TORCH_DIR",
            String::from_utf8_lossy(&out.stderr)
        );
    }
    PathBuf::from(dir)
}

fn main() {
    let torch = torch_dir();
    let inc = torch.join("include");
    let lib = torch.join("lib");
    let abi = std::env::var("CARC_TORCH_CXX11_ABI").unwrap_or_else(|_| "1".to_string());

    if !inc.join("c10/cuda/CUDAStream.h").exists() {
        panic!(
            "missing {} — torch headers not found under {}",
            inc.join("c10/cuda/CUDAStream.h").display(),
            torch.display()
        );
    }

    // CUDAStream.h pulls in <cuda_runtime_api.h>, which in turn needs the full CUDA
    // header tree (crt/host_defines.h ...). These ship in pip wheels next to torch/
    // in site-packages, but the nvidia-cuda-runtime wheel is INCOMPLETE (no crt/);
    // triton bundles a complete tree. Pick the first candidate that has BOTH the
    // entry header and crt/host_defines.h. Override: CARC_CUDA_INCLUDE.
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(d) = std::env::var("CARC_CUDA_INCLUDE") {
        if !d.is_empty() {
            candidates.push(PathBuf::from(d));
        }
    }
    if let Some(site) = torch.parent() {
        candidates.push(site.join("triton/backends/nvidia/include"));
        candidates.push(site.join("nvidia/cuda_runtime/include"));
    }
    let cuda_inc = candidates
        .into_iter()
        .find(|p| p.join("cuda_runtime_api.h").exists() && p.join("crt/host_defines.h").exists())
        .unwrap_or_else(|| {
            panic!(
                "no complete CUDA include dir found (need cuda_runtime_api.h + \
                 crt/host_defines.h, looked next to {}); set CARC_CUDA_INCLUDE",
                torch.display()
            )
        });

    cc::Build::new()
        .cpp(true)
        .file("csrc/cuda_stream_shim.cpp")
        .include(&inc)
        .include(inc.join("torch/csrc/api/include"))
        .include(&cuda_inc)
        .flag_if_supported("-std=c++17")
        .flag(&format!("-D_GLIBCXX_USE_CXX11_ABI={abi}"))
        .warnings(false)
        .compile("carc_cuda_shim");

    // Link c10_cuda (the stream API) + c10. torch-sys already adds the search
    // path and most torch libs; these are harmless if duplicated. rpath bakes the
    // lib dir so the .so resolves at runtime alongside the LD_PRELOAD'd libtorch.
    println!("cargo:rustc-link-search=native={}", lib.display());
    println!("cargo:rustc-link-lib=dylib=c10_cuda");
    println!("cargo:rustc-link-lib=dylib=c10");
    println!("cargo:rustc-link-arg=-Wl,-rpath,{}", lib.display());

    println!("cargo:rerun-if-changed=csrc/cuda_stream_shim.cpp");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=CARC_TORCH_DIR");
    println!("cargo:rerun-if-env-changed=LIBTORCH");
}
