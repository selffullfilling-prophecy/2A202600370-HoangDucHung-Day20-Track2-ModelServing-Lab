# 01 — Quickstart Results

Settings: `n_threads=12`, `n_ctx=2048`, `n_batch=512`, `n_gpu_layers=0`.

| Model | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode rate (tok/s) |
|---|---:|---:|---:|---:|---:|
| qwen2.5-1.5b-instruct-q4_k_m.gguf | 1436 | 154 / 206 | 47.2 / 51.3 | 2967 / 3432 / 3439 | 21.2 |
| qwen2.5-1.5b-instruct-q2_k.gguf | 432 | 176 / 268 | 36.8 / 47.4 | 2493 / 3252 / 3261 | 27.2 |

## Observations

- Q2_K decoded faster on this CPU run: TPOT P50 was 36.8 ms versus 47.2 ms for Q4_K_M.
- Q4_K_M remains the better default for this laptop because it is still usable at 21.2 tok/s and should preserve better answer quality.
- The run used the CPU wheel with `n_gpu_layers=0`; CUDA was detected, but not used for the core reproducibility path.
