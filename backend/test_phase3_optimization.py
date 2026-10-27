import asyncio
import json
import os
import sys
import time
from pathlib import Path

backend_dir = os.path.abspath(os.path.dirname(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ISOLAMENTO AMBIENTE DI TEST: Database separato dedicato ai test/benchmark
os.environ["COWORKEROS_DB_PATH"] = str(Path(__file__).parent / "test_isolated.db")

import database as db
from local_model_manager import local_model_mgr, get_system_ram_info
from agent_engine import orchestrator

PREVIOUS_TIMES = {
    "conversazione": 78.82,
    "tool_calling": 114.94,
    "ricerca_file": 128.74,
    "multistep": 161.33,
}

results_log = []

async def run_benchmark_case(test_id, name, prompt, bot_id, expected_tool=None):
    print(f"\n=======================================================", flush=True)
    print(f"ESECUZIONE: {name}", flush=True)
    print(f"=======================================================", flush=True)

    ram_before = get_system_ram_info()
    chat = db.create_chat(f"Fase3_{test_id}", [bot_id])
    chat_id = chat["id"]

    # Conteggio chiamate e tempi iniziali
    t0 = time.time()
    replies = await orchestrator.handle_conversation_turn(
        chat_id=chat_id,
        user_content=prompt,
        target_bot_id=bot_id
    )
    total_dur = round(time.time() - t0, 2)
    ram_after = get_system_ram_info()

    content = replies[0]["content"] if replies else ""
    acts = db.get_activities(chat_id)
    tool_calls_count = len(acts)
    tools_executed = [a["tool_name"] for a in acts]
    
    # Recupera i record di utilizzo generati in questa chat
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT input_tokens, output_tokens, duration_ms FROM usage_records WHERE chat_id=? ORDER BY id ASC", (chat_id,))
    usages = cur.fetchall()
    llm_calls_count = len(usages)
    
    total_in_tokens = sum(u[0] or 0 for u in usages)
    total_out_tokens = sum(u[1] or 0 for u in usages)
    llm_duration_s = sum((u[2] or 0) / 1000.0 for u in usages)
    orchestration_time_s = max(0.0, round(total_dur - llm_duration_s, 2))
    
    # Calcolo velocità effettiva generazione
    gen_speed = round(total_out_tokens / llm_duration_s, 2) if llm_duration_s > 0 else 0.0
    prev_time = PREVIOUS_TIMES.get(test_id, total_dur)
    improvement_pct = round(((prev_time - total_dur) / prev_time) * 100.0, 1)

    record = {
        "id": test_id,
        "name": name,
        "tempo_precedente_s": prev_time,
        "tempo_nuovo_s": total_dur,
        "miglioramento_pct": improvement_pct,
        "prompt_tokens": total_in_tokens,
        "completion_tokens": total_out_tokens,
        "reasoning_tokens": 0,
        "llm_calls": llm_calls_count,
        "tool_calls": tool_calls_count,
        "tools_executed": tools_executed,
        "gen_speed_tok_s": gen_speed,
        "orchestrazione_s": orchestration_time_s,
        "ram_avail_gb": ram_after["available_gb"],
        "content_preview": content[:180].replace("\n", " ")
    }
    results_log.append(record)

    print(f"Tempo: {total_dur}s (Prima: {prev_time}s | Miglioramento: {improvement_pct}%)", flush=True)
    print(f"Token In: {total_in_tokens} | Token Out: {total_out_tokens} | LLM Calls: {llm_calls_count}", flush=True)
    print(f"Tools ({tool_calls_count}): {tools_executed}", flush=True)
    print(f"Velocita' gen: {gen_speed} tok/s | Orchestrazione: {orchestration_time_s}s | RAM: {ram_after['available_gb']} GB", flush=True)
    print(f"Risposta: {content[:140]}...", flush=True)

async def main():
    print("==================================================================", flush=True)
    print("COWORKEROS — FASE 3: VERIFICA OTTIMIZZAZIONI PRESTAZIONI QWEN", flush=True)
    print("==================================================================", flush=True)

    db.init_db()
    db.seed_db()

    print("1. Avvio controllato di llama-server con nuove impostazioni...", flush=True)
    s_res = await local_model_mgr.start_server_async(enable_vision=False)
    if not s_res["success"]:
        print(f"Errore avvio server: {s_res}")
        return

    await orchestrator.set_provider_mode("LOCAL")

    # 1. Conversazione in italiano
    await run_benchmark_case(
        "conversazione",
        "Conversazione in italiano",
        "Ciao! Spiega in due frasi qual è il tuo ruolo come coordinatore del team.",
        bot_id="chief"
    )

    # 2. Tool calling
    await run_benchmark_case(
        "tool_calling",
        "Chiamata a uno strumento (list_windows)",
        "Usa lo strumento list_windows per elencare le finestre attive sul desktop.",
        bot_id="chief",
        expected_tool="list_windows"
    )

    # 3. Ricerca file
    await run_benchmark_case(
        "ricerca_file",
        "Ricerca di un file (search_files)",
        "Usa lo strumento search_files per trovare il file 'sample_doc.txt' all'interno della cartella 'test_data'.",
        bot_id="scout",
        expected_tool="search_files"
    )

    # 4. Attività multi-step
    await run_benchmark_case(
        "multistep",
        "Attività multi-step coordinata",
        "Esegui due passaggi: prima cerca i file con 'sample' nel nome tramite search_files, poi leggi il file 'test_data/sample_doc.txt' con read_document.",
        bot_id="scout"
    )

    print("\nArresto controllato di llama-server...", flush=True)
    await local_model_mgr.stop_server_async()

    out_file = Path(backend_dir) / "phase3_benchmark_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_log, f, indent=2, ensure_ascii=False)
    print(f"\nDati completi salvati in {out_file}!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
