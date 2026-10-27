"""
CoworkerOS Usage & Quota Tracker (Fase 2C)
Tracciamento persistente dei consumi di modelli, token, costi stimati e quote.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import database as db


# Tariffe stimate per milione di token (USD) - Clearly marked as estimates
MODEL_RATES = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-3.8-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "default": {"input": 0.10, "output": 0.40},
}


class UsageTracker:
    """Gestisce il calcolo, la registrazione e il controllo quote dei modelli."""

    @staticmethod
    def estimate_cost_usd(
        model_name: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
    ) -> float:
        """
        Calcola una stima del costo in USD basata su token input e output.
        Restituisce 0.0 se i token non sono disponibili (mai numeri inventati).
        """
        if input_tokens is None and output_tokens is None:
            return 0.0

        rate = MODEL_RATES.get(model_name.lower(), MODEL_RATES["default"])
        in_t = input_tokens or 0
        out_t = output_tokens or 0
        cost = (in_t / 1_000_000.0) * rate["input"] + (out_t / 1_000_000.0) * rate["output"]
        return round(cost, 6)

    def record_model_call(
        self,
        model_name: str,
        task_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        job_id: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """Registra la chiamata del modello con metadati reali o null."""
        cost_est = self.estimate_cost_usd(model_name, input_tokens, output_tokens)
        return db.record_usage(
            model_name=model_name,
            task_id=task_id,
            chat_id=chat_id,
            job_id=job_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost_est,
            duration_ms=duration_ms,
            is_estimated=1,
        )

    def check_limits(
        self,
        task_id: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifica se i limiti configurati (per task, giornalieri o contemporanei) sono stati superati.
        Restituisce (True, None) se entro i limiti, oppure (False, messaggio_errore).
        """
        limits = db.get_usage_limits()
        max_daily_requests = limits.get("max_requests_daily", 200)
        max_task_requests = limits.get("max_requests_per_task", 15)
        max_concurrent_tasks = limits.get("max_concurrent_tasks", 3)

        # 1. Limite richieste giornaliere
        summary = db.get_usage_summary(days=1)
        daily_count = summary.get("requests_count", 0)
        if daily_count >= max_daily_requests:
            msg = f"Limite giornaliero di richieste superato ({daily_count}/{max_daily_requests})."
            return False, msg

        # 2. Limite richieste per singolo task
        if task_id:
            task_summary = db.get_usage_summary(days=1, task_id=task_id)
            task_usage = task_summary.get("task_usage")
            task_requests = task_usage.get("requests", 0) if task_usage else 0
            if task_requests >= max_task_requests:
                msg = f"Limite di richieste per il task '{task_id}' raggiunto ({task_requests}/{max_task_requests})."
                return False, msg

        # 3. Limite task concorrenti attivi in SQLite
        conn = db.get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) AS running_count FROM tasks WHERE status = 'running';")
            row = cursor.fetchone()
            running = row["running_count"] if row else 0
            if running >= max_concurrent_tasks:
                msg = f"Raggiunto il numero massimo di task contemporanei in esecuzione ({running}/{max_concurrent_tasks})."
                return False, msg
        finally:
            conn.close()

        return True, None


usage_tracker = UsageTracker()
