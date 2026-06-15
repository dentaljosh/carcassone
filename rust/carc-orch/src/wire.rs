//! Wire protocol — byte-for-byte identical to remote_eval_bridge.py so the
//! existing Python socket client (remote_socket_handles.connect_remote) talks
//! to this server unchanged.
//!
//!   Frame:    [4 B big-endian u32 body_len][body]
//!   Request:  [8 B worker_id i64 BE][8 B request_id i64 BE]
//!             [blob obs][blob scalars][blob mask]
//!   Response: [8 B request_id i64 BE][blob priors][blob values]
//!   blob:     [4 B big-endian u32 blob_len][npy bytes]
use anyhow::{bail, Result};
use std::io::{Read, Write};
use std::net::TcpStream;

use crate::npy;

const MAX_FRAME: usize = 64 * 1024 * 1024;

pub struct Request {
    pub request_id: i64,
    pub k: i64,
    pub obs: Vec<f32>,
    pub obs_inner: Vec<i64>,
    pub scalars: Vec<f32>,
    pub scalars_inner: Vec<i64>,
    pub mask: Vec<u8>,
    pub a_size: i64,
}

pub fn read_frame(stream: &mut TcpStream) -> Result<Vec<u8>> {
    let mut hdr = [0u8; 4];
    stream.read_exact(&mut hdr)?;
    let len = u32::from_be_bytes(hdr) as usize;
    if len == 0 {
        bail!("zero-length frame");
    }
    if len > MAX_FRAME {
        bail!("frame {} exceeds cap {}", len, MAX_FRAME);
    }
    let mut body = vec![0u8; len];
    stream.read_exact(&mut body)?;
    Ok(body)
}

pub fn write_frame(stream: &mut TcpStream, body: &[u8]) -> Result<()> {
    stream.write_all(&(body.len() as u32).to_be_bytes())?;
    stream.write_all(body)?;
    Ok(())
}

fn read_blob<'a>(buf: &'a [u8], off: &mut usize) -> Result<&'a [u8]> {
    if *off + 4 > buf.len() {
        bail!("truncated blob length");
    }
    let n = u32::from_be_bytes([buf[*off], buf[*off + 1], buf[*off + 2], buf[*off + 3]]) as usize;
    *off += 4;
    if *off + n > buf.len() {
        bail!("truncated blob body");
    }
    let s = &buf[*off..*off + n];
    *off += n;
    Ok(s)
}

pub fn parse_request(body: &[u8]) -> Result<Request> {
    if body.len() < 16 {
        bail!("request body too short");
    }
    // worker_id (ignored — routing is per-socket), request_id.
    let request_id = i64::from_be_bytes(body[8..16].try_into().unwrap());
    let mut off = 16usize;

    let obs_v = npy::parse(read_blob(body, &mut off)?)?;
    let scl_v = npy::parse(read_blob(body, &mut off)?)?;
    let msk_v = npy::parse(read_blob(body, &mut off)?)?;

    if obs_v.shape.is_empty() || scl_v.shape.is_empty() || msk_v.shape.is_empty() {
        bail!("zero-rank array in request");
    }
    let k = obs_v.shape[0];
    let obs = npy::as_f32(&obs_v)?;
    let obs_inner = obs_v.shape[1..].to_vec();
    let scalars = npy::as_f32(&scl_v)?;
    let scalars_inner = scl_v.shape[1..].to_vec();
    let mask = npy::as_bool_u8(&msk_v)?;
    let a_size = *msk_v.shape.last().unwrap();

    Ok(Request {
        request_id,
        k,
        obs,
        obs_inner,
        scalars,
        scalars_inner,
        mask,
        a_size,
    })
}

/// Build a response body: [request_id i64 BE][blob priors][blob values].
pub fn build_response(request_id: i64, priors_npy: &[u8], values_npy: &[u8]) -> Vec<u8> {
    let mut out =
        Vec::with_capacity(8 + 4 + priors_npy.len() + 4 + values_npy.len());
    out.extend_from_slice(&request_id.to_be_bytes());
    out.extend_from_slice(&(priors_npy.len() as u32).to_be_bytes());
    out.extend_from_slice(priors_npy);
    out.extend_from_slice(&(values_npy.len() as u32).to_be_bytes());
    out.extend_from_slice(values_npy);
    out
}
