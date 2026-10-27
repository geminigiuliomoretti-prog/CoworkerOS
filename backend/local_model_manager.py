import os
import sys
import time
import json
import atexit
import psutil
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable, Awaitable
import httpx

LLAMA_SERVER_BIN = Path(r"C:\Users\costa\ai_local\bin\llama-server.exe")
MODEL_PATH = Path(r"C:\Users\costa\ai_local\models\Qwen_Qwen3.5-4B-Q4_K_M.gguf")
MMPROJ_PATH = Path(r"C:\Users\costa\ai_local\models\mmproj-Qwen_Qwen3.5-4B-f16.gguf")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

# Soglia minima di sicurezza RAM libera per avvio a freddo (GB)
MIN_RAM_FREE_GB = 3.2


def get_system_power_info() -> Dict[str, Any]:
    """Rileva lo stato di alimentazione (AC collegato vs Batteria) e percentuale residua."""
    try:
        b = psutil.sensors_battery()
        return {
            "power_source": "AC" if (b is None or b.power_plugged) else "BATTERY",
            "battery_pct": b.percent if b else None,
            "is_plugged": b.power_plugged if b else True,
        }
    except Exception:
        return {"power_source": "UNKNOWN", "battery_pct": None, "is_plugged": True}


def get_system_ram_info() -> Dict[str, float]:
    """Rileva la memoria RAM totale, disponibile e usata in GB."""
    v = psutil.virtual_memory()
    return {
        "total_gb": round(v.total / (1024**3), 2),
        "available_gb": round(v.available / (1024**3), 2),
        "used_gb": round(v.used / (1024**3), 2),
        "percent": round(v.percent, 1),
    }


class LocalModelManager:
    """
    Gestore del ciclo di vita e dell'inferenza di llama-server per Qwen3.5-4B.
    Garantisce:
    - Controllo RAM prima del caricamento (prevenzione thrashing)
    - Prevenzione istanze duplicate
    - Client httpx asincrono riutilizzabile (pool di connessioni efficiente)
    - Distinzione tra attesa in coda / avvio modello e tempo di generazione
    - Conservazione stderr per diagnostica
    - Lock dedicato solo all'inferenza (non blocca endpoint REST)
    - Arresto pulito alla chiusura dell'app (atexit e shutdown)
    """

    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen] = None
        self.is_vision_enabled: bool = False
        self._inference_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._status: str = "stopped"  # stopped, starting, running, error, low_ram
        self._last_error: str = ""
        self._last_stderr: str = ""
        self._pid: Optional[int] = None
        self._client: Optional[httpx.AsyncClient] = None
        self.inference_metrics_log: List[Dict[str, Any]] = []
        atexit.register(self.stop_server_sync)

    def _get_client(self, timeout: float = 180.0) -> httpx.AsyncClient:
        """Restituisce un client HTTP asincrono riutilizzabile."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10, keepalive_expiry=60.0)
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._client

    async def close_client(self) -> None:
        """Chiude il client HTTP asincrono in modo pulito."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def is_server_healthy(self, timeout: float = 0.5) -> bool:
        """Verifica se l'endpoint /health di llama-server risponde 200 OK."""
        if self.process is None or self.process.poll() is not None:
            return False
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(f"{BASE_URL}/health")
                return r.status_code == 200
        except Exception:
            return False

    async def is_server_healthy_async(self, timeout: float = 0.5) -> bool:
        """Verifica asincrona se l'endpoint /health risponde 200 OK."""
        if self.process is None or self.process.poll() is not None:
            return False
        try:
            client = self._get_client(timeout=timeout)
            r = await client.get(f"{BASE_URL}/health")
            return r.status_code == 200
        except Exception:
            return False

    def start_server_sync(self, enable_vision: bool = False) -> Dict[str, Any]:
        """Avvio sincrono di llama-server con controlli preventivi di sicurezza."""
        if self.is_server_healthy():
            self._status = "running"
            return {
                "success": True,
                "message": "llama-server è già attivo e pronto.",
                "status": "running",
                "vision": self.is_vision_enabled,
            }

        # 1. Verifica esistenza binario ed eseguibile
        if not LLAMA_SERVER_BIN.exists():
            err = f"Eseguibile llama-server non trovato in: {LLAMA_SERVER_BIN}"
            self._status = "error"
            self._last_error = err
            return {"success": False, "error": err, "status": "error"}

        if not MODEL_PATH.exists():
            err = f"File modello Qwen3.5-4B non trovato in: {MODEL_PATH}"
            self._status = "error"
            self._last_error = err
            return {"success": False, "error": err, "status": "error"}

        # 2. Controllo RAM disponibile prima dell'avvio
        ram_info = get_system_ram_info()
        if ram_info["available_gb"] < MIN_RAM_FREE_GB:
            err = (
                f"RAM disponibile insufficiente ({ram_info['available_gb']} GB liberi). "
                f"Per caricare Qwen3.5-4B in sicurezza sono necessari almeno {MIN_RAM_FREE_GB} GB di RAM libera. "
                "Chiudi Google Chrome o altre applicazioni superflue per liberare memoria prima di avviare il modello."
            )
            self._status = "low_ram"
            self._last_error = err
            return {
                "success": False,
                "error": err,
                "status": "low_ram",
                "ram_info": ram_info,
            }

        # 3. Costruzione comando per llama-server
        cmd = [
            str(LLAMA_SERVER_BIN),
            "-m", str(MODEL_PATH),
            "-c", "4096",
            "-t", "6",
            "-tb", "8",
            "-np", "1",
            "--prio", "2",
            "--reasoning", "off",
            "--reasoning-budget", "0",
            "--slot-prompt-similarity", "0.10",
            "--host", SERVER_HOST,
            "--port", str(SERVER_PORT),
        ]

        if enable_vision and MMPROJ_PATH.exists():
            cmd.extend(["--mmproj", str(MMPROJ_PATH)])
            self.is_vision_enabled = True
        else:
            self.is_vision_enabled = False

        self._status = "starting"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self._pid = self.process.pid

            # Attesa attiva fino a 35 secondi che il server risponda su /health
            t0 = time.time()
            while time.time() - t0 < 35.0:
                if self.process.poll() is not None:
                    # Il processo è uscito prematuramente: cattura stderr diagnostico
                    stderr_out = ""
                    try:
                        stderr_out = self.process.stderr.read() if self.process.stderr else ""
                    except Exception:
                        pass
                    self._last_stderr = stderr_out
                    self._status = "error"
                    self._last_error = f"llama-server terminato (code {self.process.returncode}). Stderr: {stderr_out[:300]}"
                    return {"success": False, "error": self._last_error, "status": "error"}

                if self.is_server_healthy(timeout=0.6):
                    self._status = "running"
                    self._last_error = ""
                    return {
                        "success": True,
                        "message": f"Qwen3.5-4B avviato con successo in {round(time.time() - t0, 1)}s.",
                        "status": "running",
                        "vision": self.is_vision_enabled,
                        "pid": self._pid,
                    }
                time.sleep(0.5)

            # Timeout
            self._status = "error"
            self._last_error = "Timeout durante l'avvio di llama-server (35 secondi superati)."
            self.stop_server_sync()
            return {"success": False, "error": self._last_error, "status": "error"}

        except Exception as e:
            self._status = "error"
            self._last_error = f"Errore durante l'avvio del processo: {e}"
            return {"success": False, "error": self._last_error, "status": "error"}

    async def start_server_async(self, enable_vision: bool = False) -> Dict[str, Any]:
        """Avvio asincrono protetto da lock preventivo contro avvii concorrenti."""
        async with self._start_lock:
            if await self.is_server_healthy_async():
                self._status = "running"
                return {"success": True, "status": "running", "message": "Server già attivo."}
            return await asyncio.to_thread(self.start_server_sync, enable_vision)

    def stop_server_sync(self) -> Dict[str, Any]:
        """Arresto controllato di llama-server."""
        stopped_pid = None
        try:
            if self.process and self.process.poll() is None:
                stopped_pid = self.process.pid
                self.process.terminate()
                try:
                    self.process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process = None
            self._pid = None

            # Pulizia preventiva di eventuali processi residui di llama-server
            for p in psutil.process_iter(["name", "pid"]):
                try:
                    if "llama-server" in (p.info["name"] or "").lower():
                        p.terminate()
                        p.wait(timeout=3.0)
                except Exception:
                    pass

            self._status = "stopped"
            self.is_vision_enabled = False
            return {
                "success": True,
                "message": "llama-server arrestato correttamente.",
                "status": "stopped",
                "stopped_pid": stopped_pid,
            }
        except Exception as e:
            self._status = "error"
            self._last_error = f"Errore durante l'arresto: {e}"
            return {"success": False, "error": self._last_error, "status": "error"}

    async def stop_server_async(self) -> Dict[str, Any]:
        """Arresto asincrono di llama-server e chiusura client HTTP."""
        await self.close_client()
        return await asyncio.to_thread(self.stop_server_sync)

    def get_status(self) -> Dict[str, Any]:
        """Restituisce lo stato dettagliato del runtime locale, RAM e modello."""
        alive = self.is_server_healthy()
        if alive:
            self._status = "running"
        elif self._status == "running":
            self._status = "stopped"

        ram_info = get_system_ram_info()
        server_rss_mb = 0.0

        if self._pid and alive:
            try:
                proc = psutil.Process(self._pid)
                server_rss_mb = round(proc.memory_info().rss / (1024**2), 1)
            except Exception:
                pass

        return {
            "status": self._status,
            "is_alive": alive,
            "pid": self._pid,
            "server_rss_mb": server_rss_mb,
            "vision_enabled": self.is_vision_enabled,
            "ram_info": ram_info,
            "power_info": get_system_power_info(),
            "min_ram_required_gb": MIN_RAM_FREE_GB,
            "endpoint": BASE_URL,
            "last_error": self._last_error,
        }

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
        timeout: float = 180.0,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Esegue una richiesta di completamento chat verso llama-server.
        Supporta sia output completo che streaming progressivo dei token (on_chunk).
        Usa _inference_lock per garantire che venga eseguita UNA sola inferenza alla volta.
        Registra metriche complete senza memorizzare prompt o credenziali.
        """
        req_id = f"qwen_{int(time.time()*1000)}"
        t_enqueue = time.time()
        model_start_ms = 0.0

        async with self._inference_lock:
            queue_wait_ms = round((time.time() - t_enqueue) * 1000, 1)

            # 1. Verifica che il server sia attivo, altrimenti tenta l'avvio controllato
            if not await self.is_server_healthy_async():
                t_start_model = time.time()
                start_res = await self.start_server_async()
                model_start_ms = round((time.time() - t_start_model) * 1000, 1)
                if not start_res["success"]:
                    return {
                        "success": False,
                        "error": start_res.get("error", "Impossibile avviare llama-server locale."),
                        "status": start_res.get("status", "error"),
                        "queue_wait_ms": queue_wait_ms,
                        "model_start_ms": model_start_ms,
                    }

            is_stream = on_chunk is not None
            payload: Dict[str, Any] = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": is_stream,
            }
            if is_stream:
                payload["stream_options"] = {"include_usage": True}
            if tools:
                payload["tools"] = tools

            url = f"{BASE_URL}/v1/chat/completions"
            client = self._get_client(timeout=timeout)
            t_gen_start = time.time()
            first_token_time: Optional[float] = None

            try:
                if is_stream:
                    async with client.stream("POST", url, json=payload) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            return {
                                "success": False,
                                "error": f"llama-server ha risposto con codice HTTP {resp.status_code}: {body.decode(errors='replace')}",
                                "status": "error",
                                "duration_s": round(time.time() - t_gen_start, 2),
                            }

                        accumulated_content = []
                        tool_calls_dict: Dict[int, Dict[str, Any]] = {}
                        usage = {}
                        timings = {}

                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            if line == "data: [DONE]":
                                break
                            try:
                                item = json.loads(line[6:])
                                if "usage" in item and item["usage"]:
                                    usage = item["usage"]
                                if "timings" in item and item["timings"]:
                                    timings = item["timings"]
                                choices = item.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    chunk_text = delta.get("content", "")
                                    if chunk_text:
                                        if first_token_time is None:
                                            first_token_time = time.time()
                                        accumulated_content.append(chunk_text)
                                        if on_chunk:
                                            await on_chunk(chunk_text)
                                    # Tool calls delta
                                    tcs = delta.get("tool_calls", [])
                                    for tc in tcs:
                                        idx = tc.get("index", 0)
                                        if idx not in tool_calls_dict:
                                            tool_calls_dict[idx] = {
                                                "id": tc.get("id", ""),
                                                "type": tc.get("type", "function"),
                                                "function": {"name": "", "arguments": ""}
                                            }
                                        fn = tc.get("function", {})
                                        if fn.get("name"):
                                            tool_calls_dict[idx]["function"]["name"] += fn["name"]
                                        if fn.get("arguments"):
                                            tool_calls_dict[idx]["function"]["arguments"] += fn["arguments"]
                                        if tc.get("id"):
                                            tool_calls_dict[idx]["id"] = tc["id"]
                            except Exception:
                                pass

                        total_tool_calls = [tool_calls_dict[i] for i in sorted(tool_calls_dict.keys())]
                        final_content = "".join(accumulated_content)
                        t_now = time.time()
                        generation_ms = round((t_now - t_gen_start) * 1000, 1)
                        ttft_ms = round((first_token_time - t_gen_start) * 1000, 1) if first_token_time else generation_ms
                        total_ms = round((t_now - t_enqueue) * 1000, 1)
                        completion_tokens = usage.get("completion_tokens", len(final_content.split()))
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        tokens_per_sec = round(completion_tokens / (generation_ms / 1000), 2) if generation_ms > 0 else 0.0

                        metric_entry = {
                            "request_id": req_id,
                            "provider": "LOCAL_QWEN",
                            "queue_wait_ms": queue_wait_ms,
                            "model_start_ms": model_start_ms,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "time_to_first_token_ms": ttft_ms,
                            "generation_ms": generation_ms,
                            "total_ms": total_ms,
                            "tokens_per_second": tokens_per_sec,
                        }
                        self.inference_metrics_log.append(metric_entry)

                        return {
                            "success": True,
                            "content": final_content,
                            "tool_calls": total_tool_calls,
                            "usage": usage,
                            "timings": timings,
                            "duration_s": round(generation_ms / 1000, 2),
                            "metrics": metric_entry,
                        }
                else:
                    resp = await client.post(url, json=payload)
                    t_now = time.time()
                    generation_ms = round((t_now - t_gen_start) * 1000, 1)

                    if resp.status_code != 200:
                        return {
                            "success": False,
                            "error": f"llama-server ha risposto con codice HTTP {resp.status_code}: {resp.text}",
                            "status": "error",
                            "duration_s": round(generation_ms / 1000, 2),
                        }

                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        return {
                            "success": False,
                            "error": "Risposta vuota ricevuta da llama-server.",
                            "status": "error",
                            "duration_s": round(generation_ms / 1000, 2),
                        }

                    message = choices[0].get("message", {})
                    content = message.get("content", "") or ""
                    tool_calls = message.get("tool_calls", [])
                    usage = data.get("usage", {})
                    timings = data.get("timings", {})
                    total_ms = round((t_now - t_enqueue) * 1000, 1)
                    completion_tokens = usage.get("completion_tokens", len(content.split()))
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    tokens_per_sec = round(completion_tokens / (generation_ms / 1000), 2) if generation_ms > 0 else 0.0

                    metric_entry = {
                        "request_id": req_id,
                        "provider": "LOCAL_QWEN",
                        "queue_wait_ms": queue_wait_ms,
                        "model_start_ms": model_start_ms,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "time_to_first_token_ms": generation_ms,  # non-streaming: ttft coincide col tempo di risposta
                        "generation_ms": generation_ms,
                        "total_ms": total_ms,
                        "tokens_per_second": tokens_per_sec,
                    }
                    self.inference_metrics_log.append(metric_entry)

                    return {
                        "success": True,
                        "content": content,
                        "tool_calls": tool_calls,
                        "usage": usage,
                        "timings": timings,
                        "duration_s": round(generation_ms / 1000, 2),
                        "metrics": metric_entry,
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": f"Timeout dell'inferenza locale ({timeout}s superati).",
                    "status": "timeout",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Errore di comunicazione con llama-server: {e}",
                    "status": "error",
                }


local_model_mgr = LocalModelManager()
