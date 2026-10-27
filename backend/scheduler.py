"""
CoworkerOS Local Persistent Scheduler (Fase 2C)
Gestisce la pianificazione di attività singole e ricorrenti, rispetto dei fusi orari/DST,
prevenzione atomica dei duplicati, policy per job mancati e integrazione con il Task Engine.
Funziona esclusivamente durante il ciclo di vita dell'applicazione (nessun servizio Windows).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import database as db
from notifications import notification_manager
from usage_tracker import usage_tracker

logger = logging.getLogger("coworkeros.scheduler")


def parse_timezone(tz_name: Optional[str]) -> datetime.tzinfo:
    """Risolve un nome di fuso orario IANA, con fallback sicuro su UTC in caso di errore."""
    if not tz_name or tz_name.upper() == "UTC":
        return datetime.timezone.utc
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        return datetime.timezone.utc


def get_current_time(tz: Optional[datetime.tzinfo] = None) -> datetime.datetime:
    """Restituisce il datetime corrente consapevole (timezone-aware)."""
    target_tz = tz or datetime.timezone.utc
    return datetime.datetime.now(target_tz)


class SchedulerService:
    """Servizio per la pianificazione persistente delle attività di CoworkerOS."""

    def __init__(self) -> None:
        self._background_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._is_running = False
        self._in_flight_tasks: Dict[str, asyncio.Task] = {}
        self._orchestrator_ref: Any = None

    def set_orchestrator(self, orchestrator: Any) -> None:
        """Collega l'orchestratore per il dispatch dei task."""
        self._orchestrator_ref = orchestrator

    # ========================================================================
    # 1. CALCOLO DELLA PROSSIMA ESECUZIONE (FUSI ORARI E DST)
    # ========================================================================

    @staticmethod
    def calculate_next_run(
        schedule_type: str,
        schedule_config: Dict[str, Any],
        timezone_name: str = "UTC",
        reference_time: Optional[datetime.datetime] = None,
    ) -> Optional[datetime.datetime]:
        """
        Calcola la prossima esecuzione per tipo: once, interval, daily, weekly.
        Gestisce rigorosamente fusi orari espliciti e transizioni ora solare/legale (DST).
        """
        tz = parse_timezone(timezone_name)
        ref = reference_time or get_current_time(tz)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=tz)
        else:
            ref = ref.astimezone(tz)

        st = schedule_type.lower().strip()

        if st == "once":
            target_str = schedule_config.get("target_time")
            if not target_str:
                return None
            try:
                dt = datetime.datetime.fromisoformat(target_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz)
                else:
                    dt = dt.astimezone(tz)
                return dt
            except Exception:
                return None

        elif st == "interval":
            interval_sec = int(schedule_config.get("interval_seconds", 3600))
            if interval_sec <= 0:
                interval_sec = 60
            return ref + datetime.timedelta(seconds=interval_sec)

        elif st == "daily":
            time_str = schedule_config.get("time", "09:00")
            try:
                hour, minute = map(int, time_str.split(":"))
            except Exception:
                hour, minute = 9, 0

            # Prova per oggi
            candidate = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= ref:
                # Se l'orario di oggi è già passato, calcola per domani gestendo DST con calendar addition
                candidate = (ref + datetime.timedelta(days=1)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            return candidate

        elif st == "weekly":
            days = schedule_config.get("days", [0])  # 0=Lunedì .. 6=Domenica
            time_str = schedule_config.get("time", "09:00")
            try:
                hour, minute = map(int, time_str.split(":"))
            except Exception:
                hour, minute = 9, 0

            if not days:
                days = [0]
            days_sorted = sorted(list(set(days)))

            # Cerca nel range dei prossimi 8 giorni
            for d_offset in range(8):
                check_date = ref + datetime.timedelta(days=d_offset)
                if check_date.weekday() in days_sorted:
                    candidate = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if candidate > ref:
                        return candidate

            # Fallback
            return ref + datetime.timedelta(days=7)

        return None

    # ========================================================================
    # 2. CRUD E STATO ATTIVITÀ
    # ========================================================================

    def schedule_job(
        self,
        name: str,
        prompt: str,
        schedule_type: str,
        schedule_config: Dict[str, Any],
        chat_id: str,
        target_bot_id: str = "chief",
        project_id: str = "default",
        timezone_name: str = "UTC",
        missed_job_policy: str = "skip",
        description: Optional[str] = None,
        reference_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """Crea e pianifica una nuova attività calcolando il next_run_at iniziale."""
        next_run = self.calculate_next_run(
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            timezone_name=timezone_name,
            reference_time=reference_time,
        )
        next_run_iso = next_run.isoformat() if next_run else None

        job = db.create_scheduled_job(
            name=name,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_config=schedule_config,
            chat_id=chat_id,
            target_bot_id=target_bot_id,
            project_id=project_id,
            timezone=timezone_name,
            missed_job_policy=missed_job_policy,
            next_run_at=next_run_iso,
            description=description,
        )
        return job

    def pause_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Mette in pausa un'attività programmata."""
        return db.update_scheduled_job(job_id, status="paused")

    def resume_job(
        self,
        job_id: str,
        reference_time: Optional[datetime.datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """Riattiva un'attività programmata ricalcolando la prossima esecuzione."""
        job = db.get_scheduled_job(job_id)
        if not job:
            return None

        next_run = self.calculate_next_run(
            schedule_type=job["schedule_type"],
            schedule_config=job["schedule_config"],
            timezone_name=job.get("timezone", "UTC"),
            reference_time=reference_time,
        )
        next_run_iso = next_run.isoformat() if next_run else None
        return db.update_scheduled_job(job_id, status="active", next_run_at=next_run_iso)

    def cancel_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Annulla definitivamente un'attività programmata."""
        return db.update_scheduled_job(job_id, status="cancelled", next_run_at=None)

    def delete_job(self, job_id: str) -> bool:
        """Elimina la pianificazione dal database."""
        return db.delete_scheduled_job(job_id)

    # ========================================================================
    # 3. GESTIONE RIAVVIO E JOB MANCATI (POLICY ESPLICITE)
    # ========================================================================

    async def handle_startup_recovery(
        self,
        reference_time: Optional[datetime.datetime] = None,
    ) -> Dict[str, Any]:
        """
        Policy di recupero al riavvio dell'applicazione.
        Non esegue retroattivamente decine di attività scadute in blocco.
        Applica la policy configurata (skip, run_once, catch_up).
        """
        ref_time = reference_time or get_current_time(datetime.timezone.utc)
        ref_iso = ref_time.isoformat()

        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM scheduled_jobs
                WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at < ?;
                """,
                (ref_iso,),
            )
            missed_jobs = [db._format_job_row(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

        results = {"skipped": 0, "executed_once": 0, "rescheduled": 0}

        for job in missed_jobs:
            policy = job.get("missed_job_policy", "skip").lower()
            job_id = job["id"]
            scheduled_for = job["next_run_at"]

            if job["schedule_type"] == "once":
                future_iso = None
                new_status = "completed"
            else:
                future_next = self.calculate_next_run(
                    schedule_type=job["schedule_type"],
                    schedule_config=job["schedule_config"],
                    timezone_name=job.get("timezone", "UTC"),
                    reference_time=ref_time,
                )
                future_iso = future_next.isoformat() if future_next else None
                new_status = "active"

            if policy == "skip":
                # Prenota e avanza senza eseguire
                reserved = db.reserve_job_for_execution_atomic(
                    job_id=job_id,
                    expected_next_run=scheduled_for,
                    new_next_run=future_iso,
                    new_status=new_status,
                )
                if reserved:
                    db.create_job_execution(
                        job_id=job_id,
                        scheduled_for=scheduled_for,
                        status="skipped",
                        error_message="Attività saltata in base alla policy missed_job_policy=skip (downtime applicazione).",
                    )
                    results["skipped"] += 1

            elif policy in ("run_once", "catch_up"):
                # Esegue ESATTAMENTE 1 volta l'istanza mancata, poi avanza alla prossima futura
                reserved = db.reserve_job_for_execution_atomic(
                    job_id=job_id,
                    expected_next_run=scheduled_for,
                    new_next_run=future_iso,
                    new_status=new_status,
                )
                if reserved:
                    exec_record = db.create_job_execution(
                        job_id=job_id,
                        scheduled_for=scheduled_for,
                        status="running",
                    )
                    # Esegue in background l'istanza singola
                    await self._execute_job_instance(job, exec_record["id"], scheduled_for)
                    results["executed_once"] += 1

        return results

    # ========================================================================
    # 4. CICLO SCHEDULER (TICK E PREVENZIONE CONCORRENZA)
    # ========================================================================

    async def tick(
        self,
        reference_time: Optional[datetime.datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Valuta i job con scadenza superata e li prenota atomicamente per l'esecuzione.
        Previene doppie esecuzioni concorrenti tramite lock ottimistico su SQLite.
        """
        ref_time = reference_time or get_current_time(datetime.timezone.utc)
        ref_iso = ref_time.isoformat()

        conn = db.get_connection()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM scheduled_jobs
                WHERE status = 'active' AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC;
                """,
                (ref_iso,),
            )
            due_jobs = [db._format_job_row(dict(r)) for r in cursor.fetchall()]
        finally:
            conn.close()

        triggered: List[Dict[str, Any]] = []

        for job in due_jobs:
            job_id = job["id"]
            scheduled_for = job["next_run_at"]

            if job["schedule_type"] == "once":
                next_run_iso = None
                new_status = "completed"
            else:
                next_run = self.calculate_next_run(
                    schedule_type=job["schedule_type"],
                    schedule_config=job["schedule_config"],
                    timezone_name=job.get("timezone", "UTC"),
                    reference_time=ref_time,
                )
                next_run_iso = next_run.isoformat() if next_run else None
                new_status = "active"

            # Transizione atomica su SQLite per vincere l'esecuzione:
            reserved = db.reserve_job_for_execution_atomic(
                job_id=job_id,
                expected_next_run=scheduled_for,
                new_next_run=next_run_iso,
                new_status=new_status,
            )
            if not reserved:
                # Un altro processo o thread ha già preso in carico questa esecuzione
                continue

            # Registra l'esecuzione nella cronologia
            exec_record = db.create_job_execution(
                job_id=job_id,
                scheduled_for=scheduled_for,
                status="running",
            )

            # Lancia l'esecuzione collegata al Task Engine
            asyncio.create_task(
                self._execute_job_instance(job, exec_record["id"], scheduled_for)
            )
            triggered.append({"job_id": job_id, "execution_id": exec_record["id"]})

        return triggered

    async def _execute_job_instance(
        self,
        job: Dict[str, Any],
        execution_id: str,
        scheduled_for: str,
    ) -> None:
        """
        Esegue concretamente l'istanza di un'attività programmata:
        - Verifica quote e consumi prima della chiamata.
        - Genera un task persistente nel Task Engine.
        - Preserva le approvazioni obbligatorie per qualsiasi azione mutante.
        - Invia notifiche locali e traccia consumi reali/stimati.
        """
        start_time = time.time()
        job_id = job["id"]
        job_name = job["name"]
        prompt = job["prompt"]
        chat_id = job["chat_id"]
        target_bot = job.get("target_bot_id", "chief")

        # 1. Controllo quote e limiti preventivo
        is_ok, limit_msg = usage_tracker.check_limits()
        if not is_ok:
            duration = int((time.time() - start_time) * 1000)
            db.update_job_execution(
                execution_id=execution_id,
                status="failed",
                error_message=limit_msg,
                duration_ms=duration,
            )
            await notification_manager.notify_limit_reached(
                title=f"Automazione bloccata: {job_name}",
                reason=limit_msg or "Limite quote raggiunto.",
            )
            return

        # 2. Creazione task nel Task Engine
        task_record = db.create_task(
            chat_id=chat_id,
            bot_id=target_bot,
            title=f"[Schedulato] {job_name}",
            goal=job_name,
            instruction=prompt,
        )
        task_id = task_record["id"]
        db.update_job_execution(execution_id, status="running", task_id=task_id)

        try:
            # 3. Se presente l'orchestratore, esegue il turn di conversazione
            if self._orchestrator_ref:
                user_msg = db.save_message(
                    chat_id=chat_id,
                    sender_id="system_scheduler",
                    sender_name=f"Automazione: {job_name}",
                    content=prompt,
                )
                replies = await self._orchestrator_ref.handle_conversation_turn(
                    chat_id=chat_id,
                    user_content=prompt,
                    target_bot_id=target_bot,
                    current_task_id=task_id,
                )
            else:
                # Modalità standalone o simulata
                db.update_task_status_atomic(task_id, "completed", result={"content": "Esecuzione scheduler registrata"})

            duration = int((time.time() - start_time) * 1000)
            final_task = db.get_task(task_id)
            task_status = final_task.get("status") if final_task else "completed"

            # 4. Aggiorna lo stato dell'esecuzione e notifica
            if task_status == "waiting_approval":
                db.update_job_execution(
                    execution_id=execution_id,
                    status="waiting_approval",
                    duration_ms=duration,
                    task_id=task_id,
                )
                await notification_manager.notify_approval_needed(
                    approval_id=task_id,
                    title=f"Approvazione richiesta da '{job_name}'",
                    details=f"Il task programmato '{job_name}' richiede un'autorizzazione prima di procedere.",
                )
            elif task_status == "completed":
                db.update_job_execution(
                    execution_id=execution_id,
                    status="success",
                    duration_ms=duration,
                    task_id=task_id,
                )
                await notification_manager.notify_task_completed(
                    task_id=task_id,
                    title=f"Automazione completata: {job_name}",
                    message=f"L'attività programmata '{job_name}' è terminata con successo.",
                )
            else:
                err_msg = final_task.get("error_msg") if final_task else "Errore sconosciuto nel task"
                db.update_job_execution(
                    execution_id=execution_id,
                    status="failed",
                    error_message=err_msg,
                    duration_ms=duration,
                    task_id=task_id,
                )
                await notification_manager.notify_task_failed(
                    task_id=task_id,
                    title=f"Automazione fallita: {job_name}",
                    error_msg=str(err_msg),
                )

        except asyncio.CancelledError:
            duration = int((time.time() - start_time) * 1000)
            db.update_job_execution(
                execution_id=execution_id,
                status="interrupted",
                error_message="Arresto dell'applicazione durante l'esecuzione",
                duration_ms=duration,
                task_id=task_id,
            )
            db.update_task_status_atomic(task_id, "interrupted", error_msg="Applicazione chiusa")
            raise

        except Exception as exc:
            duration = int((time.time() - start_time) * 1000)
            db.update_job_execution(
                execution_id=execution_id,
                status="failed",
                error_message=str(exc),
                duration_ms=duration,
                task_id=task_id,
            )
            db.update_task_status_atomic(task_id, "failed", error_msg=str(exc))
            await notification_manager.notify_task_failed(
                task_id=task_id,
                title=f"Errore automazione: {job_name}",
                error_msg=str(exc),
            )

    # ========================================================================
    # 5. BACKGROUND LOOP (IN-PROCESS, SOLO DURANTE L'AVVIO DELL'APP)
    # ========================================================================

    async def start_background_loop(self, poll_interval_seconds: float = 2.0) -> None:
        """
        Avvia il loop in background asincrono durante l'avvio dell'applicazione.
        Nessun servizio Windows, nessun avvio automatico nascosto.
        """
        if self._is_running:
            return

        self._is_running = True
        self._stop_event.clear()

        # Esegue prima la procedura di recovery per i job mancati durante il downtime
        try:
            await self.handle_startup_recovery()
        except Exception as exc:
            logger.error(f"Errore nella procedura di startup recovery dello scheduler: {exc}")

        async def _loop():
            while not self._stop_event.is_set():
                try:
                    await self.tick()
                except Exception as exc:
                    logger.error(f"Errore nel ciclo scheduler: {exc}")

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass

        self._background_task = asyncio.create_task(_loop())
        logger.info("Scheduler locale avviato con successo in background.")

    async def stop_background_loop(self) -> None:
        """
        Arresta in sicurezza il loop in background quando l'applicazione viene chiusa.
        Interrompe i lavori in sicurezza marcandoli 'interrupted'.
        """
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

        # Marca eventuali esecuzioni rimaste in stato 'running' come 'interrupted'
        conn = db.get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE job_executions
                    SET status = 'interrupted', error_message = 'Applicazione arrestata in sicurezza'
                    WHERE status = 'running';
                    """
                )
                conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'interrupted', error_msg = 'Applicazione arrestata in sicurezza'
                    WHERE status = 'running';
                    """
                )
        finally:
            conn.close()

        logger.info("Scheduler locale arrestato in sicurezza.")


scheduler_service = SchedulerService()
