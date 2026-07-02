#!/usr/bin/env python3
"""GPU Dashboard for TrueL1 AI Server - RTX 8000 real-time monitoring."""

import http.server
import socketserver
import subprocess
import json
import os
import time
import threading
from urllib.parse import urlparse

PORT = 3001
HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


def gpu_stats():
    """Query nvidia-smi for GPU state."""
    try:
        q = "temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,power.limit,fan.speed,clocks.current.graphics,clocks.max.graphics"
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        v = [x.strip() for x in r.stdout.strip().split(",")]
        return {
            "temperature": float(v[0]),
            "utilization": float(v[1]),
            "memory_used": float(v[2]),
            "memory_total": float(v[3]),
            "power_draw": float(v[4]),
            "power_limit": float(v[5]),
            "fan_speed": float(v[6]) if v[6] not in ("[N/A]", "N/A") else 0,
            "clock_current": float(v[7]),
            "clock_max": float(v[8]),
        }
    except Exception as e:
        return {"error": str(e)}


def throttle_status():
    """Check if GPU is thermal or power throttling."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "-q", "-d", "PERFORMANCE"],
            capture_output=True, text=True, timeout=5
        )
        out = r.stdout
        return {
            "thermal_slowdown": "HW Thermal Slowdown              : Active" in out,
            "power_slowdown": "HW Power Brake Slowdown          : Active" in out,
            "sw_thermal": "SW Thermal Slowdown              : Active" in out,
        }
    except Exception:
        return {}


def ollama_models():
    """Get currently loaded models from Ollama API."""
    try:
        r = subprocess.run(
            ["curl", "-s", "http://127.0.0.1:11434/api/ps"],
            capture_output=True, text=True, timeout=3
        )
        data = json.loads(r.stdout)
        return data.get("models", [])
    except Exception:
        return []


def health_verdict(m):
    """Overall health assessment."""
    if "error" in m:
        return {"status": "error", "message": "GPU not detected"}
    if m["temperature"] >= 88:
        return {"status": "critical", "message": "CRITICAL: GPU too hot - stop workload NOW"}
    if m["temperature"] >= 83:
        return {"status": "warning", "message": "HOT: Reduce load or improve cooling"}
    if m["power_draw"] >= m["power_limit"] * 0.98:
        return {"status": "warning", "message": "Power near limit"}
    if m["temperature"] >= 75:
        return {"status": "busy", "message": "Working hard but safe"}
    if m["utilization"] > 50:
        return {"status": "busy", "message": "In use - running well"}
    return {"status": "healthy", "message": "Ready - can push more"}



# --- 2-second metrics cache: nvidia-smi/ollama are slow (~3.6s/call), so build
# the payload at most once every CACHE_TTL seconds and serve it to all pollers.
CACHE_TTL = 2.0
_cache = {"data": None, "ts": 0.0}
_lock = threading.Lock()


def cached_metrics():
    now = time.time()
    with _lock:
        if _cache["data"] is not None and (now - _cache["ts"]) < CACHE_TTL:
            return _cache["data"]
    m = gpu_stats()
    data = {
        "metrics": m,
        "throttle": throttle_status(),
        "models": ollama_models(),
        "verdict": health_verdict(m),
    }
    with _lock:
        _cache["data"] = data
        _cache["ts"] = time.time()
    return data


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/gpu":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(HTML_PATH, "rb") as f:
                self.wfile.write(f.read())
        elif path == "/api/metrics":
            data = cached_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, f, *a):
        pass


if __name__ == "__main__":
    with socketserver.ThreadingTCPServer(("0.0.0.0", PORT), Handler) as httpd:
        print(f"GPU Dashboard on http://0.0.0.0:{PORT}/gpu")
        httpd.serve_forever()
