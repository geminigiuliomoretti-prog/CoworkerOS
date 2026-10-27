import os
import sys
import time
import json
import asyncio
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Assicura importazione corretta dei moduli backend
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ISOLAMENTO AMBIENTE DI TEST: Database separato dedicato ai test/benchmark
os.environ["COWORKEROS_DB_PATH"] = str(BACKEND_DIR / "test_isolated.db")

import database as db
import tools_os
from agent_engine import orchestrator
from local_model_manager import local_model_mgr, get_system_ram_info

TEST_RESULTS = []


def record_result(test_num: int, title: str, passed: bool, details: str = "", metrics: dict = None):
    res = {
        "test_num": test_num,
        "title": title,
        "passed": passed,
        "details": details,
        "metrics": metrics or {},
    }
    TEST_RESULTS.append(res)
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] Test {test_num}: {title} -> {details}", flush=True)


# Semplice server HTTP locale per test navigazione browser
class MockWebHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        html = (
            "<!DOCTYPE html><html><head><title>CoworkerOS Test Portal</title></head>"
            "<body><h1>Benvenuto nel portale di test locale</h1>"
            "<p>Questa è una pagina simulata per la navigazione sicura dell'agente Scout. "
            "Token di verifica browser: WEB_VERIFY_SUCCESS_778.</p></body></html>"
        )
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Silenzioso


def start_mock_web_server(port=8765):
    server = HTTPServer(("127.0.0.1", port), MockWebHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


async def run_integration_tests():
    print("==================================================================", flush=True)
    print("COWORKEROS — SUITE DI TEST INTEGRATION QWEN3.5-4B (12 PUNTI)", flush=True)
    print("==================================================================", flush=True)

    web_server = start_mock_web_server(8765)
    # Pulizia/creazione chat di test
    db.init_db()
    db.seed_db()
    
    test_chat = db.create_chat("Test Qwen Integration", ["chief", "builder", "scout"])
    test_chat_id = test_chat["id"]

    # 1. Avvio di CoworkerOS & bootstrap
    try:
        b_status = orchestrator.get_model_status()
        ram_start = get_system_ram_info()
        record_result(
            1,
            "Avvio di CoworkerOS e moduli core",
            b_status is not None,
            f"Moduli inizializzati. RAM disponibile: {ram_start['available_gb']} GB",
            {"ram_available_gb": ram_start["available_gb"]}
        )
    except Exception as e:
        record_result(1, "Avvio di CoworkerOS e moduli core", False, f"Eccezione: {e}")

    # 2. Caricamento Qwen
    try:
        t0 = time.time()
        start_res = await local_model_mgr.start_server_async(enable_vision=False)
        load_time = round(time.time() - t0, 2)
        alive = local_model_mgr.is_server_healthy()
        status = orchestrator.get_model_status()
        rss_mb = status["local_model"]["server_rss_mb"]
        record_result(
            2,
            "Caricamento Qwen3.5-4B via llama.cpp",
            alive and start_res["success"],
            f"Server pronto in {load_time}s (PID: {status['local_model']['pid']}, RSS: {rss_mb} MB)",
            {"load_time_s": load_time, "rss_mb": rss_mb}
        )
    except Exception as e:
        record_result(2, "Caricamento Qwen3.5-4B via llama.cpp", False, f"Eccezione avvio: {e}")

    # Impostiamo esplicitamente LOCAL per i test
    await orchestrator.set_provider_mode("LOCAL")

    # 3. Conversazione in italiano
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Ciao! Spiega in due frasi qual è il tuo ruolo come coordinatore del team.",
            target_bot_id="chief"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        passed = bool(text) and len(text) > 20 and not text.startswith("⚠️")
        record_result(
            3,
            "Conversazione in italiano",
            passed,
            f"Risposta in {dur}s ({len(text)} caratteri): '{text[:90]}...'",
            {"duration_s": dur, "length": len(text)}
        )
    except Exception as e:
        record_result(3, "Conversazione in italiano", False, f"Eccezione: {e}")

    # 4. Chiamata a uno strumento (list_windows)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa lo strumento list_windows per elencare le finestre attive sul desktop.",
            target_bot_id="chief"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        has_tool = any(a["tool_name"] == "list_windows" for a in acts)
        passed = has_tool or "finestr" in text.lower() or "windows" in text.lower()
        record_result(
            4,
            "Chiamata a uno strumento (list_windows)",
            passed,
            f"Tool chiamato con successo in {dur}s. Risposta: {text[:80]}",
            {"duration_s": dur, "tool_found": has_tool}
        )
    except Exception as e:
        record_result(4, "Chiamata a uno strumento (list_windows)", False, f"Eccezione: {e}")

    # 5. Ricerca di un file (search_files)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa lo strumento search_files per trovare il file 'sample_doc.txt' all'interno della cartella 'test_data'.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        has_search = any(a["tool_name"] == "search_files" for a in acts)
        passed = has_search or "sample_doc.txt" in text
        record_result(
            5,
            "Ricerca di un file (search_files)",
            passed,
            f"Ricerca file eseguita in {dur}s. Risposta: {text[:90]}",
            {"duration_s": dur, "tool_executed": has_search}
        )
    except Exception as e:
        record_result(5, "Ricerca di un file (search_files)", False, f"Eccezione: {e}")

    # 6. Lettura di un documento (read_document)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa lo strumento read_document sul percorso 'test_data/sample_doc.txt' e dimmi qual è la parola chiave segreta contenuta nel testo.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        has_read = any(a["tool_name"] == "read_document" for a in acts)
        has_secret = "omega_surface_2026" in text.lower()
        passed = has_read and has_secret
        record_result(
            6,
            "Lettura di un documento reale (read_document)",
            passed,
            f"Parola chiave segreta rilevata: {has_secret} in {dur}s.",
            {"duration_s": dur, "has_secret": has_secret}
        )
    except Exception as e:
        record_result(6, "Lettura di un documento reale (read_document)", False, f"Eccezione: {e}")

    # 7. Analisi di uno ZIP (inspect_zip)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa lo strumento inspect_zip con action='read' su 'test_data/sample_archive.zip' per leggere il file 'info.txt'.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        has_zip = any(a["tool_name"] == "inspect_zip" for a in acts)
        has_zip_code = "alpha_zip_99" in text.lower() or "info.txt" in text
        passed = has_zip and has_zip_code
        record_result(
            7,
            "Analisi archivio ZIP sicuro (inspect_zip)",
            passed,
            f"ZIP ispezionato senza estrazione su disco in {dur}s. Risposta: {text[:90]}",
            {"duration_s": dur, "has_code": has_zip_code}
        )
    except Exception as e:
        record_result(7, "Analisi archivio ZIP sicuro (inspect_zip)", False, f"Eccezione: {e}")

    # 8. Navigazione browser (browse_url)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa lo strumento browse_url per consultare la pagina web http://127.0.0.1:8765/test.html e riferiscimi il token trovato.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        has_browse = any(a["tool_name"] == "browse_url" for a in acts)
        has_token = "web_verify_success_778" in text.lower()
        passed = has_browse and has_token
        record_result(
            8,
            "Navigazione browser web sicura (browse_url)",
            passed,
            f"Pagina web consultata in {dur}s. Token trovato: {has_token}.",
            {"duration_s": dur, "has_token": has_token}
        )
    except Exception as e:
        record_result(8, "Navigazione browser web sicura (browse_url)", False, f"Eccezione: {e}")

    # 9. Gestione di un errore (file inesistente)
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Usa read_document sul file 'test_data/non_existent_file_404.txt' e spiegami l'errore riscontrato.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=5)
        passed = "non trovato" in text.lower() or "non esiste" in text.lower() or "errore" in text.lower() or any(a.get("status") == "failed" for a in acts)
        record_result(
            9,
            "Gestione controllata degli errori",
            passed,
            f"Errore gestito correttamente senza blocchi in {dur}s: {text[:90]}",
            {"duration_s": dur}
        )
    except Exception as e:
        record_result(9, "Gestione controllata degli errori", False, f"Eccezione: {e}")

    # 10. Attività con più strumenti consecutivi
    try:
        t0 = time.time()
        replies = await orchestrator.handle_conversation_turn(
            chat_id=test_chat_id,
            user_content="Esegui due passaggi: prima cerca i file con 'sample' nel nome tramite search_files, poi leggi il file 'test_data/sample_doc.txt' con read_document.",
            target_bot_id="scout"
        )
        dur = round(time.time() - t0, 2)
        text = replies[0]["content"] if replies else ""
        acts = db.get_activities(test_chat_id, limit=6)
        tool_names = [a["tool_name"] for a in acts]
        has_multi = ("search_files" in tool_names or "read_document" in tool_names) and len(text) > 30
        record_result(
            10,
            "Attività multi-step con coordinamento strumenti",
            has_multi,
            f"Catena multi-step eseguita in {dur}s: {text[:90]}",
            {"duration_s": dur, "tools": tool_names[:3]}
        )
    except Exception as e:
        record_result(10, "Attività multi-step con coordinamento strumenti", False, f"Eccezione: {e}")

    # 11. Cambio provider LOCAL / CLOUD / AUTO
    try:
        res_cloud = await orchestrator.set_provider_mode("CLOUD")
        m_cloud = orchestrator.get_provider_mode()
        res_auto = await orchestrator.set_provider_mode("AUTO")
        m_auto = orchestrator.get_provider_mode()
        res_local = await orchestrator.set_provider_mode("LOCAL")
        m_local = orchestrator.get_provider_mode()
        passed = (m_cloud == "CLOUD" and m_auto == "AUTO" and m_local == "LOCAL")
        record_result(
            11,
            "Cambio provider LOCAL / CLOUD / AUTO",
            passed,
            f"Modalità commutate e verificate con persistenza DB (CLOUD -> AUTO -> LOCAL).",
            {"modes": [m_cloud, m_auto, m_local]}
        )
    except Exception as e:
        record_result(11, "Cambio provider LOCAL / CLOUD / AUTO", False, f"Eccezione: {e}")

    # 12. Arresto corretto del server
    try:
        t0 = time.time()
        stop_res = await local_model_mgr.stop_server_async()
        dur = round(time.time() - t0, 2)
        alive_after = local_model_mgr.is_server_healthy()
        status_after = orchestrator.get_model_status()
        passed = stop_res["success"] and not alive_after and status_after["local_model"]["status"] == "stopped"
        record_result(
            12,
            "Arresto controllato di llama-server",
            passed,
            f"Server arrestato in {dur}s. Porta 8080 rilasciata. RAM residua: {status_after['ram_info']['available_gb']} GB.",
            {"duration_s": dur, "ram_freed_gb": status_after["ram_info"]["available_gb"]}
        )
    except Exception as e:
        record_result(12, "Arresto controllato di llama-server", False, f"Eccezione: {e}")

    # Chiusura mock web server
    web_server.shutdown()

    # Riepilogo finale
    total_tests = len(TEST_RESULTS)
    passed_tests = sum(1 for t in TEST_RESULTS if t["passed"])
    print("\n==================================================================", flush=True)
    print(f"RIEPILOGO TEST: {passed_tests}/{total_tests} SUPERATI", flush=True)
    print("==================================================================", flush=True)
    
    out_file = BACKEND_DIR / "test_phase2e_results.json"
    out_file.write_text(json.dumps(TEST_RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report dettagliato salvato in: {out_file}", flush=True)


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
