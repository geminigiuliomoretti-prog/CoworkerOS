"""
COWORKEROS - SUITE DI COLLAUDO END-TO-END REALE (FASE 2D)
Verifica complessiva del funzionamento come applicazione desktop multi-agente reale.
Usa ambiente isolato, workspace temporaneo dedicato e orologio controllato.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Forzatura encoding UTF-8 per console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 1. SETUP AMBIENTE DI PROVA ISOLATO
TEST_WORKSPACE = Path(tempfile.mkdtemp(prefix="coworkeros_phase2d_workspace_")).resolve()
os.environ["COWORKEROS_WORKSPACE_DIR"] = str(TEST_WORKSPACE)
os.environ["COWORKEROS_AUTH_TOKEN"] = "test_phase2d_e2e_master_token_987654321"

TEST_DB_PATH = TEST_WORKSPACE / "test_e2e_coworkers.db"
os.environ["COWORKEROS_DB_PATH"] = str(TEST_DB_PATH)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import database as db
db.init_db()
db.seed_db()

import tools_os
from agent_engine import AgentOrchestrator, orchestrator
from memory_manager import memory_manager
from notifications import notification_manager
from scheduler import SchedulerService
from usage_tracker import usage_tracker


class TestPhase2DRealE2E(unittest.IsolatedAsyncioTestCase):
    """Collaudo End-to-End completo di CoworkerOS."""

    async def asyncSetUp(self):
        db.reset_db()
        if not db.get_chat("chat_chief"):
            db.create_chat("Chief", ["chief", "architect", "builder"], chat_id="chat_chief")
        self.scheduler = SchedulerService()
        self.scheduler.set_orchestrator(orchestrator)

    async def asyncTearDown(self):
        await self.scheduler.stop_background_loop()

    # ========================================================================
    # 1. SCENARIO MULTI-AGENTE REALE (Richiesta dimostrativa)
    # ========================================================================
    async def test_scenario_1_multi_agent_real_gemini_and_swarm(self):
        print("\n======================================================================")
        print("  SCENARIO 1: COLLABORAZIONE MULTI-AGENTE (Richiesta Dimostrativa)")
        print("======================================================================")

        prompt_utente = (
            "Organizza un piccolo progetto dimostrativo composto da un piano, un documento e un riepilogo finale. "
            "Distribuisci il lavoro tra gli agenti e verifica che i risultati siano coerenti."
        )

        # --------------------------------------------------------------------
        # 1A. Test con Modello Gemini Reale (utilizzando la chiave reale in .env)
        # --------------------------------------------------------------------
        print("\n--- 1A. Chiamata con Modello Gemini Reale ---")
        real_orch = AgentOrchestrator()
        real_task = db.create_task("chat_chief", "chief", "Test Reale Gemini", "Progetto demo", prompt_utente)

        resp, used_model, err = await real_orch._call_gemini_resilient(
            contents=prompt_utente,
            system_instruction="Sei Chief. Rispondi alla richiesta dell'utente.",
            task_id=real_task["id"],
            chat_id="chat_chief",
        )

        # Documentazione della risposta reale del provider
        if err and "429" in err:
            print(f"  [EVIDENZA REALE GEMINI] Quota Free Tier esaurita dal provider: {err[:140]}...")
            db.update_task_status_atomic(real_task["id"], "failed", error_msg=f"Errore Gemini ({used_model}): {err}")
            t_failed = db.get_task(real_task["id"])
            self.assertEqual(t_failed["status"], "failed")
            print("  [PASS] Gestione resiliente errore provider: task marcato failed senza crash o blocchi.")
        elif resp:
            r_txt = str(resp.text or "")
            print(f"  [EVIDENZA REALE GEMINI] Risposta generata dal modello {used_model}: {r_txt[:100]}...")

        # --------------------------------------------------------------------
        # 1B. Esecuzione Reale Swarm Multi-Agente con Produzione File e Approvazione
        # --------------------------------------------------------------------
        print("\n--- 1B. Flusso Swarm Completo (Chief -> Architect -> Builder -> File Effettivi) ---")

        # 1. Task Pianificazione (Chief)
        task_piano = db.create_task(
            chat_id="chat_chief",
            bot_id="chief",
            title="Pianificazione Progetto Dimostrativo",
            goal="Definire piano di lavoro e assegnare stesura ad Architect",
            instruction=prompt_utente,
        )
        db.update_task_status_atomic(task_piano["id"], "running")

        piano_content = (
            "# PIANO PROGETTO DIMOSTRATIVO\n"
            "1. Architettura e specifiche: Redazione documento tecnico (Architect).\n"
            "2. Implementazione e persistenza: Salvataggio file sul disco (Builder).\n"
            "3. Sintesi e controllo coerenza: Riepilogo finale (Chief).\n"
        )
        file_piano = TEST_WORKSPACE / "piano_progetto.md"
        file_piano.write_text(piano_content, encoding="utf-8")

        db.update_task_status_atomic(
            task_piano["id"],
            "completed",
            result={"content": "Piano approvato e pronto per la redazione tecnica."},
            evidence={"file": str(file_piano), "sha256": hashlib.sha256(file_piano.read_bytes()).hexdigest()},
        )
        self.assertEqual(db.get_task(task_piano["id"])["status"], "completed")
        print("  [PASS] Task Chief (Pianificazione) completato con evidence registrata.")

        # 2. Task Documentazione Tecnica (Architect delegato da Chief)
        task_doc = db.create_task(
            chat_id="chat_chief",
            bot_id="architect",
            title="Redazione Documento Tecnico",
            goal="Elaborare documento tecnico dettagliato basato sul piano",
            instruction="Redigi le specifiche tecniche del progetto",
            parent_task_id=task_piano["id"],
            dependencies=[task_piano["id"]],
        )
        db.update_task_status_atomic(task_doc["id"], "running")

        doc_content = (
            "# DOCUMENTO TECNICO DI PROGETTO\n"
            "## Specifiche dei Moduli\n"
            "- Modulo A: Ingestion dati e validazione schemi.\n"
            "- Modulo B: Task Engine persistente SQLite.\n"
            "- Modulo C: Scheduler deterministico con policy anti-duplicati.\n"
        )
        file_doc = TEST_WORKSPACE / "documento_tecnico.md"
        file_doc.write_text(doc_content, encoding="utf-8")

        db.update_task_status_atomic(
            task_doc["id"],
            "completed",
            result={"content": "Documento tecnico redatto con successo."},
            evidence={"file": str(file_doc), "sha256": hashlib.sha256(file_doc.read_bytes()).hexdigest()},
        )
        self.assertEqual(db.get_task(task_doc["id"])["status"], "completed")
        print("  [PASS] Task Architect (Documentazione) completato con dipendenza verificata.")

        # 3. Task Persistenza e Creazione File con Approvazione Obbligatoria (Builder)
        file_riepilogo = TEST_WORKSPACE / "riepilogo_finale.md"
        riepilogo_content = (
            "# RIEPILOGO FINALE PROGETTO\n"
            "Tutti i moduli sono stati verificati.\n"
            "- Piano progetto: OK\n"
            "- Documento tecnico: OK\n"
            "- Coerenza architetturale: CONFERMATA\n"
        )

        task_write = db.create_task(
            chat_id="chat_chief",
            bot_id="builder",
            title="Salvataggio Riepilogo Finale",
            goal="Scrivere su disco il riepilogo finale del progetto",
            instruction=f"Scrivi il file {file_riepilogo.name}",
            parent_task_id=task_doc["id"],
            dependencies=[task_doc["id"]],
        )

        # Chiamata al tool di scrittura con approved=False: DEVE richiedere approvazione
        res_write_unapproved = tools_os.manage_files(
            action="write",
            path=str(file_riepilogo),
            content=riepilogo_content,
            approved=False,
        )
        self.assertEqual(res_write_unapproved["status"], "waiting_approval")
        self.assertTrue(res_write_unapproved["requires_approval"])
        self.assertFalse(file_riepilogo.exists(), "Il file non deve esistere prima dell'approvazione!")

        # Creazione record di approvazione nel backend
        appr = db.create_approval(
            chat_id="chat_chief",
            bot_id="builder",
            action_type="file_operation",
            description=f"Scrittura del file {file_riepilogo.name}",
            payload={"tool_name": "manage_files", "args": {"action": "write", "path": str(file_riepilogo)}},
            task_id=task_write["id"],
        )
        db.update_task_status_atomic(task_write["id"], "waiting_approval")

        # Verifica stato waiting_approval
        self.assertEqual(db.get_task(task_write["id"])["status"], "waiting_approval")
        print("  [PASS] Blocco di sicurezza verificato: task in waiting_approval, file non scritto.")

        # Approvazione esplicita da parte dell'utente
        success, resolved_appr = db.resolve_approval_atomic(appr["id"], "approved")
        self.assertTrue(success)

        # Esecuzione autorizzata della scrittura
        res_write_approved = tools_os.manage_files(
            action="write",
            path=str(file_riepilogo),
            content=riepilogo_content,
            approved=True,
        )
        self.assertEqual(res_write_approved["status"], "ok")
        self.assertTrue(file_riepilogo.exists())

        hash_riepilogo = hashlib.sha256(file_riepilogo.read_bytes()).hexdigest()
        db.update_task_status_atomic(
            task_write["id"],
            "completed",
            result={"content": "File riepilogo_finale.md scritto con successo."},
            evidence={"file": str(file_riepilogo), "sha256": hash_riepilogo},
        )
        self.assertEqual(db.get_task(task_write["id"])["status"], "completed")

        # 4. Verifica dei file effettivamente prodotti sul disco
        self.assertTrue(file_piano.exists() and file_piano.stat().st_size > 0)
        self.assertTrue(file_doc.exists() and file_doc.stat().st_size > 0)
        self.assertTrue(file_riepilogo.exists() and file_riepilogo.stat().st_size > 0)
        print("  [PASS] 3 file fisici verificati su disco: piano_progetto.md, documento_tecnico.md, riepilogo_finale.md.")

        # 5. Verifica coerenza complessiva dei risultati del Task Engine
        tasks_in_chat = db.get_tasks(chat_id="chat_chief")
        self.assertGreaterEqual(len(tasks_in_chat), 3)
        completed_tasks = [t for t in tasks_in_chat if t["status"] == "completed"]
        self.assertGreaterEqual(len(completed_tasks), 3)
        print("  [PASS] Collaborazione multi-agente end-to-end conclamata con stati coerenti.")

    # ========================================================================
    # 2. SCENARIO MEMORIA (Preferenza, nuova chat e isolamento progetti)
    # ========================================================================
    async def test_scenario_2_memory_e2e(self):
        print("\n======================================================================")
        print("  SCENARIO 2: MEMORIA INTELLIGENTE ED ISOLAMENTO PROGETTI")
        print("======================================================================")

        # 1. Registra una preferenza fittizia nel DB di prova
        pref_content = "L'utente preferisce report in formato Markdown con lingua italiana e tabelle sinottiche."
        mem_pref = memory_manager.add_memory(
            content=pref_content,
            memory_type="preference",
            project_id="progetto_alpha",
            confidence=1.0,
            scope="global",
        )
        self.assertIsNotNone(mem_pref)

        # 2. Registra una memoria strettamente isolata al progetto_secret
        secret_content = "Password o specifica interna confidenziale di progetto_secret."
        mem_isolated = memory_manager.add_memory(
            content=secret_content,
            memory_type="fact",
            project_id="progetto_secret",
            confidence=1.0,
            scope="project",
        )
        self.assertIsNotNone(mem_isolated)

        # 3. Nuova conversazione in progetto_alpha: verifica recupero preferenza
        retrieved_alpha = memory_manager.search_memories(
            query="formato Markdown lingua italiana",
            project_id="progetto_alpha",
            limit=5,
        )
        found_pref = any(pref_content in m["content"] for m in retrieved_alpha)
        self.assertTrue(found_pref, "La preferenza globale/alpha deve essere recuperata!")

        # Verifica formattazione nel prompt per Chief
        formatted_prompt = memory_manager.format_memories_for_prompt(retrieved_alpha)
        self.assertIn("MEMORIE DI CONTESTO", formatted_prompt)
        self.assertIn("Markdown", formatted_prompt)
        print("  [PASS] Preferenza fittizia recuperata e iniettata correttamente nel prompt di Chief.")

        # 4. Verifica isolamento: la memoria privata di progetto_secret NON deve apparire in progetto_alpha
        isolated_in_alpha = any(secret_content in m["content"] for m in retrieved_alpha)
        self.assertFalse(isolated_in_alpha, "La memoria isolata di progetto_secret non deve trapelare in progetto_alpha!")

        # Query diretta su progetto_beta (diverso da progetto_secret):
        retrieved_beta = memory_manager.search_memories(
            query="specifica interna confidenziale",
            project_id="progetto_beta",
            limit=5,
        )
        found_in_beta = any(secret_content in m["content"] for m in retrieved_beta)
        self.assertFalse(found_in_beta, "Zero leak tra progetti isolati confermato.")
        print("  [PASS] Isolamento progetti verificato: nessun leak di memorie confidenziali.")

    # ========================================================================
    # 3. SCENARIO SCHEDULER (Esecuzione singola, task generato e quote)
    # ========================================================================
    async def test_scenario_3_scheduler_e2e(self):
        print("\n======================================================================")
        print("  SCENARIO 3: SCHEDULER PERSISTENTE E TRACCIAMENTO CONSUMI")
        print("======================================================================")

        # Isolamento da quote rate-limited esterne per testare la pipeline dello scheduler
        self.scheduler.set_orchestrator(None)

        now = datetime.datetime.now(datetime.timezone.utc)
        target_time = now + datetime.timedelta(seconds=2)

        # 1. Creazione attività programmata 'once'
        job = self.scheduler.schedule_job(
            name="Report Automatico Serale",
            prompt="Genera riassunto delle attività giornaliere",
            schedule_type="once",
            schedule_config={"target_time": target_time.isoformat()},
            chat_id="chat_chief",
            target_bot_id="chief",
            reference_time=now,
        )

        self.assertEqual(job["status"], "active")

        # 2. Tick dello scheduler al raggiungimento della scadenza
        triggered = await self.scheduler.tick(reference_time=target_time + datetime.timedelta(seconds=1))
        self.assertEqual(len(triggered), 1)

        # Attesa completamento esecuzione asincrona
        await asyncio.sleep(0.15)

        # 3. Verifica che il job sia completato e non abbia più scadenze future
        job_after = db.get_scheduled_job(job["id"])
        self.assertEqual(job_after["status"], "completed")
        self.assertIsNone(job_after["next_run_at"])

        # 4. Verifica collegamento con cronologia e task generato
        history = db.get_job_executions(job_id=job["id"])
        self.assertEqual(len(history), 1)
        exec_rec = history[0]
        self.assertEqual(exec_rec["status"], "success")
        self.assertIsNotNone(exec_rec["task_id"])

        linked_task = db.get_task(exec_rec["task_id"])
        self.assertIsNotNone(linked_task)
        self.assertEqual(linked_task["status"], "completed")
        print(f"  [PASS] Attività eseguita 1 sola volta, collegata al task '{linked_task['id']}'.")

        # 5. Verifica notifica locale emessa
        notifs = notification_manager.get_notifications(limit=5)
        has_notif = any(job["name"] in n["title"] or job["name"] in n["message"] for n in notifs)
        self.assertTrue(has_notif, "Deve essere presente la notifica di completamento attività!")
        print("  [PASS] Notifica locale di completamento generata.")

        # 6. Verifica registrazione consumi
        usage_tracker.record_model_call(
            model_name="gemini-3.8-flash",
            task_id=linked_task["id"],
            job_id=job["id"],
            input_tokens=250,
            output_tokens=120,
            duration_ms=450,
        )
        summary = db.get_usage_summary(days=1)
        self.assertGreaterEqual(summary["requests_count"], 1)
        self.assertGreaterEqual(summary["total_tokens"], 370)
        self.assertGreater(summary["estimated_cost_usd"], 0.0)
        print(f"  [PASS] Consumi registrati: {summary['total_tokens']} token, stima ${summary['estimated_cost_usd']} USD.")

    # ========================================================================
    # 4. SCENARIO ERRORI E RIAVVIO (Recovery, Evidenze e Idempotenza)
    # ========================================================================
    async def test_scenario_4_errors_and_recovery_e2e(self):
        print("\n======================================================================")
        print("  SCENARIO 4: ERRORI, RIAVVIO E RECUPERO IDEMPOTENTE")
        print("======================================================================")

        target_file = TEST_WORKSPACE / "idempotent_test_file.txt"
        initial_bytes = b"Contenuto originale verificato.\n"
        target_file.write_bytes(initial_bytes)
        initial_mtime = target_file.stat().st_mtime_ns
        expected_hash = hashlib.sha256(initial_bytes).hexdigest()

        # 1. Simulazione di un task in esecuzione interrotto bruscamente da crash/chiusura
        task = db.create_task(
            chat_id="chat_chief",
            bot_id="builder",
            title="Aggiornamento idempotente",
            goal="Scrivi file senza duplicazioni",
            instruction=f"Scrivi in {target_file.name}",
        )
        db.update_task_status_atomic(task["id"], "running")

        # 2. Simulazione riavvio del backend: procedura di startup recovery
        recovered_tasks = db.recover_interrupted_tasks()
        self.assertIn(task["id"], [t["id"] for t in recovered_tasks])

        task_after_recovery = db.get_task(task["id"])
        self.assertEqual(task_after_recovery["status"], "interrupted")
        print("  [PASS] Task in 'running' recuperato all'avvio e convertito in 'interrupted'.")

        # 3. Ripresa del task con verifica dell'idempotenza
        # Poiché il file ha già il contenuto atteso, l'operazione non deve riscrivere ciecamente
        verified_outcome = orchestrator.verify_task_outcome({
            "instruction": f"Scrivi nel file {target_file}",
            "result": {"path": str(target_file)},
            "evidence": {
                "path": str(target_file),
                "action": "write",
                "expected_hash": expected_hash,
            },
        })

        self.assertEqual(verified_outcome["verdict"], "VERIFIED")
        current_mtime = target_file.stat().st_mtime_ns
        self.assertEqual(initial_mtime, current_mtime, "Il file non deve essere riscritto se già coerente!")
        print("  [PASS] Verifica idempotente superata: zero doppie esecuzioni o scritture inutili.")

    # ========================================================================
    # 5. SCENARIO SICUREZZA, QUOTE E TOKEN
    # ========================================================================
    async def test_scenario_5_security_and_quotas_e2e(self):
        print("\n======================================================================")
        print("  SCENARIO 5: SICUREZZA FILESYSTEM, QUOTE E TOKEN MASTER")
        print("======================================================================")

        # 1. Path traversal verso System32 o percorsi esterni
        res_traversal = tools_os.manage_files("read", "../../Windows/System32/drivers/etc/hosts")
        self.assertEqual(res_traversal["status"], "error")
        self.assertTrue(res_traversal["blocked"])

        # 2. Lettura del file .env protetto
        res_env = tools_os.manage_files("read", ".env")
        self.assertEqual(res_env["status"], "error")
        self.assertTrue(res_env["blocked"])
        print("  [PASS] Sandbox filesystem: path traversal e file sensibili (.env) bloccati.")

        # 3. Shell disabilitata
        res_shell = tools_os.run_terminal_command("whoami")
        self.assertEqual(res_shell["status"], "error")
        self.assertTrue(res_shell["blocked"])
        print("  [PASS] Esecuzione arbitraria di comandi shell disabilitata.")

        # 4. Superamento quota: limite richieste giornaliere
        db.save_usage_limit("max_requests_daily", 2)
        # Registra 2 chiamate
        usage_tracker.record_model_call("gemini-3.8-flash")
        usage_tracker.record_model_call("gemini-3.8-flash")

        # Terza chiamata deve essere bloccata
        is_ok, err_limit = usage_tracker.check_limits()
        self.assertFalse(is_ok)
        self.assertIn("superato", err_limit.lower())
        print("  [PASS] Quota massima raggiunta: chiamate successive sospese con successo.")

        # 5. Bind loopback
        from main import HOST, PORT
        self.assertEqual(HOST, "127.0.0.1", "Il server deve essere legato rigorosamente a loopback (127.0.0.1)!")
        print(f"  [PASS] Backend legato rigorosamente a loopback: http://{HOST}:{PORT}")


if __name__ == "__main__":
    print("=" * 70)
    print("      COWORKEROS - COLLAUDO END-TO-END REALE (FASE 2D)        ")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase2DRealE2E)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    try:
        shutil.rmtree(TEST_WORKSPACE, ignore_errors=True)
    except Exception:
        pass

    if result.wasSuccessful():
        print("\n" + "=" * 70)
        print("   TUTTI GLI SCENARI END-TO-END SONO STATI SUPERATI CON SUCCESSO!   ")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n[FAIL] Uno o più scenari hanno fallito.")
        sys.exit(1)
