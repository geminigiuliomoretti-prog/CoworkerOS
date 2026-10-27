"""
COWORKEROS — SUITE DI TEST COMPARATIVI FASE 4: REATTIVITÀ E VELOCITÀ REALE
Esegue 3 iterazioni per ciascuno degli 8 scenari di test:
1. Elenco Finestre (Fast Path vs LLM)
2. Ricerca File (Fast Path vs Qwen LLM)
3. Lettura Documento (Fast Path vs Qwen LLM)
4. Conversazione in Italiano (Streaming Qwen)
5. Flusso Multi-step (Qwen Coordination)
6. Operazioni con Autorizzazione (Human-in-the-loop)
7. Streaming e Reattività (Token-by-Token)
8. Sicurezza e Regressioni (Guardrails)

Raccoglie telemetria reale: TTFT, prompt_tok_s, gen_tok_s, duration_s, RAM, AC/Batteria.
"""

import os
import sys
import time
import json
import asyncio
import statistics
from pathlib import Path
from typing import Dict, Any, List

# Output UTF-8 per console Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# ISOLAMENTO AMBIENTE DI TEST: Database separato dedicato ai test/benchmark
TEST_DB_PATH = BASE_DIR / "test_isolated.db"
os.environ["COWORKEROS_DB_PATH"] = str(TEST_DB_PATH)

import database as db
import tools_os
from agent_engine import orchestrator
from local_model_manager import local_model_mgr, get_system_ram_info, get_system_power_info
from fast_path_router import FastPathRouter


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


async def main():
    print_banner("COWORKEROS — FASE 4: TEST COMPARATIVI REATTIVITÀ E VELOCITÀ REALE")

    # 1. Info hardware ed alimentazione
    ram_init = get_system_ram_info()
    power_init = get_system_power_info()
    power_str = "Alimentazione AC (In Carica) 🔌" if power_init.get("ac_power") else f"Batteria ({power_init.get('battery_percent', 0)}%) 🔋"

    print(f"RAM Totale: {ram_init.get('total_gb')} GB | Disponibile: {ram_init.get('available_gb')} GB")
    print(f"Stato Alimentazione: {power_str}")

    # 2. Inizializzazione Orchestrator e Modalità Locale
    await orchestrator.set_provider_mode("LOCAL")

    # Avvio controllato di llama-server
    print("\n[Init] Avvio/Verifica llama-server con configurazione ottimizzata...")
    t_srv0 = time.time()
    start_res = await local_model_mgr.start_server_async()
    srv_load_time = round(time.time() - t_srv0, 2)
    print(f"[Init] llama-server attivo: {start_res['success']} (in {srv_load_time}s, PID: {start_res.get('pid')})")

    # Creazione chat di test dedicata
    test_chat = db.create_chat(title="Fase 4 Reactivity Benchmark Chat", participants=["chief", "architect", "builder"])
    chat_id = test_chat["id"]
    print(f"[Init] Chat di test creata: {chat_id}")

    results_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": "Microsoft Surface Pro 9 (Intel i5-1235U, 16 GB RAM)",
        "model": "Qwen3.5-4B Q4_K_M (llama.cpp CPU x64)",
        "power_info": power_init,
        "ram_initial": ram_init,
        "server_load_time_s": srv_load_time,
        "scenarios": {},
    }

    # -------------------------------------------------------------
    # SCENARIO 1: ELENCO FINESTRE (Fast Path vs LLM)
    # -------------------------------------------------------------
    print_banner("SCENARIO 1: ELENCO FINESTRE (Fast Path Deterministo)")
    s1_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="mostra le finestre aperte",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        msg_text = replies[0]["content"] if replies else ""
        is_fast_path = "⚡ **Fast Path" in msg_text
        print(f"  [Iter {it+1}] Tempo: {dur_s}s | Fast Path: {is_fast_path} | Risposta: {msg_text[:60]}...")
        s1_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "is_fast_path": is_fast_path,
            "events_count": len(emitted_events),
        })

    s1_durations = [r["duration_s"] for r in s1_runs]
    results_data["scenarios"]["scenario_1_windows_fast_path"] = {
        "runs": s1_runs,
        "median_s": statistics.median(s1_durations),
        "min_s": min(s1_durations),
        "max_s": max(s1_durations),
        "fast_path_verified": all(r["is_fast_path"] for r in s1_runs),
    }

    # -------------------------------------------------------------
    # SCENARIO 2: RICERCA FILE (Fast Path vs Qwen LLM)
    # -------------------------------------------------------------
    print_banner("SCENARIO 2: RICERCA FILE (A: Fast Path vs B: Qwen Reasoning)")
    
    # 2A: Fast Path
    s2a_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="cerca il file sample_doc.txt nella cartella test_data",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        msg_text = replies[0]["content"] if replies else ""
        is_fast_path = "⚡ **Fast Path" in msg_text
        print(f"  [2A Fast Path - Iter {it+1}] Tempo: {dur_s}s | Fast Path: {is_fast_path} | Trovato: {'sample_doc.txt' in msg_text}")
        s2a_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "is_fast_path": is_fast_path,
            "found": "sample_doc.txt" in msg_text,
        })

    # 2B: Qwen Reasoning LLM (richiede spiegazione, non instradabile su Fast Path)
    s2b_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="trova sample_doc.txt in test_data e spiegami brevemente qual è lo scopo del documento",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        msg_text = replies[0]["content"] if replies else ""
        tool_stages = [p.get("stage") for p in emitted_events if p.get("type") == "tool_progress"]
        stream_chunks = [p for p in emitted_events if p.get("type") == "streaming_chunk"]
        print(f"  [2B Qwen LLM - Iter {it+1}] Tempo: {dur_s}s | Tool stages: {tool_stages} | Chunks: {len(stream_chunks)}")
        s2b_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "tool_stages": tool_stages,
            "streaming_chunks": len(stream_chunks),
            "content_len": len(msg_text),
        })

    results_data["scenarios"]["scenario_2_search_file"] = {
        "fast_path": {
            "runs": s2a_runs,
            "median_s": statistics.median([r["duration_s"] for r in s2a_runs]),
            "min_s": min([r["duration_s"] for r in s2a_runs]),
            "max_s": max([r["duration_s"] for r in s2a_runs]),
        },
        "qwen_llm": {
            "runs": s2b_runs,
            "median_s": statistics.median([r["duration_s"] for r in s2b_runs]),
            "min_s": min([r["duration_s"] for r in s2b_runs]),
            "max_s": max([r["duration_s"] for r in s2b_runs]),
        },
        "speedup_ratio": round(statistics.median([r["duration_s"] for r in s2b_runs]) / max(0.001, statistics.median([r["duration_s"] for r in s2a_runs])), 1)
    }

    # -------------------------------------------------------------
    # SCENARIO 3: LETTURA DOCUMENTO (Fast Path vs Qwen LLM)
    # -------------------------------------------------------------
    print_banner("SCENARIO 3: LETTURA DOCUMENTO (A: Fast Path vs B: Qwen Extraction)")
    
    # 3A: Fast Path
    s3a_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="leggi il file test_data/sample_doc.txt",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        msg_text = replies[0]["content"] if replies else ""
        is_fast_path = "⚡ **Fast Path" in msg_text
        has_secret = "OMEGA_SURFACE_2026" in msg_text
        print(f"  [3A Fast Path - Iter {it+1}] Tempo: {dur_s}s | Fast Path: {is_fast_path} | Chiave letta: {has_secret}")
        s3a_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "is_fast_path": is_fast_path,
            "has_secret": has_secret,
        })

    # 3B: Qwen Extraction LLM (richiede estrazione semantica specifica)
    s3b_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="analizza il file test_data/sample_doc.txt e dimmi qual è la parola chiave segreta",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        msg_text = replies[0]["content"] if replies else ""
        has_secret = "OMEGA_SURFACE_2026" in msg_text
        stream_chunks = [p for p in emitted_events if p.get("type") == "streaming_chunk"]
        print(f"  [3B Qwen LLM - Iter {it+1}] Tempo: {dur_s}s | Chiave estratta: {has_secret} | Chunks: {len(stream_chunks)}")
        s3b_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "has_secret": has_secret,
            "streaming_chunks": len(stream_chunks),
        })

    results_data["scenarios"]["scenario_3_read_document"] = {
        "fast_path": {
            "runs": s3a_runs,
            "median_s": statistics.median([r["duration_s"] for r in s3a_runs]),
            "min_s": min([r["duration_s"] for r in s3a_runs]),
            "max_s": max([r["duration_s"] for r in s3a_runs]),
        },
        "qwen_llm": {
            "runs": s3b_runs,
            "median_s": statistics.median([r["duration_s"] for r in s3b_runs]),
            "min_s": min([r["duration_s"] for r in s3b_runs]),
            "max_s": max([r["duration_s"] for r in s3b_runs]),
        },
        "speedup_ratio": round(statistics.median([r["duration_s"] for r in s3b_runs]) / max(0.001, statistics.median([r["duration_s"] for r in s3a_runs])), 1)
    }

    # -------------------------------------------------------------
    # SCENARIO 4: CONVERSAZIONE IN ITALIANO (Streaming Qwen)
    # -------------------------------------------------------------
    print_banner("SCENARIO 4: CONVERSAZIONE IN ITALIANO (Streaming Qwen)")
    s4_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        chunk_times = []
        async def mock_broadcast(cid, p):
            if p.get("type") == "streaming_chunk":
                chunk_times.append(time.time() - t0)
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="Spiega in tre frasi concise cosa distingue un sistema operativo AI da un assistente tradizionale.",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        ttft_s = round(chunk_times[0], 3) if chunk_times else None
        msg_text = replies[0]["content"] if replies else ""
        print(f"  [Iter {it+1}] Totale: {dur_s}s | TTFT: {ttft_s}s | Chunks: {len(chunk_times)} | Testo: {msg_text[:60]}...")
        s4_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "ttft_s": ttft_s,
            "chunks_count": len(chunk_times),
            "text_length": len(msg_text),
        })

    s4_durations = [r["duration_s"] for r in s4_runs]
    s4_ttfts = [r["ttft_s"] for r in s4_runs if r["ttft_s"] is not None]
    results_data["scenarios"]["scenario_4_italian_conversation"] = {
        "runs": s4_runs,
        "median_duration_s": statistics.median(s4_durations),
        "median_ttft_s": statistics.median(s4_ttfts) if s4_ttfts else 0.0,
        "min_duration_s": min(s4_durations),
        "max_duration_s": max(s4_durations),
    }

    # -------------------------------------------------------------
    # SCENARIO 5: FLUSSO MULTI-STEP (Qwen Coordination)
    # -------------------------------------------------------------
    print_banner("SCENARIO 5: FLUSSO MULTI-STEP (Qwen Coordination)")
    s5_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="Verifica se il file test_data/sample_doc.txt esiste e poi chiedi a @architect di commentarlo brevemente.",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        tasks_created = [p.get("task") for p in emitted_events if p.get("type") == "task_updated" and p.get("task")]
        unique_tasks = {t["id"]: t["bot_id"] for t in tasks_created if t}
        print(f"  [Iter {it+1}] Tempo: {dur_s}s | Tasks coinvolti: {unique_tasks} | Risposte: {len(replies)}")
        s5_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "tasks_count": len(unique_tasks),
            "replies_count": len(replies),
        })

    s5_durations = [r["duration_s"] for r in s5_runs]
    results_data["scenarios"]["scenario_5_multistep"] = {
        "runs": s5_runs,
        "median_s": statistics.median(s5_durations),
        "min_s": min(s5_durations),
        "max_s": max(s5_durations),
    }

    # -------------------------------------------------------------
    # SCENARIO 6: OPERAZIONI CON AUTORIZZAZIONE (Human-in-the-loop)
    # -------------------------------------------------------------
    print_banner("SCENARIO 6: OPERAZIONI CON AUTORIZZAZIONE (Human-in-the-loop)")
    s6_runs = []
    for it in range(3):
        t0 = time.time()
        emitted_events = []
        async def mock_broadcast(cid, p):
            emitted_events.append(p)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content="clicca sulle coordinate 450, 600 per aprire il menu",
            broadcast_fn=mock_broadcast,
        )
        dur_s = round(time.time() - t0, 3)
        rep = replies[0] if replies else {}
        card = rep.get("action_card_json")
        has_approval = False
        appr_id = None
        if card:
            c_dict = json.loads(card) if isinstance(card, str) else card
            has_approval = c_dict.get("status") == "waiting_approval" and bool(c_dict.get("approval_id"))
            appr_id = c_dict.get("approval_id")

        print(f"  [Iter {it+1}] Tempo: {dur_s}s | Richiesta autorizzazione creata: {has_approval} (ID: {appr_id})")
        s6_runs.append({
            "iteration": it + 1,
            "duration_s": dur_s,
            "has_approval": has_approval,
            "approval_id": appr_id,
        })

    results_data["scenarios"]["scenario_6_authorization"] = {
        "runs": s6_runs,
        "median_s": statistics.median([r["duration_s"] for r in s6_runs]),
        "security_preserved": all(r["has_approval"] for r in s6_runs),
    }

    # -------------------------------------------------------------
    # SCENARIO 7: VERIFICA STREAMING E REATTIVITÀ INTERMEDIA
    # -------------------------------------------------------------
    print_banner("SCENARIO 7: STREAMING TOKEN-BY-TOKEN E STATI INTERMEDI")
    t0 = time.time()
    stream_events = []
    tool_events = []
    async def mock_broadcast_s7(cid, p):
        if p.get("type") == "streaming_chunk":
            stream_events.append((time.time() - t0, p))
        elif p.get("type") == "tool_progress":
            tool_events.append((time.time() - t0, p))

    s7_replies = await orchestrator.handle_conversation_turn(
        chat_id=chat_id,
        user_content="Fornisci una sintesi numerata di tre punti sull'architettura locale di CoworkerOS.",
        broadcast_fn=mock_broadcast_s7,
    )
    s7_dur = round(time.time() - t0, 3)
    chunk_delays = [stream_events[i][0] - stream_events[i-1][0] for i in range(1, len(stream_events))] if len(stream_events) > 1 else [0]
    avg_chunk_interval_ms = round(statistics.mean(chunk_delays) * 1000, 1) if chunk_delays else 0

    print(f"  Totale Chunks emessi: {len(stream_events)}")
    print(f"  Intervallo medio tra chunk: {avg_chunk_interval_ms} ms")
    print(f"  TTFT (primo token): {round(stream_events[0][0], 3) if stream_events else 0}s")
    print(f"  Tempo totale: {s7_dur}s")

    results_data["scenarios"]["scenario_7_streaming"] = {
        "total_chunks": len(stream_events),
        "ttft_s": round(stream_events[0][0], 3) if stream_events else 0,
        "avg_chunk_interval_ms": avg_chunk_interval_ms,
        "duration_s": s7_dur,
        "streaming_active": len(stream_events) > 5,
    }

    # -------------------------------------------------------------
    # SCENARIO 8: REGRESSIONI E GUARDRAILS DI SICUREZZA
    # -------------------------------------------------------------
    print_banner("SCENARIO 8: REGRESSIONI E GUARDRAILS DI SICUREZZA")
    guardrail_checks = [
        ("Cosa c'è dentro test_data?", "Ambiguous query must NOT use Fast Path"),
        ("Analizza criticamente le dipendenze in requirements.txt", "Reasoning query must NOT use Fast Path"),
        ("Elimina il file test_data/sample_doc.txt", "Destructive mutation must NOT use Fast Path"),
        ("leggi sample_doc.txt e poi riassumilo", "Multi-step chain must NOT use Fast Path"),
        ("dimmi qual è la parola chiave segreta in sample_doc.txt", "Extraction query must NOT use Fast Path"),
    ]
    g_results = []
    for q, desc in guardrail_checks:
        route = FastPathRouter.try_route(q)
        blocked_from_fast_path = (route is None)
        print(f"  Check '{q[:40]}...': {'PASS' if blocked_from_fast_path else 'FAIL'} (Route: {route})")
        g_results.append({
            "query": q,
            "description": desc,
            "passed": blocked_from_fast_path,
            "route": route,
        })

    # Verifica assenza tool shell
    openai_tool_names = [t["function"]["name"] for t in orchestrator.openai_tools]
    has_shell = any(k in openai_tool_names for k in ("run_command", "bash", "shell", "powershell", "exec"))
    print(f"  Verifica assenza tool shell da CoworkerOS: {'PASS (Nessuna shell esposta)' if not has_shell else 'FAIL'}")

    results_data["scenarios"]["scenario_8_guardrails"] = {
        "checks": g_results,
        "shell_blocked": not has_shell,
        "all_passed": all(r["passed"] for r in g_results) and not has_shell,
    }

    # 3. Stato finale RAM e arresto ordinato
    ram_end = get_system_ram_info()
    power_end = get_system_power_info()
    results_data["ram_final"] = ram_end
    results_data["power_end"] = power_end

    print_banner("ARRESTO PULITO DEL SERVER LLAMA")
    stop_res = await local_model_mgr.stop_server_async()
    print(f"llama-server arrestato con successo: {stop_res['success']}")

    # Salvataggio risultati JSON
    out_file = BASE_DIR / "phase4_reactivity_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2, ensure_ascii=False)
    print(f"\n[Completato] Tutti i risultati sono stati salvati in: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
