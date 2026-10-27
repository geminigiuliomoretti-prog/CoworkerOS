import asyncio
import os
import sys
import time
import json
import httpx
import psutil
import subprocess
from pathlib import Path

backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

server_bin = r"C:\Users\costa\ai_local\bin\llama-server.exe"
model_path = r"C:\Users\costa\ai_local\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf"
url = "http://127.0.0.1:8080/v1/chat/completions"

test_prompt = "Spiega brevemente la differenza tra memoria RAM e memoria disco usando una metafora da ufficio."

def get_power_info():
    b = psutil.sensors_battery()
    return {
        "power_source": "AC" if (b is None or b.power_plugged) else "BATTERY",
        "battery_pct": b.percent if b else None,
        "ram_avail_gb": round(psutil.virtual_memory().available / (1024**3), 2)
    }

async def benchmark_single_config(t, tb, prio, b_size=2048, ub_size=512):
    power = get_power_info()
    cmd = [
        server_bin,
        "-m", model_path,
        "-c", "4096",
        "-t", str(t),
        "-tb", str(tb),
        "-b", str(b_size),
        "-ub", str(ub_size),
        "-np", "1",
        "--prio", str(prio),
        "--reasoning", "off",
        "--reasoning-budget", "0",
        "--slot-prompt-similarity", "0.10",
        "--host", "127.0.0.1",
        "--port", "8080"
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
    
    # Wait for ready
    t_start = time.time()
    ready = False
    for _ in range(40):
        await asyncio.sleep(0.5)
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                r = await client.get("http://127.0.0.1:8080/health")
                if r.status_code == 200:
                    ready = True
                    break
        except Exception:
            pass
            
    load_time = round(time.time() - t_start, 2)
    if not ready:
        proc.kill()
        return None

    # Esegui 2 iterazioni (1 cold, 1 warm cache)
    runs = []
    messages = [
        {"role": "system", "content": "Sei un assistente utile."},
        {"role": "user", "content": test_prompt}
    ]

    for it in range(1, 3):
        t0 = time.time()
        cpu_before = psutil.cpu_percent(interval=None)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json={
                    "messages": messages,
                    "max_tokens": 80,
                    "temperature": 0.2,
                    "stream": False
                })
                lat = round(time.time() - t0, 2)
                cpu_after = psutil.cpu_percent(interval=0.2)
                data = resp.json()
                timings = data.get("timings", {})
                usage = data.get("usage", {})
                runs.append({
                    "iteration": it,
                    "latency_s": lat,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "prompt_tok_s": round(timings.get("prompt_per_second", 0), 2),
                    "pred_tok_s": round(timings.get("predicted_per_second", 0), 2),
                    "ttft_s": round(timings.get("prompt_ms", 0) / 1000.0, 2),
                    "cache_n": timings.get("cache_n", 0),
                    "cpu_pct": cpu_after
                })
        except Exception as e:
            print(f"Error in run {it}: {e}")

    proc.terminate()
    proc.wait()
    await asyncio.sleep(1)

    return {
        "threads": t,
        "batch_threads": tb,
        "prio": prio,
        "load_time_s": load_time,
        "power": power,
        "runs": runs
    }

async def main():
    print("===============================================================", flush=True)
    print("FASE 4: BENCHMARK CONFIGURAZIONI RUNTIME LLAMA.CPP", flush=True)
    print("===============================================================", flush=True)

    configs = [
        # (threads, batch_threads, prio)
        (4, 6, 0),
        (4, 6, 2),
        (6, 6, 0),
        (6, 8, 2),
        (8, 8, 0),
        (8, 8, 2),
    ]

    results = []
    for t, tb, prio in configs:
        print(f"\nTestando config: t={t}, tb={tb}, prio={prio}...", flush=True)
        res = await benchmark_single_config(t, tb, prio)
        if res:
            results.append(res)
            r1 = res["runs"][0] if len(res["runs"]) > 0 else {}
            r2 = res["runs"][1] if len(res["runs"]) > 1 else {}
            print(f"  Load: {res['load_time_s']}s | Cold: {r1.get('latency_s')}s (Gen: {r1.get('pred_tok_s')} t/s, TTFT: {r1.get('ttft_s')}s, Prompt: {r1.get('prompt_tok_s')} t/s)")
            print(f"  Warm: {r2.get('latency_s')}s (Gen: {r2.get('pred_tok_s')} t/s, TTFT: {r2.get('ttft_s')}s, Cache: {r2.get('cache_n')} tokens)")

    out_file = Path(backend_dir) / "llama_config_benchmarks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nRisultati salvati in {out_file}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
