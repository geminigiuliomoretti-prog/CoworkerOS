"""
CoworkerOS - Suite di Test Automatizzati Fase 2A.1: Affidabilità Task Engine
Verifica dei requisiti:
1. File preesistente ma con contenuto errato (mismatch rilevato, richiesta approvazione, non completato).
2. File modificato correttamente prima di un crash (hash verificato, completamento idempotente).
3. Azione desktop con esito sconosciuto (esito ignoto -> waiting_approval, nessun clic cieco).
4. Delega Chief → Builder → Chief legittima (collaborazione con progresso consentita).
5. Ciclo ripetitivo senza progresso (stesso task ping-pong bloccato).
6. Ripresa dopo crash senza doppia esecuzione (verifica evidenze, zero mutazioni duplicate).
"""

import os
import sys
import time
import uuid
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import database as db
import tools_os
from agent_engine import orchestrator


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def test_file_preesistente_contenuto_errato():
    """1. File preesistente ma con contenuto errato."""
    print("\n--- TEST 1: File preesistente con contenuto errato ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Mismatch Room", ["chief", "builder"], chat_id=chat_id)

    test_file = tools_os.PROJECT_ROOT / f"test_mismatch_{uuid.uuid4().hex[:6]}.txt"
    # Scrivi contenuto preesistente errato
    test_file.write_text("VECCHIO_CONTENUTO_NON_VALIDO", encoding="utf-8")

    try:
        expected_content = "NUOVO_CONTENUTO_RICHIESTO_DALL_UTENTE"
        expected_hash = hashlib.sha256(expected_content.encode("utf-8")).hexdigest()

        task_id = f"task_mismatch_{uuid.uuid4().hex[:8]}"
        db.create_task(
            task_id=task_id,
            chat_id=chat_id,
            bot_id="builder",
            title="Scrittura file con verifica hash",
            instruction=f"Scrivi su {test_file.name}",
        )
        # Il task era running prima del crash con metadati dell'azione richiesta
        db.update_task_status_atomic(
            task_id,
            new_status="running",
            evidence={
                "tool": "manage_files",
                "action": "write",
                "path": test_file.name,
                "file_created": str(test_file.resolve()),
                "expected_content": expected_content,
                "expected_hash": expected_hash,
            },
        )
        # Crash simulation -> task diventa interrupted
        db.recover_interrupted_tasks()
        assert db.get_task(task_id)["status"] == "interrupted"

        # Esecuzione resume
        res = asyncio.run(orchestrator.resume_task(task_id=task_id))

        # VERIFICA: Il task NON deve essere completato!
        # Deve risultare in waiting_approval con richiesta esplicita di verifica
        assert res["status"] == "waiting_approval"
        assert res.get("verdict") == "MISMATCH"
        assert res.get("requires_verification") is True

        task_after = db.get_task(task_id)
        assert task_after["status"] == "waiting_approval"
        assert "contenuto errato o difforme" in task_after["error_msg"]

        # Il file su disco non deve essere stato modificato
        assert test_file.read_text(encoding="utf-8") == "VECCHIO_CONTENUTO_NON_VALIDO"
        print("  [PASS] File con hash errato rilevato: task impostato a waiting_approval, nessuna sovrascrittura cieca.")
    finally:
        if test_file.exists():
            test_file.unlink()


def test_file_modificato_correttamente_prima_del_crash():
    """2. File modificato correttamente prima di un crash."""
    print("\n--- TEST 2: File modificato correttamente prima di un crash ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Crash Room", ["chief", "builder"], chat_id=chat_id)

    test_file = tools_os.PROJECT_ROOT / f"test_correct_{uuid.uuid4().hex[:6]}.txt"
    correct_content = "DATI_CORRETTI_SCRITTI_PRIMA_DEL_CRASH_98765"
    test_file.write_text(correct_content, encoding="utf-8")
    expected_hash = hashlib.sha256(correct_content.encode("utf-8")).hexdigest()

    try:
        task_id = f"task_crash_{uuid.uuid4().hex[:8]}"
        db.create_task(
            task_id=task_id,
            chat_id=chat_id,
            bot_id="builder",
            title="File già scritto prima del crash",
            instruction=f"Scrivi su {test_file.name}",
        )
        db.update_task_status_atomic(
            task_id,
            new_status="running",
            evidence={
                "tool": "manage_files",
                "action": "write",
                "path": test_file.name,
                "file_created": str(test_file.resolve()),
                "expected_content": correct_content,
                "expected_hash": expected_hash,
            },
        )
        # Riavvio: task passa a interrupted
        db.recover_interrupted_tasks()
        assert db.get_task(task_id)["status"] == "interrupted"

        # Resume
        res = asyncio.run(orchestrator.resume_task(task_id=task_id))
        assert res["status"] == "ok"
        assert res.get("verdict") == "VERIFIED"

        task_after = db.get_task(task_id)
        assert task_after["status"] == "completed"
        assert task_after["result"]["verified"] is True
        print("  [PASS] File con hash verificato: completamento riconosciuto senza rieseguire scritture.")
    finally:
        if test_file.exists():
            test_file.unlink()


def test_azione_desktop_esito_sconosciuto():
    """3. Azione desktop con esito sconosciuto."""
    print("\n--- TEST 3: Azione desktop con esito sconosciuto ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Desktop Room", ["chief", "builder"], chat_id=chat_id)

    task_id = f"task_desk_{uuid.uuid4().hex[:8]}"
    db.create_task(
        task_id=task_id,
        chat_id=chat_id,
        bot_id="builder",
        title="Clic desktop interrotto",
        instruction="Clicca sul pulsante Invia in Chrome",
    )
    # L'azione desktop è stata avviata ma prima di confermare il nuovo stato si è interrotta
    db.update_task_status_atomic(
        task_id,
        new_status="running",
        evidence={
            "tool": "click_screen_element",
            "real_coords": [520, 680],
            "window": "Google Chrome",
            "post_inspection_verified": False,
        },
    )
    # Riavvio: task interrupted
    db.recover_interrupted_tasks()
    assert db.get_task(task_id)["status"] == "interrupted"

    # Resume del task
    res = asyncio.run(orchestrator.resume_task(task_id=task_id))

    # VERIFICA: L'azione fisica non deve essere rieseguita alla cieca né data per completata!
    assert res["status"] == "waiting_approval"
    assert res.get("verdict") == "UNVERIFIABLE"
    assert res.get("requires_verification") is True

    task_after = db.get_task(task_id)
    assert task_after["status"] == "waiting_approval"
    assert "esito fisico sconosciuto o non verificabile" in task_after["error_msg"]
    print("  [PASS] Azione desktop non verificabile: bloccata riesecuzione automatica, impostato waiting_approval.")


def test_delega_chief_builder_chief_legittima():
    """4. Delega Chief -> Builder -> Chief legittima."""
    print("\n--- TEST 4: Delega Chief -> Builder -> Chief legittima ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Collab Room", ["chief", "builder"], chat_id=chat_id)

    # Step 1: Chief crea task iniziale
    t1 = db.create_task(
        task_id=f"t1_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        bot_id="chief",
        title="Pianificazione feature",
        instruction="Analizza i requisiti e delega la scrittura a Builder",
    )
    # Step 2: Builder riceve sotto-task da Chief e lo completa con progresso/evidenza
    t2 = db.create_task(
        task_id=f"t2_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        parent_task_id=t1["id"],
        bot_id="builder",
        title="Implementazione feature",
        instruction="Crea file component.jsx",
    )
    db.update_task_status_atomic(
        t2["id"],
        new_status="completed",
        evidence={"file_created": "component.jsx", "verified": True},
        result_data={"summary": "File component.jsx creato con successo"},
    )

    # Step 3: Builder passa la palla di nuovo a Chief per la revisione finale
    # La delega Chief -> Builder -> Chief con progresso DEVE essere considerata legittima
    is_cycle = orchestrator._is_cycle_detected(
        parent_task_id=t2["id"],
        target_bot_id="chief",
        instruction="Ho completato component.jsx. Chief esegui la code review finale e notifica l'utente.",
        caller_bot_id="builder",
    )
    assert is_cycle is False, "Delega legittima Chief->Builder->Chief erroneamente bloccata come ciclo!"
    print("  [PASS] Delega Chief → Builder → Chief con progresso riconosciuta come collaborazione legittima.")


def test_ciclo_ripetitivo_senza_progresso():
    """5. Ciclo ripetitivo senza progresso."""
    print("\n--- TEST 5: Ciclo ripetitivo senza progresso ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Loop Room", ["chief", "builder"], chat_id=chat_id)

    # Step 1: Chief assegna a Builder un task
    t1 = db.create_task(
        task_id=f"t1_loop_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        bot_id="chief",
        title="Task ripetitivo",
        instruction="Scrivi script main.py",
    )
    # Step 2: Builder senza produrre progresso/risultati tenta di rimandare a Chief lo stesso identico task
    t2 = db.create_task(
        task_id=f"t2_loop_{uuid.uuid4().hex[:8]}",
        chat_id=chat_id,
        parent_task_id=t1["id"],
        bot_id="builder",
        title="Task ripetitivo",
        instruction="Scrivi script main.py",
    )
    # t2 è ancora in pending/running e non ha prodotto alcun risultato o evidenza

    is_cycle = orchestrator._is_cycle_detected(
        parent_task_id=t2["id"],
        target_bot_id="chief",
        instruction="Scrivi script main.py",
        caller_bot_id="builder",
    )
    assert is_cycle is True, "Ciclo ripetitivo identico senza progresso NON è stato bloccato!"

    # Test auto-delega diretta: Builder -> Builder
    is_self_cycle = orchestrator._is_cycle_detected(
        parent_task_id=t2["id"],
        target_bot_id="builder",
        instruction="Fallo tu stesso",
        caller_bot_id="builder",
    )
    assert is_self_cycle is True, "Auto-delega non rilevata come ciclo!"

    print("  [PASS] Ciclo ripetitivo senza progresso e auto-delega rilevati e bloccati con successo.")


def test_ripresa_dopo_crash_senza_doppia_esecuzione():
    """6. Ripresa dopo crash senza doppia esecuzione."""
    print("\n--- TEST 6: Ripresa dopo crash senza doppia esecuzione ---")
    chat_id = f"test_chat_{uuid.uuid4().hex[:8]}"
    db.create_chat("Idempotency Room", ["builder"], chat_id=chat_id)

    test_file = tools_os.PROJECT_ROOT / f"test_idemp_{uuid.uuid4().hex[:6]}.txt"
    initial_content = "CONTENUTO_ORIGINALE_SCRITTO_12345"
    test_file.write_text(initial_content, encoding="utf-8")
    expected_hash = hashlib.sha256(initial_content.encode("utf-8")).hexdigest()

    # Rileva mtime iniziale del file
    initial_mtime = test_file.stat().st_mtime_ns

    try:
        task_id = f"t_idemp_{uuid.uuid4().hex[:8]}"
        db.create_task(
            task_id=task_id,
            chat_id=chat_id,
            bot_id="builder",
            title="Scrittura idempotente",
            instruction=f"Scrivi su {test_file.name}",
            idempotency_key=f"idemp_{test_file.name}",
        )
        db.update_task_status_atomic(
            task_id,
            new_status="running",
            evidence={
                "tool": "manage_files",
                "action": "write",
                "path": test_file.name,
                "file_created": str(test_file.resolve()),
                "expected_content": initial_content,
                "expected_hash": expected_hash,
            },
        )
        # Crash
        db.recover_interrupted_tasks()

        # Prima ripresa: rileva completamento tramite evidenze
        res1 = asyncio.run(orchestrator.resume_task(task_id=task_id))
        assert res1["status"] == "ok"
        assert res1["verdict"] == "VERIFIED"

        # Seconda ripresa (replay): non deve rieseguire nulla
        res2 = asyncio.run(orchestrator.resume_task(task_id=task_id))
        assert res2["status"] == "ok"
        assert "già completato" in res2["message"].lower()

        # Verifica che il file non sia stato toccato o riscritto (mtime invariato)
        final_mtime = test_file.stat().st_mtime_ns
        assert final_mtime == initial_mtime, "Il file è stato riscritto inutilmente durante la ripresa!"
        print("  [PASS] Ripresa idempotente: file non riscritto (mtime invariato), nessuna doppia esecuzione.")
    finally:
        if test_file.exists():
            test_file.unlink()


def run_all_reliability_tests():
    print("======================================================================")
    print("   COWORKEROS - VERIFICA FASE 2A.1: AFFIDABILITÀ TASK ENGINE         ")
    print("======================================================================")
    start_time = time.time()

    test_file_preesistente_contenuto_errato()
    test_file_modificato_correttamente_prima_del_crash()
    test_azione_desktop_esito_sconosciuto()
    test_delega_chief_builder_chief_legittima()
    test_ciclo_ripetitivo_senza_progresso()
    test_ripresa_dopo_crash_senza_doppia_esecuzione()

    elapsed = time.time() - start_time
    print("\n======================================================================")
    print(f"   ESITO FINALE: TUTTI I TEST FASE 2A.1 SUPERATI CON SUCCESSO! ({elapsed:.2f}s)")
    print("======================================================================")


if __name__ == "__main__":
    run_all_reliability_tests()
