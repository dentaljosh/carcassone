//! `carc-cli` — replay/digest/fuzz driver over `carc-core`.
//!
//! P0 stub: exposes the `compat` primitives as line-oriented subcommands so a
//! fuzz harness can drive them without building the Python wheel (useful on the
//! laptop/M5 legs of the G0 transcendental harness, and on Android where there
//! is no maturin). P1+ adds `replay` / `digest`.

use std::io::{self, BufRead, Write};

use carc_core::compat;

fn usage() -> ! {
    eprintln!(
        "carc-cli {}\n\
         \n\
         usage:\n\
         \x20 carc-cli shuffle <seed-decimal> <n>      permutation of range(n)\n\
         \x20 carc-cli fsum                            f64s on stdin (one per line), one sum out\n\
         \x20 carc-cli npsum64                         f64s on stdin, np.sum order\n\
         \x20 carc-cli npsum32                         f32s on stdin, np.sum order\n\
         \x20 carc-cli exp [--fma]                     f64 hex bits per line -> hex bits\n\
         \x20 carc-cli tanh  [--flavor F]              F = msun|msun_fma|glibc|glibc_fma\n\
         \x20 carc-cli expm1 [--flavor F]              F = msun|msun_fma|glibc|glibc_fma\n\
         \x20 carc-cli selftest                        quick internal consistency check\n",
        carc_core::VERSION
    );
    std::process::exit(2)
}

fn read_f64_lines() -> Vec<f64> {
    let stdin = io::stdin();
    stdin
        .lock()
        .lines()
        .map_while(Result::ok)
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.trim().parse::<f64>().expect("expected a float per line"))
        .collect()
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.is_empty() {
        usage();
    }
    let out = io::stdout();
    let mut w = io::BufWriter::new(out.lock());
    match args[0].as_str() {
        "shuffle" => {
            if args.len() != 3 {
                usage();
            }
            let n: usize = args[2].parse().expect("n must be an integer");
            let p = compat::shuffle_indices(&args[1], compat::SeedMode::GlobalSeed, n);
            let s: Vec<String> = p.iter().map(|v| v.to_string()).collect();
            writeln!(w, "{}", s.join(" ")).unwrap();
        }
        "fsum" => {
            let v = read_f64_lines();
            writeln!(w, "{:016x}", compat::fsum(&v).to_bits()).unwrap();
        }
        "npsum64" => {
            let v = read_f64_lines();
            writeln!(w, "{:016x}", compat::np_sum_f64(&v).to_bits()).unwrap();
        }
        "npsum32" => {
            let v: Vec<f32> = read_f64_lines().into_iter().map(|x| x as f32).collect();
            writeln!(w, "{:08x}", compat::np_sum_f32(&v).to_bits()).unwrap();
        }
        "exp" | "tanh" | "expm1" => {
            let fma = args.iter().any(|a| a == "--fma");
            let flavor = args
                .iter()
                .position(|a| a == "--flavor")
                .and_then(|i| args.get(i + 1))
                .map(|s| s.as_str())
                .unwrap_or("msun");
            let flavor = match flavor {
                "msun" => compat::LibmFlavor::Msun,
                "msun_fma" => compat::LibmFlavor::MsunFma,
                "glibc" => compat::LibmFlavor::Glibc,
                "glibc_fma" => compat::LibmFlavor::GlibcFma,
                other => {
                    eprintln!("unknown --flavor {other}");
                    std::process::exit(2);
                }
            };
            let kind = args[0].clone();
            let stdin = io::stdin();
            for line in stdin.lock().lines().map_while(Result::ok) {
                let t = line.trim();
                if t.is_empty() {
                    continue;
                }
                let bits = u64::from_str_radix(t, 16).expect("expected f64 bits as hex");
                let x = f64::from_bits(bits);
                let y = match (kind.as_str(), fma) {
                    ("exp", false) => compat::exp64(x),
                    ("exp", true) => compat::exp64_fma(x),
                    ("expm1", _) => compat::expm1_64_flavor(x, flavor),
                    _ => compat::tanh64_flavor(x, flavor),
                };
                writeln!(w, "{:016x}", y.to_bits()).unwrap();
            }
        }
        "selftest" => {
            assert_eq!(compat::fsum(&[1e16, 1.0, -1e16]), 1.0);
            assert_eq!(compat::np_sum_f64(&[0.1; 10]), 0.1f64 * 0.0 + {
                let v = [0.1f64; 10];
                compat::np_sum_f64(&v)
            });
            let p = compat::shuffle_indices("0", compat::SeedMode::GlobalSeed, 71);
            assert_eq!(p.len(), 71);
            assert_eq!(compat::exp64(0.0), 1.0);
            assert_eq!(compat::tanh64(0.0), 0.0);
            writeln!(w, "ok {}", carc_core::VERSION).unwrap();
        }
        _ => usage(),
    }
}
