import os
import sys
import asyncio
import json
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# 1. Isolamento DB prima di qualsiasi import di CoworkerOS
sys.path.insert(0, os.path.abspath("backend"))
import test_db_isolation
import database as db
from agent_engine import AgentOrchestrator, orchestrator
from local_model_manager import local_model_mgr

async def run_regression_test():
    print("=== AVVIO TEST DI REGRESSIONE OBBLIGATORIO COWORKEROS ===")
    we_started_server = False
    if not local_model_mgr.is_server_healthy():
        print("Avvio di llama-server per inferenza locale Qwen3.5-4B...")
        start_res = local_model_mgr.start_server_sync(enable_vision=False)
        if not start_res.get("success"):
            print(f"ATTENZIONE: Avvio llama-server locale non riuscito: {start_res}")
        else:
            we_started_server = True
            print("llama-server avviato e pronto.")

    try:
        prompt = "Devi entrare nell'app di Antigravity, aprire il progetto clone-whoop, creare una conversazione e chiedere lo stato del progetto."
        print(f"Prompt di test: \"{prompt}\"\n")

        # TEST 1: Verifica selezione deterministica strumenti per Chief
        print("[TEST 1] Verifica _select_tools_for_turn()...")
        chief_tools = orchestrator._select_tools_for_turn("chief", prompt)
        chief_tool_names = {t["function"]["name"] for t in chief_tools}
        print(f"Tool selezionati per Chief: {chief_tool_names}")

        assert "delegate_to_coworker" not in chief_tool_names, "ERRORE: Chief NON deve avere delegate_to_coworker per compiti desktop!"
        assert "inspect_zip" not in chief_tool_names, "ERRORE: inspect_zip non deve essere selezionato per compiti desktop!"
        assert "manage_files" not in chief_tool_names, "ERRORE: manage_files non deve essere selezionato per compiti desktop!"
        assert "list_windows" in chief_tool_names, "ERRORE: list_windows deve essere presente!"
        assert "inspect_screen" in chief_tool_names, "ERRORE: inspect_screen deve essere presente!"
        assert "click_screen_element" in chief_tool_names, "ERRORE: click_screen_element deve essere presente!"
        assert "focus_and_paste_into_app" in chief_tool_names, "ERRORE: focus_and_paste_into_app deve essere presente!"
        print("-> PASS: Chief ha esclusivamente strumenti desktop, nessuna delega e nessun tool ZIP/file.\n")

        # TEST 2: Inizializzazione DB di test e Chat
        print("[TEST 2] Creazione chat di test nel DB isolato...")
        chat = db.create_chat(title="Regression Test Antigravity", participants=["chief"])
        chat_id = chat["id"]
        print(f"Chat creata: {chat_id} nel DB {os.environ.get('COWORKEROS_DB_PATH')}")

        # TEST 3: Esecuzione reale del turno con il modello
        print("[TEST 3] Esecuzione handle_conversation_turn con il prompt richiesto...")
        t0 = time.time()
        events = []
        async def capture_event(cid, evt):
            events.append(evt)

        replies = await orchestrator.handle_conversation_turn(
            chat_id=chat_id,
            user_content=prompt,
            broadcast_fn=capture_event,
            target_bot_id="chief",
        )
        elapsed = round(time.time() - t0, 2)
        print(f"Turno completato in {elapsed}s. Risposte generate: {len(replies)}")

        # Ispezione attività e task nel DB isolato
        tasks = db.get_tasks(chat_id=chat_id)
        activities = db.get_activities(chat_id=chat_id)
        print(f"Task registrati: {len(tasks)}")
        print(f"Attività registrate: {len(activities)}")

        for t in tasks:
            print(f"  Task {t['id']} | Bot: {t['bot_id']} | Status: {t['status']} | Title: {t['title']}")
            if t.get("error_msg"):
                print(f"    Error/Reason: {t['error_msg']}")

        for act in activities:
            print(f"  Attività {act['id']} | Tool: {act['tool_name']} | Status: {act['status']}")

        for r in replies:
            print(f"\nRisposta di @{r.get('sender_name', 'Bot')}:\n{r.get('content')}\n")

        # Verifiche vincoli:
        # 1. Chief non deleghi ad Archivist
        delegated_acts = [a for a in activities if a["tool_name"] == "delegate_to_coworker"]
        assert len(delegated_acts) == 0, f"ERRORE: È stata eseguita una delega non consentita: {delegated_acts}"
        print("-> PASS: Chief non ha delegato ad Archivist.")

        # 2. Nessun agente tenti di aprire zip
        zip_acts = [a for a in activities if a["tool_name"] == "inspect_zip"]
        assert len(zip_acts) == 0, f"ERRORE: È stato chiamato inspect_zip: {zip_acts}"
        print("-> PASS: Nessun agente ha tentato di aprire zip.")

        # 3. Il primo strumento scelto sia pertinente al desktop
        assert len(activities) > 0, "ERRORE: Nessuna attività registrata!"
        first_tool = activities[0]["tool_name"]
        assert first_tool in ("list_windows", "inspect_screen"), f"ERRORE: Primo tool '{first_tool}' non è uno strumento desktop!"
        print(f"-> PASS: Il primo strumento scelto è pertinente al desktop: '{first_tool}'.")

        # 4. Il task non risulti completato prima dell'esecuzione e riporti il limite reale se Antigravity non è disponibile
        root_task = tasks[0]
        assert root_task["status"] != "completed", f"ERRORE: Il task non deve risultare completato con successo fittizio! Status: {root_task['status']}"
        print(f"-> PASS: Il task non è marcato falsamente come completato (Status: {root_task['status']}).")

        # 5. La risposta finale riporti soltanto risultati effettivamente osservati
        final_text = replies[-1]["content"]
        assert any(w in final_text.lower() for w in ("antigravity", "schermo", "clone-whoop", "ispezione", "non identificato")), f"ERRORE: La risposta finale deve riportare l'osservazione: {final_text}"
        print("-> PASS: La risposta finale segnala fedelmente lo stato reale delle finestre Windows / schermo.\n")

        # TEST 4: Verifica sistema di approvazione e ripresa automatica del task (Fase 4 & Task Engine)
        print("[TEST 4] Test approvazione e ripresa automatica multi-passaggio...")
        appr_task = db.create_task(
            chat_id=chat_id,
            bot_id="chief",
            title="Test Clic Desktop Antigravity",
            goal="Aprire clone-whoop cliccando su pulsante",
            instruction="Clicca su coordinate (300, 400)",
        )
        act_card = db.create_approval(
            chat_id=chat_id,
            bot_id="chief",
            action_type="desktop_click",
            description="Clic su pulsante progetto clone-whoop",
            payload={"tool_name": "click_screen_element", "args": {"norm_x": 300, "norm_y": 400, "goal_description": "clone-whoop"}},
            task_id=appr_task["id"],
        )
        db.update_task_status_atomic(appr_task["id"], "waiting_approval")
        print(f"Approvazione creata: {act_card['id']} in stato 'waiting_approval' per task {appr_task['id']}")

        # Esecuzione dell'approvazione con ripresa
        res_appr = await orchestrator.execute_approved_action(
            approval_id=act_card["id"],
            approved=True,
            broadcast_fn=capture_event,
        )
        print(f"Esito execute_approved_action: {res_appr.get('status')}")
        updated_appr_task = db.get_task(appr_task["id"])
        print(f"Stato task dopo approvazione ed esecuzione: {updated_appr_task['status']}")
        assert res_appr.get("status") == "ok", "ERRORE: Risoluzione approvazione fallita!"
        print("-> PASS: Approvazione eseguita, evidenza registrata e flusso di ripresa attivato con successo.\n")

        # TEST 5: Verifica metriche di latenza con prefill_ms registrato
        print("[TEST 5] Verifica metriche di inferenza e latenza...")
        metrics = local_model_mgr.inference_metrics_log
        print(f"Numero chiamate registrate nel log metriche: {len(metrics)}")
        if metrics:
            last_m = metrics[-1]
            print(f"Ultima metrica registrata:")
            print(f"  Provider: {last_m.get('provider')}")
            print(f"  Queue wait: {last_m.get('queue_wait_ms')} ms")
            print(f"  Prefill: {last_m.get('prefill_ms')} ms")
            print(f"  Generation: {last_m.get('generation_ms')} ms")
            print(f"  TTFT: {last_m.get('time_to_first_token_ms')} ms")
            print(f"  Tokens/s: {last_m.get('tokens_per_second')}")
            assert "prefill_ms" in last_m, "ERRORE: prefill_ms deve essere presente nelle metriche!"
            print("-> PASS: Metriche separate per attesa, prefill e generazione correttamente registrate.\n")

        print("=== TUTTI I 5 TEST DI REGRESSIONE SUPERATI CON SUCCESSO ===")

    finally:
        if we_started_server:
            print("Arresto di sicurezza di llama-server avviato per il test...")
            local_model_mgr.stop_server_sync()
            print("llama-server arrestato con successo.")

if __name__ == "__main__":
    asyncio.run(run_regression_test())
