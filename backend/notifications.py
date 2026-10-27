"""
CoworkerOS Local Notifications Manager (Fase 2C)
Gestisce le notifiche locali per task, approvazioni, limiti di quota ed errori.
Garantisce l'assenza totale di segreti, token o credenziali nei testi.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

import database as db

# Regex per sanificazione credenziali nei messaggi di notifica
SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"sk-[0-9a-zA-Z]{20,}"),
    re.compile(r"(?:bearer\s+|token\s*[:=]\s*|apikey\s*[:=]\s*|api_key\s*[:=]\s*)['\"]?[a-zA-Z0-9_\-\.]{20,}['\"]?", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|PGP)?\s?PRIVATE KEY-----"),
    re.compile(r"(?:password|passwd|pwd|segreto)\s*[:=]\s*['\"]?\S+['\"]?", re.IGNORECASE),
]


def sanitize_notification_text(text: str) -> str:
    """Rimuove o maschera eventuali credenziali o token dal testo della notifica."""
    if not text:
        return ""
    sanitized = text
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[DATO_SENSIBILE_PROTETTO]", sanitized)
    return sanitized.strip()


class NotificationManager:
    """Gestore delle notifiche locali con audit trail e broadcast WebSocket."""

    def __init__(self) -> None:
        self._broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None

    def register_broadcast_callback(self, cb: Callable[[Dict[str, Any]], Any]) -> None:
        """Registra la callback per trasmettere le notifiche in tempo reale ai client."""
        self._broadcast_callback = cb

    async def _emit_ws(self, notification: Dict[str, Any]) -> None:
        if self._broadcast_callback:
            try:
                res = self._broadcast_callback({"type": "notification", "notification": notification})
                if hasattr(res, "__await__"):
                    await res
            except Exception:
                pass

    async def notify_task_completed(
        self,
        task_id: str,
        title: str,
        message: str = "Il task è stato completato con successo.",
    ) -> Dict[str, Any]:
        """Crea notifica di completamento task."""
        clean_title = sanitize_notification_text(title)
        clean_msg = sanitize_notification_text(message)
        notif = db.create_notification(
            category="task_completed",
            title=clean_title or "Task completato",
            message=clean_msg,
            related_id=task_id,
        )
        await self._emit_ws(notif)
        return notif

    async def notify_task_failed(
        self,
        task_id: str,
        title: str,
        error_msg: str,
    ) -> Dict[str, Any]:
        """Crea notifica di fallimento task."""
        clean_title = sanitize_notification_text(title)
        clean_err = sanitize_notification_text(error_msg)
        notif = db.create_notification(
            category="task_failed",
            title=clean_title or "Task fallito",
            message=clean_err or "Si è verificato un errore durante l'esecuzione del task.",
            related_id=task_id,
        )
        await self._emit_ws(notif)
        return notif

    async def notify_approval_needed(
        self,
        approval_id: str,
        title: str,
        details: str,
    ) -> Dict[str, Any]:
        """Crea notifica di richiesta approvazione per azione protetta."""
        clean_title = sanitize_notification_text(title)
        clean_details = sanitize_notification_text(details)
        notif = db.create_notification(
            category="approval_needed",
            title=clean_title or "Approvazione richiesta",
            message=clean_details or "Un'azione protetta richiede autorizzazione esplicita.",
            related_id=approval_id,
        )
        await self._emit_ws(notif)
        return notif

    async def notify_limit_reached(
        self,
        title: str,
        reason: str,
    ) -> Dict[str, Any]:
        """Crea notifica di limite quote raggiunto."""
        clean_title = sanitize_notification_text(title)
        clean_reason = sanitize_notification_text(reason)
        notif = db.create_notification(
            category="limit_reached",
            title=clean_title or "Quota di utilizzo raggiunta",
            message=clean_reason or "È stato raggiunto un limite configurato di richieste o token.",
            related_id=None,
        )
        await self._emit_ws(notif)
        return notif

    @staticmethod
    def get_notifications(limit: int = 50, unread_only: bool = False) -> List[Dict[str, Any]]:
        return db.get_notifications(limit=limit, unread_only=unread_only)

    @staticmethod
    def mark_read(notification_id: str) -> bool:
        return db.mark_notification_read(notification_id)

    @staticmethod
    def mark_all_read() -> int:
        return db.mark_all_notifications_read()


notification_manager = NotificationManager()
