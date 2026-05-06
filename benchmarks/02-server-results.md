# 02 — llama-server Load Test Results

Server: local OpenAI-compatible llama.cpp server on `http://localhost:8080`, CPU wheel, `n_threads=12`, `n_gpu_layers=0`, model `qwen2.5-1.5b-instruct-q4_k_m.gguf`.

| Concurrency | Total RPS | TTFB/E2E P50 (ms) | E2E P95 (ms) | E2E P99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|
| 10 | 0.23 | 27000 | 42000 | 42000 | 0 |
| 50 | 0.22 | 15000 | 38000 | 38000 | 0 |

Metrics artifacts:

- `benchmarks/02-server-metrics-u10.csv`: peak `llamacpp:kv_cache_usage_ratio = 0.2109`
- `benchmarks/02-server-metrics-u50.csv`: peak `llamacpp:kv_cache_usage_ratio = 0.0459`

Observation: the CPU wheel serves requests correctly but queues heavily under concurrency. The useful takeaway is not raw speed; it is that increasing users mostly increases waiting time while the single local decode path remains the bottleneck.
