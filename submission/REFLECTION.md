# Reflection — Lab 20 (Personal Report)

**Họ Tên:** Hoang Duc Hung
**Cohort:** A20
**Ngày submit:** 2026-05-06

---

## 1. Hardware spec (từ `00-setup/detect-hardware.py`)

- **OS:** Windows 10 AMD64
- **CPU:** unknown from Windows probe; detected 12 physical / 12 logical cores
- **Cores:** 12 physical / 12 logical
- **CPU extensions:** not reported by Windows probe
- **RAM:** 15.4 GB usable, laptop advertised 16 GB
- **Accelerator:** NVIDIA GeForce RTX 3050 Laptop GPU, 4096 MiB
- **llama.cpp backend đã chọn:** CPU wheel for the core run; CUDA detected but not used because the local Windows wheel was CPU-only
- **Recommended model tier:** Qwen2.5-1.5B-Instruct Q4_K_M

**Setup story** (≤ 80 chữ): Windows WMI did not report RAM correctly in the original probe, so I fixed the probe to use the Windows memory API. `llama-cpp-python` source install hit Windows long-path errors, so I installed the prebuilt CPU wheel from the llama-cpp-python wheel index.

---

## 2. Track 01 — Quickstart numbers (từ `benchmarks/01-quickstart-results.md`)

| Model | Load (ms) | TTFT P50/P95 (ms) | TPOT P50/P95 (ms) | E2E P50/P95/P99 (ms) | Decode rate (tok/s) |
|---|--:|--:|--:|--:|--:|
| qwen2.5-1.5b-instruct-q4_k_m.gguf | 1436 | 154 / 206 | 47.2 / 51.3 | 2967 / 3432 / 3439 | 21.2 |
| qwen2.5-1.5b-instruct-q2_k.gguf | 432 | 176 / 268 | 36.8 / 47.4 | 2493 / 3252 / 3261 | 27.2 |

**Một quan sát** (≤ 50 chữ): Q2_K decoded about 28% faster by TPOT, but Q4_K_M is still fast enough on CPU and should preserve better answer quality. For this laptop, Q4_K_M is the better default unless memory is very tight.

---

## 3. Track 02 — llama-server load test

| Concurrency | Total RPS | TTFB P50 (ms) | E2E P95 (ms) | E2E P99 (ms) | Failures |
|--:|--:|--:|--:|--:|--:|
| 10 | 0.23 | 27000 | 42000 | 42000 | 0 |
| 50 | 0.22 | 15000 | 38000 | 38000 | 0 |

**KV-cache observation** (từ `record-metrics.py`): peak `llamacpp:kv_cache_usage_ratio` ở concurrency 50 = `0.0459`, nghĩa là prompt/context trong load test vẫn nhỏ so với `n_ctx=2048`. Bottleneck chính là CPU decode/queueing, không phải KV-cache capacity.

---

## 4. Track 03 — Milestone integration

- **N16 (Cloud/IaC):** stub: localhost-only serving endpoint
- **N17 (Data pipeline):** stub: static in-memory document list
- **N18 (Lakehouse):** stub: in-memory records instead of Delta/Iceberg
- **N19 (Vector + Feature Store):** stub: toy keyword retrieval over `TOY_DOCS`

**Nơi tốn nhiều ms nhất** trong pipeline (đo bằng `time.perf_counter` trong `pipeline.py`):

- embed: 0.0 ms, no embedding model in the stub path
- retrieve: 0.0–0.1 ms
- llama-server: 5194.2–10561.1 ms

**Reflection** (≤ 60 chữ): Bottleneck nằm hoàn toàn ở llama-server call. Retrieval gần như miễn phí vì chỉ là keyword overlap trong memory. Điều này khớp kỳ vọng: với local CPU wheel, decode latency dominates; một vector store thật sẽ chỉ đáng kể nếu remote/network hoặc embedding model chậm.

---

## 5. Bonus — The single change that mattered most

**Change:** Dùng CPU-safe serving path với custom FastAPI wrapper có `/metrics`, thay vì cố chạy `python -m llama_cpp.server --metrics` trên wheel Windows không hỗ trợ flag này.

**Before vs after**:

```text
before: llama_cpp.server exited with "unrecognized arguments: --metrics"; no /metrics evidence
after:  smoke test passed; /metrics showed llamacpp:tokens_predicted_total 23 and kv_cache_usage_ratio 0.0229
speedup: not a throughput speedup; it changed the setup from ungradable to measurable
```

**Tại sao nó work**:

The grading bottleneck was observability, not raw model speed. The installed Windows CPU wheel could generate text, but the server entrypoint did not expose the native llama.cpp metrics flag required by the rubric. Wrapping the same `Llama` object behind FastAPI kept the OpenAI-compatible `/v1/chat/completions` shape while adding Prometheus-style counters with the exact metric names used by the lab scripts.

This also made the system honest about the hardware path. CUDA was detected, but the installed wheel was CPU-only, so forcing `LAB_N_GPU_LAYERS=0` avoided fake GPU offload and produced reproducible CPU numbers. The load test then showed the real limitation: requests queue behind decode, so P95 grows even though KV-cache usage remains low.

---

## 6. (Optional) Điều ngạc nhiên nhất

The advertised 16 GB laptop appeared as 15.4 GB usable RAM, which changed the auto-selected model tier from the 3B row to the safer 1.5B row. That was a good reminder to tune from measured available resources, not marketing specs.

---

## 7. Self-graded checklist

- [x] `hardware.json` đã commit
- [x] `models/active.json` đã commit
- [x] `benchmarks/01-quickstart-results.md` đã commit
- [x] `benchmarks/02-server-results.md` (hoặc CSV từ `record-metrics.py`) đã commit
- [ ] `benchmarks/bonus-*.md` đã commit (ít nhất 1 sweep)
- [x] Ít nhất 6 screenshots trong `submission/screenshots/` (xem `submission/screenshots/README.md`)
- [x] `make verify` exit 0 (chạy ngay trước khi push)
- [ ] Repo trên GitHub ở chế độ **public**
- [ ] Đã paste public repo URL vào VinUni LMS

---

**Quan trọng:** repo phải **public** đến khi điểm được công bố. Nếu private, grader không xem được → 0 điểm.
