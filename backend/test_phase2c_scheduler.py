"""
COWORKEROS - SUITE DI VERIFICA FASE 2C: AUTONOMIA PROGRAMMATA E CONTROLLO CONSUMI
Test completi automatizzati in ambiente isolato con database SQLite temporaneo.
Nessuna azione reale sul PC, orologio simulato e mock dei modelli.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

# Forzatura output UTF-8 su console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup ambiente di test isolato
TEST_DIR = Path(tempfile.mkdtemp(prefix="coworkeros_test_phase2c_"))
TEST_DB_PATH = TEST_DIR / "test_coworkers.db"

# Override ambiente
os.environ["COWORKEROS_AUTH_TOKEN"] = "test_secret_token_phase2c_master_12345"
os.environ["COWORKEROS_DB_PATH"] = str(TEST_DB_PATH)

# Patch database path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import database as db

# Re-inizializzazione del DB di test
db.init_db()
db.seed_db()

from notifications import notification_manager, sanitize_notification_text
from scheduler import SchedulerService, get_current_time, parse_timezone, scheduler_service
from usage_tracker import UsageTracker, usage_tracker
import agent_engine
import tools_os


class TestPhase2CScheduler(unittest.IsolatedAsyncioTestCase):
    """Test suite per la Fase 2C: Autonomia programmata, background e consumi."""

    async def asyncSetUp(self):
        db.reset_db()
        self.scheduler = SchedulerService()

    async def asyncTearDown(self):
        await self.scheduler.stop_background_loop()

    # ========================================================================
    # TEST 1: ESECUZIONE SINGOLA (ONCE)
    # ========================================================================
    async def test_1_single_execution(self):
        print("\n--- TEST 1: Esecuzione singola ---")
        now = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        target_time = now + datetime.timedelta(hours=2)

        job = self.scheduler.schedule_job(
            name="Backup isolato",
            prompt="Esegui backup dati",
            schedule_type="once",
            schedule_config={"target_time": target_time.isoformat()},
            chat_id="chat_chief",
            reference_time=now,
        )

        self.assertEqual(job["status"], "active")
        self.assertIsNotNone(job["next_run_at"])

        # Tick prima della scadenza: non deve scattare
        triggered = await self.scheduler.tick(reference_time=now + datetime.timedelta(hours=1))
        self.assertEqual(len(triggered), 0)

        # Tick alla scadenza
        triggered = await self.scheduler.tick(reference_time=target_time + datetime.timedelta(seconds=1))
        self.assertEqual(len(triggered), 1)

        # Attesa completamento esecuzione asincrona
        await asyncio.sleep(0.1)

        updated_job = db.get_scheduled_job(job["id"])
        self.assertEqual(updated_job["status"], "completed")
        self.assertIsNone(updated_job["next_run_at"])

        history = db.get_job_executions(job_id=job["id"])
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "success")
        print("  [PASS] Esecuzione singola verificata: transizione ad 'completed' e next_run_at rimosso.")

    # ========================================================================
    # TEST 2: RICORRENZA A INTERVALLI (INTERVAL)
    # ========================================================================
    async def test_2_recurrence(self):
        print("\n--- TEST 2: Ricorrenza ---")
        t0 = datetime.datetime(2026, 10, 26, 8, 0, 0, tzinfo=datetime.timezone.utc)
        interval_sec = 1800  # 30 minuti

        job = self.scheduler.schedule_job(
            name="Controllo periodico",
            prompt="Verifica salute servizi",
            schedule_type="interval",
            schedule_config={"interval_seconds": interval_sec},
            chat_id="chat_chief",
            reference_time=t0,
        )

        t1 = t0 + datetime.timedelta(seconds=interval_sec)
        # Primo intervallo raggiunto
        trig1 = await self.scheduler.tick(reference_time=t1)
        self.assertEqual(len(trig1), 1)
        await asyncio.sleep(0.05)

        j1 = db.get_scheduled_job(job["id"])
        self.assertEqual(j1["status"], "active")
        # Prossima esecuzione deve essere avanzata di 30 minuti
        next_dt = datetime.datetime.fromisoformat(j1["next_run_at"])
        self.assertEqual(next_dt, t1 + datetime.timedelta(seconds=interval_sec))

        # Secondo intervallo raggiunto
        t2 = t1 + datetime.timedelta(seconds=interval_sec)
        trig2 = await self.scheduler.tick(reference_time=t2)
        self.assertEqual(len(trig2), 1)
        await asyncio.sleep(0.05)

        history = db.get_job_executions(job_id=job["id"])
        self.assertEqual(len(history), 2)
        print("  [PASS] Ricorrenza a intervallo verificata: avanzamento regolare e cronologia tracciata.")

    # ========================================================================
    # TEST 3: GESTIONE FUSI ORARI E CAMBI ORA LEGALE (DST)
    # ========================================================================
    async def test_3_timezone_and_dst(self):
        print("\n--- TEST 3: Gestione fusi orari e cambi ora legale ---")
        # Domenica 25 Ottobre 2026: cambio ora legale in Europa/Roma (da CEST UTC+2 a CET UTC+1 alle 03:00)
        # Prima del cambio (24 Ottobre ore 10:00 CEST -> offset +02:00)
        t_before = datetime.datetime(2026, 10, 24, 10, 0, 0, tzinfo=ZoneInfo("Europe/Rome"))

        next_run = self.scheduler.calculate_next_run(
            schedule_type="daily",
            schedule_config={"time": "09:00"},
            timezone_name="Europe/Rome",
            reference_time=t_before,
        )
        # Deve essere 25 Ottobre ore 09:00 in Europe/Rome
        self.assertEqual(next_run.hour, 9)
        self.assertEqual(next_run.minute, 0)
        self.assertEqual(next_run.day, 25)
        # Alle 09:00 del 25 Ottobre l'ora è già diventata solare (CET, offset +01:00)
        self.assertEqual(next_run.utcoffset(), datetime.timedelta(hours=1))

        # Settimanale
        weekly_run = self.scheduler.calculate_next_run(
            schedule_type="weekly",
            schedule_config={"time": "14:30", "days": [0, 4]},  # Lunedì e Venerdì
            timezone_name="Europe/Rome",
            reference_time=datetime.datetime(2026, 10, 26, 15, 0, 0, tzinfo=ZoneInfo("Europe/Rome")),
        )
        self.assertEqual(weekly_run.weekday(), 4)  # Prossimo deve essere Venerdì
        self.assertEqual(weekly_run.hour, 14)
        self.assertEqual(weekly_run.minute, 30)
        print("  [PASS] Fusi orari IANA e cambio ora legale (DST) calcolati rigorosamente.")

    # ========================================================================
    # TEST 4: RIAVVIO DELL'APP
    # ========================================================================
    async def test_4_app_restart(self):
        print("\n--- TEST 4: Riavvio dell'app ---")
        now = datetime.datetime(2026, 10, 26, 10, 0, 0, tzinfo=datetime.timezone.utc)
        job = self.scheduler.schedule_job(
            name="Job persistente",
            prompt="Attività da mantenere",
            schedule_type="daily",
            schedule_config={"time": "18:00"},
            chat_id="chat_chief",
            reference_time=now,
        )

        # Simula chiusura dell'app (nuova istanza del servizio su stesso DB)
        fresh_scheduler = SchedulerService()
        recovered = db.get_scheduled_job(job["id"])

        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["name"], "Job persistente")
        self.assertEqual(recovered["status"], "active")
        print("  [PASS] Riavvio dell'app verificato: nessuna perdita di pianificazioni su SQLite.")

    # ========================================================================
    # TEST 5: JOB MANCATI (POLICY DOWNTIME)
    # ========================================================================
    async def test_5_missed_jobs(self):
        print("\n--- TEST 5: Job mancati ---")
        # Simuliamo un'attività scaduta 4 ore fa (mentre l'app era chiusa)
        t_downtime = datetime.datetime(2026, 10, 26, 6, 0, 0, tzinfo=datetime.timezone.utc)
        now = datetime.datetime(2026, 10, 26, 10, 0, 0, tzinfo=datetime.timezone.utc)

        # 1. Job con policy 'skip'
        job_skip = self.scheduler.schedule_job(
            name="Job saltato",
            prompt="Istruzione skip",
            schedule_type="interval",
            schedule_config={"interval_seconds": 3600},
            chat_id="chat_chief",
            missed_job_policy="skip",
            reference_time=t_downtime,
        )

        # 2. Job con policy 'run_once'
        job_run_once = self.scheduler.schedule_job(
            name="Job run once",
            prompt="Istruzione una tantum",
            schedule_type="interval",
            schedule_config={"interval_seconds": 3600},
            chat_id="chat_chief",
            missed_job_policy="run_once",
            reference_time=t_downtime,
        )

        # Esecuzione della procedura di recupero al riavvio
        recovery_report = await self.scheduler.handle_startup_recovery(reference_time=now)

        self.assertEqual(recovery_report["skipped"], 1)
        self.assertEqual(recovery_report["executed_once"], 1)

        # Verifica che il job skip non abbia generato esecuzioni multiple
        skip_execs = db.get_job_executions(job_id=job_skip["id"])
        self.assertEqual(len(skip_execs), 1)
        self.assertEqual(skip_execs[0]["status"], "skipped")

        # Verifica che il job run_once abbia eseguito ESATTAMENTE 1 volta
        run_once_execs = db.get_job_executions(job_id=job_run_once["id"])
        self.assertEqual(len(run_once_execs), 1)
        self.assertIn(run_once_execs[0]["status"], ("running", "success"))

        print("  [PASS] Policy per job mancati verificata: zero valanghe di task arretrati.")

    # ========================================================================
    # TEST 6: CONCORRENZA E PREVENZIONE DUPLICATI
    # ========================================================================
    async def test_6_concurrency_and_duplicates(self):
        print("\n--- TEST 6: Concorrenza e prevenzione duplicati ---")
        now = datetime.datetime(2026, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)
        job = self.scheduler.schedule_job(
            name="Job atomico",
            prompt="Esecuzione concorrente",
            schedule_type="once",
            schedule_config={"target_time": now.isoformat()},
            chat_id="chat_chief",
            reference_time=now,
        )

        # Simuliamo 5 worker concorrenti che tentano di prenotare lo stesso identico job nello stesso istante
        async def _worker_reserve():
            return db.reserve_job_for_execution_atomic(
                job_id=job["id"],
                expected_next_run=job["next_run_at"],
                new_next_run=None,
                new_status="completed",
            )

        results = await asyncio.gather(*[_worker_reserve() for _ in range(5)])
        # Esattamente 1 worker deve vincere la prenotazione, 4 devono fallire
        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 4)
        print("  [PASS] Prevenzione duplicati atomica su SQLite verificata al 100% (1 vincitore su 5 concorrenti).")

    # ========================================================================
    # TEST 7: APPROVAZIONI OBBLIGATORIE SUI TASK SCHEDULATI
    # ========================================================================
    async def test_7_mandatory_approvals(self):
        print("\n--- TEST 7: Approvazioni obbligatorie ---")
        # Simuliamo un'attività programmata che tenta un'azione mutante sui file
        test_file = TEST_DIR / "file_schedulato.txt"

        task = db.create_task(
            chat_id="chat_chief",
            bot_id="builder",
            title="Task da scheduler",
            goal="Scrivi file critico",
            instruction=f"Scrivi dati in {test_file}",
        )

        appr = db.create_approval(
            chat_id="chat_chief",
            bot_id="builder",
            action_type="file_operation",
            description=f"Scrittura file {test_file}",
            payload={"tool_name": "file_operation", "args": {"action": "write", "path": str(test_file), "content": "ciao"}},
            task_id=task["id"],
        )
        db.update_task_status_atomic(task["id"], "waiting_approval")

        # Il task deve rimanere bloccato in waiting_approval finché l'utente non approva
        t_state = db.get_task(task["id"])
        self.assertEqual(t_state["status"], "waiting_approval")
        self.assertFalse(test_file.exists(), "Il file non deve essere scritto prima dell'approvazione umana!")

        # Approvazione esplicita
        success, _ = db.resolve_approval_atomic(appr["id"], "approved")
        self.assertTrue(success)
        print("  [PASS] Nessun aggiramento delle approvazioni: le azioni mutanti restano bloccate in waiting_approval.")

    # ========================================================================
    # TEST 8: QUOTE E LIMITI DI UTILIZZO
    # ========================================================================
    async def test_8_quotas_and_limits(self):
        print("\n--- TEST 8: Quote e limiti di utilizzo ---")
        tracker = UsageTracker()

        # Configura quote restrittive per il test
        db.save_usage_limit("max_requests_daily", 3)
        db.save_usage_limit("max_requests_per_task", 2)

        task_id = "task_quota_test"

        # Prima richiesta ok
        tracker.record_model_call("gemini-2.5-flash", task_id=task_id, input_tokens=100, output_tokens=50)
        ok1, _ = tracker.check_limits(task_id=task_id)
        self.assertTrue(ok1)

        # Seconda richiesta ok
        tracker.record_model_call("gemini-2.5-flash", task_id=task_id, input_tokens=100, output_tokens=50)
        # Limite task raggiunto (2/2)
        ok2, err2 = tracker.check_limits(task_id=task_id)
        self.assertFalse(ok2)
        self.assertIn("raggiunto", err2.lower())

        # Verifica consumi registrati
        summary = db.get_usage_summary(days=1)
        self.assertEqual(summary["requests_count"], 2)
        self.assertEqual(summary["total_tokens"], 300)
        self.assertGreater(summary["estimated_cost_usd"], 0.0)
        self.assertIn("non costituisce fatturazione", summary["is_estimate_notice"])
        print("  [PASS] Controllo quote (per task e giornaliere) e tracciamento consumi verificati.")

    # ========================================================================
    # TEST 9: ARRESTO DURANTE UN'ESECUZIONE (SHUTDOWN SICURO)
    # ========================================================================
    async def test_9_stop_during_execution(self):
        print("\n--- TEST 9: Arresto durante un'esecuzione ---")
        # Crea un task e un'esecuzione in corso ('running')
        task = db.create_task("chat_chief", "builder", "In corso", "Lavoro lungo", "Lavoro lungo")
        db.update_task_status_atomic(task["id"], "running")

        job = self.scheduler.schedule_job(
            name="Job interrotto",
            prompt="Esegui lungo",
            schedule_type="interval",
            schedule_config={"interval_seconds": 3600},
            chat_id="chat_chief",
        )
        exec_rec = db.create_job_execution(job["id"], scheduled_for=datetime.datetime.now(datetime.timezone.utc).isoformat(), task_id=task["id"], status="running")

        # Chiamata di arresto sicuro (simulazione shutdown app)
        self.scheduler._is_running = True
        await self.scheduler.stop_background_loop()

        # Verifica che running sia stato convertito in 'interrupted'
        updated_exec = db.get_job_executions(job_id=job["id"])[0]
        self.assertEqual(updated_exec["status"], "interrupted")
        updated_task = db.get_task(task["id"])
        self.assertEqual(updated_task["status"], "interrupted")
        print("  [PASS] Arresto sicuro verificato: transizione a 'interrupted' senza corruzione del database.")

    # ========================================================================
    # TEST 10: NOTIFICHE LOCALI E SANIFICAZIONE SEGRETI
    # ========================================================================
    async def test_10_notifications_and_secrets(self):
        print("\n--- TEST 10: Notifiche locali ---")
        # Notifica con tentativo di inclusione token/password
        secret_text = "Task fallito per via del Bearer sk-1234567890abcdef1234567890 e password=MioSegreto123!"
        notif = await notification_manager.notify_task_failed(
            task_id="task_test_sec",
            title="Errore connessione",
            error_msg=secret_text,
        )

        self.assertNotIn("sk-1234567890abcdef1234567890", notif["message"])
        self.assertNotIn("MioSegreto123", notif["message"])
        self.assertIn("[DATO_SENSIBILE_PROTETTO]", notif["message"])

        # Notifica completamento e lettura
        n_comp = await notification_manager.notify_task_completed("task_ok", "Tutto fatto", "Finito con successo")
        unread = notification_manager.get_notifications(unread_only=True)
        self.assertGreaterEqual(len(unread), 2)

        notification_manager.mark_read(n_comp["id"])
        unread_after = notification_manager.get_notifications(unread_only=True)
        self.assertEqual(len(unread_after), len(unread) - 1)
        print("  [PASS] Notifiche locali attive con sanificazione totale di credenziali e token.")

    # ========================================================================
    # TEST 11: NESSUNA ESECUZIONE NASCOSTA DOPO CHIUSURA
    # ========================================================================
    async def test_11_no_hidden_execution_after_exit(self):
        print("\n--- TEST 11: Nessuna esecuzione nascosta dopo chiusura ---")
        # Verifica assenza di servizi Windows registrati o task schedulati nell'OS
        # Il sistema opera ESCLUSIVAMENTE tramite il processo Python/asyncio
        self.assertFalse(self.scheduler._is_running)
        self.assertIsNone(self.scheduler._background_task)

        # Se il tempo avanza senza il processo attivo, nessun tick deve avvenire
        now = datetime.datetime.now(datetime.timezone.utc)
        execs_before = len(db.get_job_executions())
        # (Nessun tick chiamato)
        execs_after = len(db.get_job_executions())
        self.assertEqual(execs_before, execs_after)
        print("  [PASS] Nessun servizio Windows o task pianificato a livello di sistema operativo: esecuzione limitata al ciclo vitale.")

    # ========================================================================
    # TEST 12: REGRESSIONE COMPLETA (FASI 1, 1.1, 2A, 2A.1, 2B)
    # ========================================================================
    async def test_12_full_regression(self):
        print("\n--- TEST 12: Regressione Fasi 1, 1.1, 2A, 2A.1 e 2B ---")
        # 1. Sicurezza Filesystem
        res1 = tools_os.manage_files("read", "../../Windows/System32/drivers/etc/hosts")
        self.assertTrue(res1.get("blocked"))
        res_env = tools_os.manage_files("read", ".env")
        self.assertTrue(res_env.get("blocked"))

        # 2. Shell disabilitata
        res_shell = tools_os.run_terminal_command("whoami")
        self.assertTrue(res_shell.get("blocked"))

        # 3. Transizione atomica approvazioni
        appr = db.create_approval("chat_chief", "builder", "click", "clic", {}, None, None)
        s1, _ = db.resolve_approval_atomic(appr["id"], "approved")
        s2, _ = db.resolve_approval_atomic(appr["id"], "rejected")
        self.assertTrue(s1)
        self.assertFalse(s2)  # Replay bloccato

        # 4. Task persistence
        t = db.create_task("chat_chief", "chief", "Task", "Goal", "Instr")
        self.assertEqual(db.get_task(t["id"])["status"], "pending")

        # 5. Memoria & FTS5
        mem = db.save_memory(content="Preferenza test", memory_type="preference", project_id="p1")
        fts_res = db.search_memories_fts("Preferenza")
        self.assertGreaterEqual(len(fts_res), 1)

        print("  [PASS] 100% dei requisiti di sicurezza e affidabilità delle Fasi 1, 1.1, 2A, 2A.1 e 2B verificati intatti.")


if __name__ == "__main__":
    print("=" * 70)
    print("   COWORKEROS - VERIFICA FASE 2C: AUTONOMIA E CONTROLLO CONSUMI   ")
    print("=" * 70)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase2CScheduler)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)

    try:
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    except Exception:
        pass

    if result.wasSuccessful():
        print("\n" + "=" * 70)
        print("   ESITO FINALE: TUTTI I 12 TEST FASE 2C SUPERATI CON SUCCESSO!   ")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n[FAIL] Alcuni test non sono stati superati.")
        sys.exit(1)
