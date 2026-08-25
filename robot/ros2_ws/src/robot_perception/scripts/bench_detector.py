#!/usr/bin/env python3
"""Phase 4 step 0: measure the detector on the ACTUAL mini PC before building.

The Dell OptiPlex 3050 Micro has an i3-7100T: 2 cores / 4 threads, 35 W, no
discrete GPU.  Nav2 already lives on those threads.  Whether Phase 4 is even
possible is a measurement, not an opinion -- and the answer decides the design,
so it comes first.

Two things this answers:

  1. How many milliseconds does one detection cost, at the resolution and
     precision you actually plan to ship?
  2. Does the HD Graphics 630 iGPU work at all?  It is Gen9.5 and the OpenVINO
     GPU plugin is unreliable on that generation.  If it works, it is free
     headroom that leaves the CPU to Nav2.  If it does not, you use CPU and
     lower the frame rate.  Either way you find out in one minute instead of
     after a week of integration.

Export the model on your LAPTOP (needs ultralytics + torch, which never have
to touch the robot):

    pip install ultralytics
    yolo export model=yolo26n.pt format=openvino imgsz=320 int8=True
    # -> yolo26n_int8_openvino_model/yolo26n.xml  (+ .bin)

Copy that folder to the mini PC, then here:

    pip3 install "openvino>=2024.0"
    python3 bench_detector.py yolo26n_int8_openvino_model/yolo26n.xml

Run it TWICE: once on an idle machine, once with the Phase 3 navigation stack
running.  The second number is the real one.
"""

import argparse
import statistics
import sys
import time

import numpy as np


def bench(xml_path, device, imgsz, threads, iters, warmup):
    import openvino as ov

    core = ov.Core()
    if device not in core.available_devices:
        return None, f'device "{device}" not available (co: {core.available_devices})'

    cfg = {'PERFORMANCE_HINT': 'LATENCY'}
    if device == 'CPU' and threads:
        # A detector that eats every thread starves nav2_controller and the
        # control loop starts missing its 10 Hz deadline.  Pin it.
        cfg['INFERENCE_NUM_THREADS'] = threads

    try:
        model = core.read_model(xml_path)
        compiled = core.compile_model(model, device, cfg)
    except Exception as exc:  # noqa: BLE001
        return None, f'{type(exc).__name__}: {exc}'

    inp = compiled.input(0)
    shape = list(inp.shape)
    # Ultralytics exports NCHW with a dynamic batch; pin what we cannot infer.
    for i, d in enumerate(shape):
        if d in (-1, 0) or str(d) == '?':
            shape[i] = 1 if i == 0 else imgsz
    blob = np.random.rand(*shape).astype(np.float32)

    req = compiled.create_infer_request()
    for _ in range(warmup):
        req.infer({0: blob})

    times = []
    for _ in range(iters):
        t0 = time.perf_counter()
        req.infer({0: blob})
        times.append((time.perf_counter() - t0) * 1000.0)

    out_shapes = [tuple(o.shape) for o in compiled.outputs]
    return {
        'p50': statistics.median(times),
        'p95': sorted(times)[int(0.95 * len(times)) - 1],
        'mean': statistics.fmean(times),
        'in_shape': tuple(shape),
        'out_shapes': out_shapes,
    }, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml', help='Path to the exported OpenVINO .xml')
    ap.add_argument('--imgsz', type=int, default=320)
    ap.add_argument('--threads', type=int, default=2,
                    help='CPU threads for inference. Leave 1-2 free for Nav2.')
    ap.add_argument('--iters', type=int, default=100)
    ap.add_argument('--warmup', type=int, default=10)
    ap.add_argument('--target-hz', type=float, default=5.0,
                    help='Detection rate Phase 4 plans to run at.')
    args = ap.parse_args()

    print(f'model   : {args.xml}')
    print(f'imgsz   : {args.imgsz}   threads(CPU): {args.threads}   iters: {args.iters}')
    print('-' * 62)

    results = {}
    for dev in ('CPU', 'GPU'):
        r, err = bench(args.xml, dev, args.imgsz, args.threads, args.iters, args.warmup)
        if err:
            print(f'{dev:<4} : KHONG CHAY DUOC -- {err}')
            if dev == 'GPU':
                print('       (HD 630 la Gen9.5; OpenVINO GPU plugin hay hong tren doi nay.')
                print('        Khong sao -- dung CPU, day chinh la ly do phai do truoc.)')
            continue
        results[dev] = r
        print(f'{dev:<4} : p50 {r["p50"]:6.1f} ms | p95 {r["p95"]:6.1f} ms | '
              f'{1000.0/r["p50"]:5.1f} FPS toi da')

    if not results:
        print('\nKhong device nao chay duoc. Kiem tra lai duong dan .xml va '
              'pip3 install openvino.')
        return 1

    best_dev = min(results, key=lambda d: results[d]['p50'])
    best = results[best_dev]
    budget_ms = 1000.0 / args.target_hz
    load = 100.0 * best['p50'] / budget_ms

    print('-' * 62)
    print(f'input  : {best["in_shape"]}')
    print(f'output : {best["out_shapes"]}')
    print(f'   (1, N, 6) = model NMS-free (YOLO26) -> parser don gian')
    print(f'   (1, 84, N) = con phai chay NMS tren CPU -> cong them vai ms')
    print()
    print(f'Chay o {args.target_hz:.0f} Hz tren {best_dev}: '
          f'{best["p50"]:.1f} / {budget_ms:.0f} ms = {load:.0f}% ngan sach mot chu ky')
    if load < 40:
        print('  => THOAI MAI. Co the tang len 10 Hz hoac dung model to hon.')
    elif load < 75:
        print('  => VUA DU. Giu 5 Hz, dung tang do phan giai.')
    else:
        print('  => QUA NANG. Ha imgsz xuong 256, hoac doi sang model')
        print('     person-detection-0202 cua Intel Open Model Zoo (nhe hon nhieu),')
        print('     hoac ha target xuong 2-3 Hz.')
    print()
    print('Bay gio chay lai LAN NUA trong khi navigation.launch.py dang chay.')
    print('Con so do moi la con so that.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
