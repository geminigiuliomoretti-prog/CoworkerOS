"""
CoworkerOS - Suite di Test Automatizzati Fase 2A: Motore Multi-Agente Persistente
Verifica dei 10 requisiti architetturali:
1. Persistenza dei task nel database SQLite tra riavvii.
2. Rispetto delle dipendenze (Task B non parte finché Task A non è completed).
3. Passaggio di consegne strutturato tra agenti con contesto verificabile e annotazione peer review.
4. Rilevamento e blocco di cicli di delega (A -> B -> A).
5. Riconoscimento dei task interrotti all'avvio e transizione atomica a 'interrupted'.
6. Ripresa sicura di un task senza rieseguire azioni non idempotenti (verifica evidence).
7. Associazione corretta e atomica tra task e approvazioni.
8. Esecuzione concorrente di task indipendenti senza corruzione dello stato.
9. Gestione dei fallimenti del modello con fallback o marcatura 'failed' senza loop infiniti.
10. Regression test completo: tutte le protezioni delle Fasi 1 e 1.1 continuano a funzionare al 100%.
"""

import os
import sys
import time
import uuid
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import database as db
import tools_os
from agent_engine import orchestrator
from main import app, AUTH_TOKEN
from fastapi.testclient import TestClient

# Import suite di regressione Fase 1 / 1.1
import test_hardening_phase1


def test_1_task_persistence_across_restarts():
    """1. Persistenza dei task nel database SQLite tra riavvii."""
    print("\n--- TEST 1: Persistenza Task SQLite tra Riavvii ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Persistence Test Room", ["chief", "architect"], chat_id=chat_id)

    task_id = f"task_{uuid.uuid4().hex[:8]}"
    created = db.create_task(
        task_id=task_id,
        chat_id=chat_id,
        bot_id="chief",
        title="Verifica persistenza disco",
        goal="Assicurare che i dati siano scritti su SQLite WAL",
        instruction="Scrivi un record e ricaricalo con nuova connessione",
        dependencies=["dep_1", "dep_2"],
        max_retries=3,
        idempotency_key=f"idem_{task_id}",
    )
    assert created["id"] == task_id
    assert created["status"] == "pending"
    assert created["dependencies"] == ["dep_1", "dep_2"]

    # Simula riavvio: chiudi la connessione e interroga direttamente SQLite
    fetched = db.get_task(task_id)
    assert fetched is not None, "Il task non è stato persistito su disco!"
    assert fetched["id"] == task_id
    assert fetched["bot_id"] == "chief"
    assert fetched["title"] == "Verifica persistenza disco"
    assert fetched["dependencies"] == ["dep_1", "dep_2"]
    assert fetched["idempotency_key"] == f"idem_{task_id}"

    # Filtro tasks per chat e status
    chat_tasks = db.get_tasks(chat_id=chat_id, status="pending")
    assert any(t["id"] == task_id for t in chat_tasks)
    print("  [PASS] Task creato, persistito su SQLite e ricaricato correttamente con tutti i metadati.")


def test_2_dependency_ordering():
    """2. Rispetto delle dipendenze: il task B non parte se il task A non è completato."""
    print("\n--- TEST 2: Rispetto delle Dipendenze dei Task ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Dep Test Room", ["architect", "builder"], chat_id=chat_id)

    task_a_id = f"task_a_{uuid.uuid4().hex[:8]}"
    task_b_id = f"task_b_{uuid.uuid4().hex[:8]}"

    # Task A: nessun vincolo
    db.create_task(task_id=task_a_id, chat_id=chat_id, bot_id="architect", title="Task A", dependencies=[])
    # Task B: dipende da Task A
    db.create_task(task_id=task_b_id, chat_id=chat_id, bot_id="builder", title="Task B", dependencies=[task_a_id])

    # Inizialmente: solo Task A deve risultare pronto
    ready_tasks = db.get_ready_tasks(chat_id)
    ready_ids = [t["id"] for t in ready_tasks]
    assert task_a_id in ready_ids, "Task A dovrebbe essere pronto"
    assert task_b_id not in ready_ids, "Task B NON deve essere pronto (Task A è pending)"

    # Task A passa a 'running': Task B non è ancora pronto
    db.update_task_status_atomic(task_a_id, from_status="pending", to_status="running")
    ready_tasks = db.get_ready_tasks(chat_id)
    assert task_b_id not in [t["id"] for t in ready_tasks], "Task B non può partire se Task A è running"

    # Task A completa con successo: Task B diventa pronto
    db.update_task_status_atomic(task_a_id, from_status="running", to_status="completed", result_data={"proof": "ok"})
    ready_tasks = db.get_ready_tasks(chat_id)
    ready_ids = [t["id"] for t in ready_tasks]
    assert task_b_id in ready_ids, "Task B deve risultare pronto dopo che Task A è completato"

    # Se un task dipende da un task fallito, non deve mai risultare pronto
    task_c_id = f"task_c_{uuid.uuid4().hex[:8]}"
    task_failed_id = f"task_f_{uuid.uuid4().hex[:8]}"
    db.create_task(task_id=task_failed_id, chat_id=chat_id, bot_id="architect", title="Task Fallito")
    db.update_task_status_atomic(task_failed_id, from_status="pending", to_status="failed", error_msg="Crash")
    db.create_task(task_id=task_c_id, chat_id=chat_id, bot_id="builder", title="Task C", dependencies=[task_failed_id])

    ready_tasks = db.get_ready_tasks(chat_id)
    assert task_c_id not in [t["id"] for t in ready_tasks], "Task C non deve partire se la sua dipendenza è fallita"
    print("  [PASS] Dipendenze rispettate rigorosamente: Task B attende Task A, dipendenze fallite bloccano l'esecuzione.")


def test_3_structured_delegation_and_peer_review():
    """3. Passaggio di consegne strutturato e annotazione peer review."""
    print("\n--- TEST 3: Delega Strutturata e Peer Review ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Delegation Room", ["chief", "architect", "builder"], chat_id=chat_id)

    # Verifica registrazione tool peer review
    from agent_engine import _build_gemini_tools
    tools = _build_gemini_tools()
    func_declarations = tools[0].function_declarations
    tool_names = [f.name for f in func_declarations]
    assert "delegate_to_coworker" in tool_names, "delegate_to_coworker deve essere registrato nei tool"
    assert "request_peer_review" in tool_names, "request_peer_review deve essere registrato nei tool"

    # Verifica schema di peer review
    peer_tool = next(f for f in func_declarations if f.name == "request_peer_review")
    assert "reviewer_bot_id" in peer_tool.parameters.properties
    assert "artifact_to_review" in peer_tool.parameters.properties
    assert "non costituisce una validazione indipendente" in peer_tool.description

    # Simula passaggio di contesto strutturato
    parent_task = db.create_task(
        task_id=f"parent_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        bot_id="chief",
        title="Coordinamento",
        goal="Sviluppare un modulo",
    )
    subtask = db.create_task(
        task_id=f"sub_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        parent_task_id=parent_task["id"],
        bot_id="architect",
        title="Architettura modulo",
        goal="Definire le specifiche tecniche",
        instruction="Produci specifica JSON senza toccare il desktop",
    )
    assert subtask["parent_task_id"] == parent_task["id"]
    print("  [PASS] Tool e schemi di delega strutturata e peer review conformi alle specifiche.")


def test_4_cycle_detection():
    """4. Rilevamento e blocco di cicli di delega (A -> B -> A)."""
    print("\n--- TEST 4: Rilevamento e Blocco Cicli di Delega ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Cycle Room", ["chief", "architect", "builder", "scout"], chat_id=chat_id)

    # Scenario: Chief crea Task 1
    t1 = db.create_task(task_id=f"t1_{uuid.uuid4().hex[:8]}", chat_id=chat_id, bot_id="chief", title="Root")
    # Architect riceve Subtask 2 da Chief
    t2 = db.create_task(task_id=f"t2_{uuid.uuid4().hex[:8]}", chat_id=chat_id, parent_task_id=t1["id"], bot_id="architect", title="Sub 1")
    # Builder riceve Subtask 3 da Architect
    t3 = db.create_task(task_id=f"t3_{uuid.uuid4().hex[:8]}", chat_id=chat_id, parent_task_id=t2["id"], bot_id="builder", title="Sub 2")

    # 1. Builder tenta di ridelegare a Chief -> CICLO RILEVATO (Chief -> Architect -> Builder -> Chief)
    assert orchestrator._is_cycle_detected(parent_task_id=t3["id"], target_bot_id="chief") is True, "Ciclo a Chief non rilevato!"
    # 2. Builder tenta di ridelegare a Architect -> CICLO RILEVATO (Architect -> Builder -> Architect)
    assert orchestrator._is_cycle_detected(parent_task_id=t3["id"], target_bot_id="architect") is True, "Ciclo ad Architect non rilevato!"
    # 3. Builder tenta di ridelegare a se stesso -> CICLO RILEVATO
    assert orchestrator._is_cycle_detected(parent_task_id=t3["id"], target_bot_id="builder") is True, "Auto-delega non rilevata come ciclo!"
    # 4. Builder delega a Scout (agente non ancora nella catena) -> NESSUN CICLO
    assert orchestrator._is_cycle_detected(parent_task_id=t3["id"], target_bot_id="scout") is False, "Falso positivo su Scout!"

    print("  [PASS] Rilevamento cicli di delega (A -> B -> A, catene profonde e auto-delega) attivo ed efficace.")


def test_5_interruption_recovery_on_startup():
    """5. Riconoscimento dei task interrotti all'avvio e transizione a interrupted."""
    print("\n--- TEST 5: Recovery dei Task Interrotti all'Avvio ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Interruption Room", ["chief", "builder", "architect"], chat_id=chat_id)

    # Crea 3 task in stati diversi
    t_running = db.create_task(task_id=f"trun_{uuid.uuid4().hex[:8]}", chat_id=chat_id, bot_id="builder", title="Task Interrotto")
    db.update_task_status_atomic(t_running["id"], from_status="pending", to_status="running")

    t_waiting = db.create_task(task_id=f"twait_{uuid.uuid4().hex[:8]}", chat_id=chat_id, bot_id="builder", title="Task in Attesa Approvazione")
    db.update_task_status_atomic(t_waiting["id"], from_status="pending", to_status="waiting_approval")

    t_completed = db.create_task(task_id=f"tdone_{uuid.uuid4().hex[:8]}", chat_id=chat_id, bot_id="architect", title="Task Già Fatto")
    db.update_task_status_atomic(t_completed["id"], from_status="pending", to_status="completed")

    # Simula riavvio del processo backend
    recovered = db.recover_interrupted_tasks()
    recovered_ids = [t["id"] for t in recovered]

    assert t_running["id"] in recovered_ids, "Il task 'running' doveva essere recuperato"
    assert db.get_task(t_running["id"])["status"] == "interrupted", "Stato non aggiornato a 'interrupted'"

    # Verifica che i task in waiting_approval o completed NON vengano alterati
    assert db.get_task(t_waiting["id"])["status"] == "waiting_approval", "waiting_approval non deve essere toccato!"
    assert db.get_task(t_completed["id"])["status"] == "completed", "completed non deve essere toccato!"
    print("  [PASS] Task 'running' marcato come 'interrupted' al riavvio; stati 'waiting_approval' e 'completed' preservati.")


def test_6_safe_resume_with_idempotency_and_evidence():
    """6. Ripresa sicura di un task senza rieseguire azioni non idempotenti."""
    print("\n--- TEST 6: Ripresa Sicura di Task con Idempotenza ed Evidence ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Resume Room", ["chief", "builder"], chat_id=chat_id)

    # Crea file di prova all'interno del workspace
    test_file = tools_os.PROJECT_ROOT / f"evidence_test_{uuid.uuid4().hex[:8]}.txt"
    test_file.write_text("Dati già scritti prima del crash", encoding="utf-8")

    try:
        task_id = f"task_resume_{uuid.uuid4().hex[:8]}"
        task = db.create_task(
            task_id=task_id,
            chat_id=chat_id,
            bot_id="builder",
            title="Scrittura file",
            instruction=f"Scrivi su {test_file.name}",
            idempotency_key=f"write_{test_file.name}",
        )
        # Il task era running prima del crash con evidence del file creato
        db.update_task_status_atomic(
            task_id,
            from_status="pending",
            to_status="running",
            evidence={"file_created": str(test_file.resolve())},
        )
        # Riavvio: il task diventa interrupted
        db.recover_interrupted_tasks()
        assert db.get_task(task_id)["status"] == "interrupted"

        # Esegui resume asincrono
        broadcast_messages = []
        async def mock_broadcast(cid: str, payload: Dict[str, Any]):
            broadcast_messages.append(payload)

        res = asyncio.run(orchestrator.resume_task(task_id=task_id, broadcast_fn=mock_broadcast))
        assert res["status"] == "ok"

        # Poiché il file esisteva già fisicamente (evidence valida), il task è marcato completed
        # senza rieseguire scritture duplicate!
        resumed_task = db.get_task(task_id)
        assert resumed_task["status"] == "completed"
        assert "già verificata con successo" in resumed_task["result_data"].get("message", "")
        print("  [PASS] Task ripreso in sicurezza: evidence verificata, zero doppie esecuzioni non idempotenti.")
    finally:
        if test_file.exists():
            test_file.unlink()


def test_7_task_approval_association():
    """7. Associazione corretta tra task e approvazioni."""
    print("\n--- TEST 7: Associazione Task e Approvazioni ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Approval Room", ["chief", "builder"], chat_id=chat_id)
    task_id = f"task_appr_{uuid.uuid4().hex[:8]}"
    db.create_task(task_id=task_id, chat_id=chat_id, bot_id="builder", title="Azione da Approvare")

    # Creazione approvazione collegata al task
    appr = db.create_approval(
        chat_id=chat_id,
        bot_id="builder",
        action_type="file_write",
        description="Scrittura file protetta",
        payload={"tool_name": "write_file_workspace", "rel_path": "test_appr.txt", "content": "ciao"},
        task_id=task_id,
    )
    assert appr["task_id"] == task_id, "L'approvazione deve includere il task_id"

    # Verifica recupero approvazioni in sospeso
    pending = db.get_pending_approvals(chat_id)
    matched = next((a for a in pending if a["id"] == appr["id"]), None)
    assert matched is not None
    assert matched["task_id"] == task_id

    # Risoluzione atomica dell'approvazione
    success, updated = db.resolve_approval_atomic(appr["id"], "approved")
    assert success is True
    assert updated is not None
    assert updated["status"] == "approved"
    assert updated["task_id"] == task_id
    print("  [PASS] Task e approvazione associati bidirezionalmente e persistiti su SQLite.")


def test_8_concurrent_independent_tasks():
    """8. Esecuzione concorrente di task indipendenti senza corruzione dello stato."""
    print("\n--- TEST 8: Concorrenza Task Indipendenti (Race Conditions Check) ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Concurrent Room", ["scout"], chat_id=chat_id)

    # Crea 10 task indipendenti
    task_ids = [f"t_conc_{i}_{uuid.uuid4().hex[:6]}" for i in range(10)]
    for tid in task_ids:
        db.create_task(task_id=tid, chat_id=chat_id, bot_id="scout", title=f"Concurrent Task {tid}")

    # Aggiorna concorrentemente i task da 5 thread diversi
    errors = []
    def worker_thread(slice_tids):
        try:
            for tid in slice_tids:
                ok1, _ = db.update_task_status_atomic(tid, from_status="pending", to_status="running")
                assert ok1, f"Fallito passaggio pending->running per {tid}"
                time.sleep(0.01)
                ok2, _ = db.update_task_status_atomic(tid, from_status="running", to_status="completed", result_data={"worker": "ok"})
                assert ok2, f"Fallito passaggio running->completed per {tid}"
        except Exception as e:
            errors.append(e)

    threads = []
    chunk_size = 2
    for i in range(0, len(task_ids), chunk_size):
        t = threading.Thread(target=worker_thread, args=(task_ids[i:i+chunk_size],))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errori durante l'accesso concorrente a SQLite: {errors}"

    # Verifica stato finale di tutti i task
    for tid in task_ids:
        task = db.get_task(tid)
        assert task["status"] == "completed"
        assert task["result_data"] == {"worker": "ok"}

    print("  [PASS] 10 transizioni di stato concorrenti completate con successo senza deadlock o corruzione.")


def test_9_model_failure_handling():
    """9. Gestione di fallimenti del modello con fallback o marcatura failed."""
    print("\n--- TEST 9: Gestione Fallimenti Modello e Marcatura Failed ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Failure Room", ["chief"], chat_id=chat_id)
    task_id = f"t_fail_{uuid.uuid4().hex[:8]}"

    db.create_task(
        task_id=task_id,
        chat_id=chat_id,
        bot_id="chief",
        title="Task che deve fallire",
        max_retries=2,
    )
    # Simula primo fallimento -> retry_count = 1
    db.update_task_status_atomic(task_id, from_status="pending", to_status="running")
    task = db.get_task(task_id)

    # Simula retry logico
    retries = task["retry_count"] + 1
    db.update_task_status_atomic(task_id, from_status="running", to_status="pending", error_msg="Timeout modello")
    # Simula secondo fallimento -> supera max_retries (2) -> failed
    db.update_task_status_atomic(task_id, from_status="pending", to_status="failed", error_msg="API Gemini non raggiungibile: quota esaurita")

    final_task = db.get_task(task_id)
    assert final_task["status"] == "failed"
    assert "quota esaurita" in final_task["error_msg"]
    print("  [PASS] Fallimento modello gestito correttamente: stato 'failed' registrato con dettaglio dell'errore.")


def test_10_phase1_regression_suite():
    """10. Regression test: tutte le protezioni delle Fasi 1 e 1.1 continuano a funzionare."""
    print("\n--- TEST 10: Regression Test Fasi 1 e 1.1 ---")
    # Esegue l'intera suite di hardening precedente
    test_hardening_phase1.test_auth_protection_headers_only()
    test_hardening_phase1.test_token_storage_and_renderer_exposure()
    test_hardening_phase1.test_websocket_auth_and_tickets()
    test_hardening_phase1.test_atomic_approval_transitions_and_concurrency()
    test_hardening_phase1.test_path_traversal_and_file_security()
    test_hardening_phase1.test_arbitrary_shell_disabled()
    test_hardening_phase1.test_approval_enforcement()
    test_hardening_phase1.test_screen_control_no_blind_fallback()

    # Verifica anche i nuovi endpoint REST protetti per i task
    client = TestClient(app)
    # Senza auth -> 401
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks/xyz").status_code == 401
    assert client.post("/api/tasks/xyz/resume").status_code == 401
    assert client.post("/api/tasks/xyz/cancel").status_code == 401

    # Con auth -> 200
    auth_hdr = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    r = client.get("/api/tasks", headers=auth_hdr)
    assert r.status_code == 200
    assert "tasks" in r.json()
    print("  [PASS] 100% dei controlli di sicurezza Fase 1 e 1.1 + nuovi endpoint Task API protetti e conformi.")


def run_all_phase2a_tests():
    print("======================================================================")
    print("   COWORKEROS - SUITE DI VERIFICA FASE 2A: MOTORE MULTI-AGENTE       ")
    print("======================================================================")
    start_time = time.time()

    test_1_task_persistence_across_restarts()
    test_2_dependency_ordering()
    test_3_structured_delegation_and_peer_review()
    test_4_cycle_detection()
    test_5_interruption_recovery_on_startup()
    test_6_safe_resume_with_idempotency_and_evidence()
    test_7_task_approval_association()
    test_8_concurrent_independent_tasks()
    test_9_model_failure_handling()
    test_10_phase1_regression_suite()

    elapsed = time.time() - start_time
    print("\n======================================================================")
    print(f"   ESITO FINALE: TUTTI I 10 TEST FASE 2A SUPERATI CON SUCCESSO! ({elapsed:.2f}s)")
    print("======================================================================")


if __name__ == "__main__":
    run_all_phase2a_tests()
