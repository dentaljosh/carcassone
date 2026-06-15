// CUDA-stream shim for carc-orch.
//
// tch 0.24 exposes NO CUDA-stream API, so to give each forwarder thread its own
// non-default stream (so their forward kernels overlap on the GPU instead of
// serializing on the shared default stream) we call libtorch's c10::cuda stream
// API directly from a tiny C++ TU and expose plain `extern "C"` entry points.
//
// libtorch's current-CUDA-stream is THREAD-LOCAL: setCurrentCUDAStream(s) affects
// only the calling thread, and every CUDA op that thread subsequently issues
// (i.e. that forwarder's module.forward) runs on `s`. So each forwarder thread
// calls carc_set_thread_stream() once at startup -> N forwarders -> N streams ->
// kernels overlap. This is the in-process equivalent of orch-off's N independent
// per-process CUDA contexts (the free concurrency that made orch-off win).
//
// Must be compiled with -D_GLIBCXX_USE_CXX11_ABI matching libtorch (=1 here) so
// the by-value CUDAStream symbol mangling matches the exported library symbols.
#include <c10/cuda/CUDAStream.h>

extern "C" {

// Acquire a fresh stream from this device's pool and make it the current stream
// for the CALLING thread. Pool has 32 streams/device; <=32 callers get distinct
// streams. Safe to call once per forwarder thread at startup.
void carc_set_thread_stream(int device) {
    auto s = c10::cuda::getStreamFromPool(/*isHighPriority=*/false,
                                          static_cast<c10::DeviceIndex>(device));
    c10::cuda::setCurrentCUDAStream(s);
}

// Debug/verification: the raw cudaStream_t of the calling thread's current
// stream, as an integer. The default stream is 0; a pooled stream is non-zero.
// Lets the orchestrator log that its forwarders are on DISTINCT, non-default
// streams (proof the overlap path is actually engaged).
long long carc_current_stream_id(int device) {
    auto s = c10::cuda::getCurrentCUDAStream(static_cast<c10::DeviceIndex>(device));
    return reinterpret_cast<long long>(s.stream());
}

}  // extern "C"
