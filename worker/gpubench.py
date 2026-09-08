"""Benchmark WebGPU (Dawn/RTX) vs OpenCV-CPU no preprocess do placar.

Pipeline: RGBA 1920x1080 -> cinza -> threshold 150 (igual clean_score).
Uso: python worker/gpubench.py [frame.jpg]
"""
from __future__ import annotations
import sys
import time
import numpy as np

FRAME = sys.argv[1] if len(sys.argv) > 1 else "D:/wikival-work/frames/calib_02_714s.jpg"
W, H = 1920, 1080

WGSL = """
@group(0) @binding(0) var<storage, read> src : array<u32>;
@group(0) @binding(1) var<storage, read_write> dst : array<u32>;
@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid : vec3<u32>) {
  let i = gid.x;
  if (i >= arrayLength(&src)) { return; }
  let px = src[i];
  let r = f32(px & 255u);
  let g = f32((px >> 8u) & 255u);
  let b = f32((px >> 16u) & 255u);
  let gray = 0.299 * r + 0.587 * g + 0.114 * b;
  dst[i] = select(0u, 255u, gray > 150.0);
}
"""


def main() -> int:
    import cv2
    import wgpu

    img = cv2.imread(FRAME)
    img = cv2.resize(img, (W, H))
    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    src_np = rgba.view(np.uint32).reshape(-1).copy()
    n = src_np.size

    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    info = adapter.info
    print(f"adapter: {info.get('device')} | backend={info.get('backend_type')}")
    device = adapter.request_device_sync()

    src_buf = device.create_buffer_with_data(data=src_np, usage=wgpu.BufferUsage.STORAGE)
    dst_buf = device.create_buffer(size=n * 4, usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC)
    read_buf = device.create_buffer(size=n * 4, usage=wgpu.BufferUsage.MAP_READ | wgpu.BufferUsage.COPY_DST)
    shader = device.create_shader_module(code=WGSL)
    pipe = device.create_compute_pipeline(layout="auto", compute={"module": shader, "entry_point": "main"})
    bind = device.create_bind_group(layout=pipe.get_bind_group_layout(0),
                                    entries=[{"binding": 0, "resource": {"buffer": src_buf, "offset": 0, "size": n * 4}},
                                             {"binding": 1, "resource": {"buffer": dst_buf, "offset": 0, "size": n * 4}}])

    def dispatch() -> None:
        enc = device.create_command_encoder()
        cp = enc.begin_compute_pass()
        cp.set_pipeline(pipe)
        cp.set_bind_group(0, bind)
        cp.dispatch_workgroups((n + 255) // 256)
        cp.end()
        enc.copy_buffer_to_buffer(dst_buf, 0, read_buf, 0, n * 4)
        device.queue.submit([enc.finish()])
        device.queue.read_buffer(dst_buf, 0, 4)  # sync implícito (0.32 quebra no callback)

    dispatch()  # warmup
    reps = 20
    t0 = time.perf_counter()
    for _ in range(reps):
        dispatch()
    gpu_ms = (time.perf_counter() - t0) / reps * 1000

    # CPU equivalente (inclui upload implícito = 0, dados já em RAM)
    t0 = time.perf_counter()
    for _ in range(reps):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(g, 150, 255, cv2.THRESH_BINARY)
    cpu_ms = (time.perf_counter() - t0) / reps * 1000
    # checagem de corretude: compara GPU vs CPU
    read_buf.map_sync(wgpu.MapMode.READ)
    raw = bytes(read_buf.read_mapped())
    read_buf.unmap()
    arr32 = np.frombuffer(raw, dtype=np.uint32)
    gpu_out = ((arr32 & 255).astype(np.uint8)).reshape(H, W)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, cpu_out = cv2.threshold(g, 150, 255, cv2.THRESH_BINARY)
    match = bool((gpu_out == cpu_out).all())
    agree = float((gpu_out == cpu_out).mean())
    print(f"GPU(WebGPU): {gpu_ms:.2f} ms/frame | CPU(OpenCV): {cpu_ms:.2f} ms/frame | iguais: {match} (agree {agree * 100:.2f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
