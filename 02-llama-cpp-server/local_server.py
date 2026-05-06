#!/usr/bin/env python3
"""Minimal OpenAI-compatible llama.cpp server with Prometheus-style metrics.

This fills the lab's required serving surface on Windows where
`python -m llama_cpp.server` does not expose llama.cpp's native `--metrics`.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from llama_cpp import Llama


def load_active_model() -> str:
    return json.loads(Path("models/active.json").read_text())["primary_model"]


def load_threads() -> int:
    hw_path = Path("hardware.json")
    if not hw_path.exists():
        return 4
    hw = json.loads(hw_path.read_text())
    return int(hw.get("cpu", {}).get("cores_physical") or 4)


def render_prompt(messages: list[dict[str, str]]) -> str:
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role}: {content}")
    parts.append("assistant:")
    return "\n".join(parts)


class Metrics:
    def __init__(self, n_ctx: int) -> None:
        self.n_ctx = n_ctx
        self.lock = threading.Lock()
        self.tokens_predicted_total = 0
        self.prompt_tokens_total = 0
        self.n_decode_total = 0
        self.requests_processing = 0
        self.requests_deferred = 0
        self.kv_cache_tokens = 0

    def begin(self) -> None:
        with self.lock:
            if self.requests_processing:
                self.requests_deferred += 1
            self.requests_processing += 1

    def end(self, prompt_tokens: int, predicted_tokens: int) -> None:
        with self.lock:
            self.requests_processing = max(0, self.requests_processing - 1)
            self.prompt_tokens_total += prompt_tokens
            self.tokens_predicted_total += predicted_tokens
            self.n_decode_total += 1
            self.kv_cache_tokens = min(self.n_ctx, prompt_tokens + predicted_tokens)

    def text(self) -> str:
        with self.lock:
            kv_ratio = self.kv_cache_tokens / max(self.n_ctx, 1)
            return "\n".join(
                [
                    "# HELP llamacpp:tokens_predicted_total Total predicted tokens.",
                    "# TYPE llamacpp:tokens_predicted_total counter",
                    f"llamacpp:tokens_predicted_total {self.tokens_predicted_total}",
                    "# HELP llamacpp:prompt_tokens_total Total prompt tokens.",
                    "# TYPE llamacpp:prompt_tokens_total counter",
                    f"llamacpp:prompt_tokens_total {self.prompt_tokens_total}",
                    "# HELP llamacpp:n_decode_total Total decode calls.",
                    "# TYPE llamacpp:n_decode_total counter",
                    f"llamacpp:n_decode_total {self.n_decode_total}",
                    "# HELP llamacpp:requests_processing Requests currently processing.",
                    "# TYPE llamacpp:requests_processing gauge",
                    f"llamacpp:requests_processing {self.requests_processing}",
                    "# HELP llamacpp:requests_deferred Requests queued behind another decode.",
                    "# TYPE llamacpp:requests_deferred counter",
                    f"llamacpp:requests_deferred {self.requests_deferred}",
                    "# HELP llamacpp:kv_cache_tokens Approximate active KV cache tokens.",
                    "# TYPE llamacpp:kv_cache_tokens gauge",
                    f"llamacpp:kv_cache_tokens {self.kv_cache_tokens}",
                    "# HELP llamacpp:kv_cache_usage_ratio Approximate KV cache usage ratio.",
                    "# TYPE llamacpp:kv_cache_usage_ratio gauge",
                    f"llamacpp:kv_cache_usage_ratio {kv_ratio:.4f}",
                    "",
                ]
            )


def create_app(model_path: str, n_threads: int, n_ctx: int, n_gpu_layers: int) -> FastAPI:
    app = FastAPI(title="Day20 local llama.cpp server")
    llm = Llama(
        model_path=model_path,
        n_threads=n_threads,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )
    decode_lock = threading.Lock()
    metrics = Metrics(n_ctx=n_ctx)

    @app.get("/v1/models")
    def models() -> dict[str, Any]:
        return {"object": "list", "data": [{"id": "local", "object": "model"}]}

    @app.post("/v1/chat/completions")
    def chat(payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="messages must be a list")

        prompt = render_prompt(messages)
        max_tokens = int(payload.get("max_tokens", 128))
        temperature = float(payload.get("temperature", 0.3))
        prompt_tokens = len(llm.tokenize(prompt.encode("utf-8"), add_bos=True))

        metrics.begin()
        try:
            with decode_lock:
                result = llm.create_completion(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )
        finally:
            pass

        text = result["choices"][0]["text"]
        predicted = len(llm.tokenize(text.encode("utf-8"), add_bos=False))
        metrics.end(prompt_tokens, predicted)
        now = int(time.time())
        return {
            "id": f"chatcmpl-local-{now}",
            "object": "chat.completion",
            "created": now,
            "model": payload.get("model", "local"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": predicted,
                "total_tokens": prompt_tokens + predicted,
            },
        }

    @app.get("/metrics", response_class=PlainTextResponse)
    def prometheus_metrics() -> str:
        return metrics.text()

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=load_active_model())
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--n_threads", type=int, default=load_threads())
    parser.add_argument("--n_gpu_layers", type=int, default=0)
    parser.add_argument("--n_ctx", type=int, default=2048)
    args = parser.parse_args()

    print("==> Starting Day20 local llama.cpp server")
    print(f"    model     : {args.model}")
    print(f"    threads   : {args.n_threads}")
    print(f"    gpu_layers: {args.n_gpu_layers}")
    print(f"    ctx       : {args.n_ctx}")
    print(f"    listening : http://{args.host}:{args.port}")
    app = create_app(args.model, args.n_threads, args.n_ctx, args.n_gpu_layers)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
