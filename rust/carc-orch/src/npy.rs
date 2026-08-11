//! Minimal `.npy` (NumPy save format v1.0) read/write for the fixed dtypes
//! the orchestrator carries: float32 ('<f4') and bool ('|b1'). This matches
//! the blobs produced by `np.save(..., allow_pickle=False)` in
//! remote_eval_bridge.py — header is self-describing (shape + dtype), so the
//! Rust side never hardcodes board dims.
use anyhow::{bail, Context, Result};

const MAGIC: &[u8] = b"\x93NUMPY";

/// Parsed npy view: dtype descr, shape, and a slice into the raw data region.
pub struct NpyView<'a> {
    pub descr: String,
    pub shape: Vec<i64>,
    pub data: &'a [u8],
}

/// Parse the npy header and return a view over the raw data bytes.
pub fn parse<'a>(buf: &'a [u8]) -> Result<NpyView<'a>> {
    if buf.len() < 10 || &buf[0..6] != MAGIC {
        bail!("not an npy blob (bad magic)");
    }
    let major = buf[6];
    let (header_start, header_len) = if major == 1 {
        let l = u16::from_le_bytes([buf[8], buf[9]]) as usize;
        (10usize, l)
    } else {
        // v2.0+: 4-byte header length (guard the extra 2 bytes — §4 OOB fix)
        if buf.len() < 12 {
            bail!("npy v2 header truncated");
        }
        let l = u32::from_le_bytes([buf[8], buf[9], buf[10], buf[11]]) as usize;
        (12usize, l)
    };
    let header_end = header_start + header_len;
    if header_end > buf.len() {
        bail!("npy header length exceeds buffer");
    }
    let header = std::str::from_utf8(&buf[header_start..header_end])
        .context("npy header not utf8")?;

    let descr = extract_quoted(header, "'descr':")
        .context("npy header missing descr")?;
    let fortran = header.contains("'fortran_order': True");
    if fortran {
        bail!("fortran-ordered npy not supported");
    }
    let shape = extract_shape(header).context("npy header missing/!shape")?;

    Ok(NpyView { descr, shape, data: &buf[header_end..] })
}

/// Total element count, rejecting negative dims and overflow (§4 hardening
/// against a crafted/corrupt header feeding a bad shape into the batcher).
fn numel(shape: &[i64]) -> Result<usize> {
    let mut n: usize = 1;
    for &d in shape {
        if d < 0 {
            bail!("negative dim {d} in shape");
        }
        n = n.checked_mul(d as usize).context("shape product overflow")?;
    }
    Ok(n)
}

/// Interpret a parsed float32 ('<f4') blob as a Vec<f32>.
pub fn as_f32(v: &NpyView) -> Result<Vec<f32>> {
    if v.descr != "<f4" {
        bail!("expected '<f4' float32, got '{}'", v.descr);
    }
    let n = numel(&v.shape)?;
    let need = n.checked_mul(4).context("f32 size overflow")?;
    if v.data.len() < need {
        bail!("f32 data short: have {} need {}", v.data.len(), need);
    }
    let mut out = Vec::with_capacity(n);
    for c in v.data[..need].chunks_exact(4) {
        out.push(f32::from_le_bytes([c[0], c[1], c[2], c[3]]));
    }
    Ok(out)
}

/// Interpret a parsed bool ('|b1') blob as a Vec<u8> (0/1 per element).
pub fn as_bool_u8(v: &NpyView) -> Result<Vec<u8>> {
    if v.descr != "|b1" {
        bail!("expected '|b1' bool, got '{}'", v.descr);
    }
    let n = numel(&v.shape)?;
    if v.data.len() < n {
        bail!("bool data short: have {} need {}", v.data.len(), n);
    }
    Ok(v.data[..n].to_vec())
}

/// Write a C-contiguous float32 array as an npy v1.0 blob (numpy-loadable).
pub fn write_f32(shape: &[i64], data: &[f32]) -> Vec<u8> {
    let shape_str = if shape.len() == 1 {
        format!("({},)", shape[0])
    } else {
        let parts: Vec<String> = shape.iter().map(|d| d.to_string()).collect();
        format!("({})", parts.join(", "))
    };
    let dict = format!(
        "{{'descr': '<f4', 'fortran_order': False, 'shape': {}, }}",
        shape_str
    );
    // Pad header (magic 6 + ver 2 + len 2 + dict + '\n') to a 64-byte multiple.
    let prefix = 6 + 2 + 2;
    let unpadded = prefix + dict.len() + 1; // +1 for trailing '\n'
    let pad = (64 - (unpadded % 64)) % 64;
    let header_len = dict.len() + pad + 1; // padding spaces + newline

    let mut out = Vec::with_capacity(prefix + header_len + data.len() * 4);
    out.extend_from_slice(MAGIC);
    out.push(1); // major
    out.push(0); // minor
    out.extend_from_slice(&(header_len as u16).to_le_bytes());
    out.extend_from_slice(dict.as_bytes());
    out.extend(std::iter::repeat(b' ').take(pad));
    out.push(b'\n');
    for &x in data {
        out.extend_from_slice(&x.to_le_bytes());
    }
    out
}

fn extract_quoted(header: &str, key: &str) -> Option<String> {
    let i = header.find(key)? + key.len();
    let rest = &header[i..];
    let a = rest.find('\'')? + 1;
    let b = rest[a..].find('\'')? + a;
    Some(rest[a..b].to_string())
}

fn extract_shape(header: &str) -> Option<Vec<i64>> {
    let i = header.find("'shape':")? + "'shape':".len();
    let rest = &header[i..];
    let a = rest.find('(')? + 1;
    let b = rest[a..].find(')')? + a;
    let inner = &rest[a..b];
    let mut dims = Vec::new();
    for tok in inner.split(',') {
        let t = tok.trim();
        if t.is_empty() {
            continue;
        }
        dims.push(t.parse::<i64>().ok()?);
    }
    Some(dims)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn f32_roundtrip_2d() {
        let data: Vec<f32> = (0..6).map(|i| i as f32 * 0.5).collect();
        let blob = write_f32(&[2, 3], &data);
        // header region must be 64-byte aligned (numpy convention)
        assert_eq!((blob.len() - data.len() * 4) % 64, 0);
        let v = parse(&blob).unwrap();
        assert_eq!(v.descr, "<f4");
        assert_eq!(v.shape, vec![2, 3]);
        assert_eq!(as_f32(&v).unwrap(), data);
    }

    #[test]
    fn f32_roundtrip_1d_trailing_comma() {
        let data = vec![1.0f32, 2.0, 3.0];
        let blob = write_f32(&[3], &data);
        // 1-D numpy shape uses a trailing comma: (3,). Decode only the header
        // region (blob[10..10+hlen]) — the f32 data after it isn't UTF-8.
        let hlen = u16::from_le_bytes([blob[8], blob[9]]) as usize;
        let hdr = std::str::from_utf8(&blob[10..10 + hlen]).unwrap();
        assert!(hdr.contains("(3,)"), "header was {hdr:?}");
        let v = parse(&blob).unwrap();
        assert_eq!(v.shape, vec![3]);
        assert_eq!(as_f32(&v).unwrap(), data);
    }

    #[test]
    fn parses_real_numpy_bool_header() {
        // header numpy emits for a (2, 3) bool array, padded to 64 bytes.
        let dict = "{'descr': '|b1', 'fortran_order': False, 'shape': (2, 3), }";
        let mut buf = Vec::new();
        buf.extend_from_slice(b"\x93NUMPY");
        buf.push(1);
        buf.push(0);
        let prefix = 10;
        let pad = (64 - ((prefix + dict.len() + 1) % 64)) % 64;
        let hlen = dict.len() + pad + 1;
        buf.extend_from_slice(&(hlen as u16).to_le_bytes());
        buf.extend_from_slice(dict.as_bytes());
        buf.extend(std::iter::repeat(b' ').take(pad));
        buf.push(b'\n');
        buf.extend_from_slice(&[1u8, 0, 1, 0, 1, 1]); // 6 bools
        let v = parse(&buf).unwrap();
        assert_eq!(v.descr, "|b1");
        assert_eq!(v.shape, vec![2, 3]);
        assert_eq!(as_bool_u8(&v).unwrap(), vec![1, 0, 1, 0, 1, 1]);
    }

    #[test]
    fn rejects_bad_magic() {
        assert!(parse(b"not-an-npy-blob-at-all").is_err());
    }
}
