#!/usr/bin/env python3
"""Redis import/export helpers for the Julia precompile-trace artifact cache.

The artifact is a plain Julia source file of precompile() calls produced by
Julia's --trace-compile flag.  It is stored in Redis as a gzip-compressed blob
so that a fresh pod can pull it, decompress it, and include() it before the
HTTP server starts -- pre-triggering LLVM compilation of all traced methods.

Environment variables:
  REDIS_ADDR      host:port or redis://host:port  (overrides HOST/PORT)
  REDIS_HOST      Redis hostname  (default: redis.openfaas.svc.cluster.local)
  REDIS_PORT      Redis port      (default: 6379)
  REDIS_PASSWORD  optional AUTH password
  REDIS_DB        database index  (default: 0)
  REDIS_TIMEOUT   socket timeout  (default: 8s)
  JULIA_CACHE_KEY Redis key for the trace blob  (default: julia-precompile-trace:default)
  JULIA_CACHE_MODE baseline | populate | redis   (default: baseline)
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import socket
import time
from pathlib import Path
from typing import Any


class RedisError(RuntimeError):
    pass


# ──────────────────────────────────────────────────────────────
# Minimal RESP client (same implementation as jax prototype)
# ──────────────────────────────────────────────────────────────

class RedisClient:
    def __init__(self) -> None:
        host, port = _host_port()
        self.host = host
        self.port = port
        self.password = os.getenv("REDIS_PASSWORD") or os.getenv("redis_password") or ""
        self.db = int(os.getenv("REDIS_DB") or os.getenv("redis_db") or "0")
        self.timeout = _parse_seconds(os.getenv("REDIS_TIMEOUT") or "8s")

    def command(self, *args: bytes | str | int) -> Any:
        encoded = [_encode(a) for a in args]
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            reader = sock.makefile("rb")
            if self.password:
                self._send(sock, "AUTH", self.password)
                _read_resp(reader)
            if self.db > 0:
                self._send(sock, "SELECT", str(self.db))
                _read_resp(reader)
            self._send(sock, *encoded)
            return _read_resp(reader)

    def ping(self) -> str:
        reply = self.command("PING")
        return reply.decode("utf-8", errors="replace") if isinstance(reply, bytes) else str(reply)

    def get(self, key: str) -> bytes | None:
        reply = self.command("GET", key)
        if reply is None:
            return None
        if not isinstance(reply, bytes):
            raise RedisError(f"unexpected GET reply type {type(reply).__name__}")
        return reply

    def set(self, key: str, value: bytes) -> None:
        reply = self.command("SET", key, value)
        if reply not in ("OK", b"OK"):
            raise RedisError(f"unexpected SET reply: {reply!r}")

    @staticmethod
    def _send(sock: socket.socket, *args: bytes | str | int) -> None:
        encoded = [_encode(a) for a in args]
        parts: list[bytes] = [f"*{len(encoded)}\r\n".encode("ascii")]
        for arg in encoded:
            parts.append(f"${len(arg)}\r\n".encode("ascii"))
            parts.append(arg)
            parts.append(b"\r\n")
        sock.sendall(b"".join(parts))


def _encode(arg: bytes | str | int) -> bytes:
    if isinstance(arg, bytes):
        return arg
    return str(arg).encode("utf-8")


def _read_line(reader: Any) -> bytes:
    line = reader.readline()
    if not line:
        raise RedisError("unexpected EOF from Redis")
    if not line.endswith(b"\r\n"):
        raise RedisError(f"malformed Redis line: {line!r}")
    return line[:-2]


def _read_resp(reader: Any) -> Any:
    prefix = reader.read(1)
    if not prefix:
        raise RedisError("unexpected EOF")
    if prefix == b"+":
        return _read_line(reader).decode("utf-8", errors="replace")
    if prefix == b"-":
        raise RedisError(_read_line(reader).decode("utf-8", errors="replace"))
    if prefix == b":":
        return int(_read_line(reader))
    if prefix == b"$":
        length = int(_read_line(reader))
        if length < 0:
            return None
        data = reader.read(length)
        trailer = reader.read(2)
        if len(data) != length or trailer != b"\r\n":
            raise RedisError("malformed bulk string")
        return data
    if prefix == b"*":
        count = int(_read_line(reader))
        if count < 0:
            return None
        return [_read_resp(reader) for _ in range(count)]
    raise RedisError(f"unknown RESP prefix: {prefix!r}")


def _host_port() -> tuple[str, int]:
    raw = os.getenv("REDIS_ADDR") or ""
    if not raw:
        host = os.getenv("REDIS_HOST") or os.getenv("redis_host") or "redis.openfaas.svc.cluster.local"
        port = int(os.getenv("REDIS_PORT") or os.getenv("redis_port") or "6379")
        return host, port
    if raw.startswith("redis://"):
        raw = raw.removeprefix("redis://").split("/", 1)[0]
    host, sep, raw_port = raw.rpartition(":")
    if not sep:
        return raw, 6379
    return host, int(raw_port)


def _parse_seconds(raw: str) -> float:
    v = raw.strip().lower()
    if v.endswith("ms"):
        return float(v[:-2]) / 1000.0
    if v.endswith("s"):
        return float(v[:-1])
    return float(v)


# ──────────────────────────────────────────────────────────────
# Cache key / path helpers
# ──────────────────────────────────────────────────────────────

def cache_key() -> str:
    return os.getenv("JULIA_CACHE_KEY", "julia-precompile-trace:default")


def cache_mode() -> str:
    return os.getenv("JULIA_CACHE_MODE", "baseline").lower()


def meta_path(suffix: str) -> Path:
    base = Path(os.getenv("JULIA_META_DIR", "/profiles"))
    return base / f"julia-cache-{suffix}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# Pull (import) a precompile trace from Redis
# ──────────────────────────────────────────────────────────────

def pull_trace(out_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    key = cache_key()
    mode = cache_mode()

    if mode != "redis":
        meta: dict[str, Any] = {
            "mode": mode, "redis_key": key,
            "artifact_found": False, "imported": False,
            "status": "skipped",
        }
        _write_json(meta_path("import"), meta)
        return meta

    client = RedisClient()
    blob = client.get(key)
    if blob is None:
        meta = {
            "mode": mode, "redis_key": key,
            "artifact_found": False, "imported": False,
            "artifact_bytes": 0,
            "import_ms": (time.perf_counter() - started) * 1000.0,
            "status": "missing",
        }
        _write_json(meta_path("import"), meta)
        return meta

    content = gzip.decompress(blob)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)
    meta = {
        "mode": mode, "redis_key": key,
        "artifact_found": True, "imported": True,
        "artifact_bytes": len(blob),
        "trace_bytes": len(content),
        "trace_lines": content.count(b"\n"),
        "import_ms": (time.perf_counter() - started) * 1000.0,
        "status": "ok",
    }
    _write_json(meta_path("import"), meta)
    return meta


# ──────────────────────────────────────────────────────────────
# Push (export) a precompile trace to Redis
# ──────────────────────────────────────────────────────────────

def push_trace(trace_file: Path) -> dict[str, Any]:
    started = time.perf_counter()
    key = cache_key()
    if not trace_file.exists():
        meta: dict[str, Any] = {
            "mode": cache_mode(), "redis_key": key,
            "exported": False,
            "status": "trace_file_missing",
            "trace_file": str(trace_file),
        }
        _write_json(meta_path("export"), meta)
        return meta

    # Read and filter the trace file
    content = trace_file.read_text(encoding='utf-8')
    lines = content.splitlines()

    # Filter out problematic lines that won't replay portably
    filtered_lines = []
    for line in lines:
        # Skip lines containing JLL references, ccall, or other non-portable constructs
        low = line.lower()
        if '_jll' in low or 'jllwrappers' in low or 'ccall' in low or 'openssl' in low or 'mbedtls' in low or 'libdl' in low:
            continue
        filtered_lines.append(line)

    filtered_content = '\n'.join(filtered_lines)
    content_bytes = filtered_content.encode('utf-8')
    blob = gzip.compress(content_bytes, compresslevel=6)
    RedisClient().set(key, blob)
    meta = {
        "mode": cache_mode(), "redis_key": key,
        "exported": True,
        "trace_file": str(trace_file),
        "trace_bytes": len(content_bytes),
        "trace_lines": len(filtered_lines),
        "filtered_lines": len(lines) - len(filtered_lines),
        "artifact_bytes": len(blob),
        "export_ms": (time.perf_counter() - started) * 1000.0,
        "status": "ok",
    }
    _write_json(meta_path("export"), meta)
    return meta


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────

def _cmd_pull(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else Path("/tmp/julia-precompile.jl")
    try:
        meta = pull_trace(out)
    except Exception as exc:  # noqa: BLE001
        meta = {
            "mode": cache_mode(), "redis_key": cache_key(),
            "artifact_found": False, "imported": False,
            "status": "error", "error": str(exc),
        }
        _write_json(meta_path("import"), meta)
    print(json.dumps(meta, indent=2), flush=True)
    return 0


def _cmd_push(args: argparse.Namespace) -> int:
    trace_file = Path(args.trace_file) if args.trace_file else Path(
        os.getenv("JULIA_TRACE_FILE", "/tmp/julia-trace.jl")
    )
    try:
        meta = push_trace(trace_file)
    except Exception as exc:  # noqa: BLE001
        meta = {
            "mode": cache_mode(), "redis_key": cache_key(),
            "exported": False, "status": "error", "error": str(exc),
        }
        _write_json(meta_path("export"), meta)
    print(json.dumps(meta, indent=2), flush=True)
    return 0 if meta.get("status") == "ok" else 1


def _cmd_ping(_args: argparse.Namespace) -> int:
    reply = RedisClient().ping()
    print(json.dumps({"ok": True, "reply": reply}), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Julia precompile-trace Redis cache controller")
    subs = parser.add_subparsers(dest="command", required=True)

    pull_p = subs.add_parser("pull", help="Download trace from Redis")
    pull_p.add_argument("--out", default="", help="Output path for the trace file")
    pull_p.set_defaults(func=_cmd_pull)

    push_p = subs.add_parser("push", help="Upload trace to Redis")
    push_p.add_argument("--trace-file", default="", help="Path to the --trace-compile output file")
    push_p.set_defaults(func=_cmd_push)

    ping_p = subs.add_parser("ping", help="Ping Redis")
    ping_p.set_defaults(func=_cmd_ping)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
