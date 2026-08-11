//! Phase-0 binding smoke: prove tch-rs loads the exported TorchScript module
//! on CUDA and runs the (obs, scalars, mask) -> (priors, values) forward with
//! sane output. If this prints valid shapes + priors rows summing to ~1, the
//! libtorch 2.11/cu128 binding works and the server build is unblocked.
//!
//! Run: LIBTORCH_USE_PYTORCH=1 LIBTORCH_BYPASS_VERSION_CHECK=1 \
//!      LD_LIBRARY_PATH=$TORCHLIB cargo run --release --bin smoke -- /tmp/carc_iter8.ts.pt
use anyhow::{Context, Result};
use tch::{CModule, Device, IValue, Kind, Tensor};

fn main() -> Result<()> {
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "/tmp/carc_iter8.ts.pt".to_string());

    let cuda = Device::cuda_if_available();
    println!("[smoke] device = {:?}, cuda_available = {}", cuda, tch::Cuda::is_available());

    let mut module = CModule::load_on_device(&path, cuda)
        .with_context(|| format!("loading TorchScript module {path}"))?;
    module.set_eval();
    println!("[smoke] loaded {path}");

    // iter8 dims: obs (k,78,25,25) f32, scalars (k,12) f32, mask (k,2511) bool.
    for &k in &[1i64, 8, 37] {
        let obs = Tensor::randn([k, 78, 25, 25], (Kind::Float, cuda));
        let scalars = Tensor::randn([k, 12], (Kind::Float, cuda));
        // mask: all-true except force determinism; bool tensor.
        let mask = Tensor::ones([k, 2511], (Kind::Bool, cuda));

        let out = module
            .forward_is(&[
                IValue::Tensor(obs),
                IValue::Tensor(scalars),
                IValue::Tensor(mask),
            ])
            .context("forward_is")?;

        let (priors, values) = match out {
            IValue::Tuple(mut v) => {
                let values = match v.pop().unwrap() {
                    IValue::Tensor(t) => t,
                    other => anyhow::bail!("expected Tensor value, got {other:?}"),
                };
                let priors = match v.pop().unwrap() {
                    IValue::Tensor(t) => t,
                    other => anyhow::bail!("expected Tensor priors, got {other:?}"),
                };
                (priors, values)
            }
            other => anyhow::bail!("expected Tuple output, got {other:?}"),
        };

        let psum = f64::try_from(priors.sum(Kind::Float))? / (k as f64);
        let pshape = priors.size();
        let vshape = values.size();
        let v0 = f64::try_from(values.get(0))?;
        println!(
            "[smoke] k={k:3}: priors{pshape:?} values{vshape:?}  mean_row_sum={psum:.6}  v[0]={v0:+.4}"
        );
        if (psum - 1.0).abs() > 1e-3 {
            anyhow::bail!("priors rows do not sum to ~1 (got {psum}) — masked softmax broken");
        }
    }
    println!("[smoke] OK — tch-rs <-> libtorch CUDA forward verified.");
    Ok(())
}
