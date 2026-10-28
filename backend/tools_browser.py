"""
Modulo strumenti browser isolato per CoworkerOS.
Interfaccia client HTTP verso il server sandbox Playwright in Docker (http://127.0.0.1:9333).
Garantisce protezione da prompt injection tramite sanitize_untrusted_text e troncamento sicuro.
"""

from typing import Dict, Any, Optional
import httpx
from memory_manager import MemoryManager

SANDBOX_BASE_URL = "http://127.0.0.1:9333"
DEFAULT_TIMEOUT = 18.0
DEFAULT_MAX_CHARS = 8000

DOCKER_UNAVAILABLE_MSG = (
    "Sandbox browser non disponibile. Assicurati che il container Docker sia in esecuzione su 127.0.0.1:9333 "
    "(consulta sandbox/README.md per avviare il container con docker run)."
)


def _handle_request_error(e: Exception) -> Dict[str, Any]:
    """Cattura e normalizza gli errori di connessione verso la sandbox Docker."""
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError)):
        return {
            "status": "error",
            "docker_available": False,
            "message": DOCKER_UNAVAILABLE_MSG,
        }
    return {
        "status": "error",
        "docker_available": True,
        "message": f"Errore durante la comunicazione con il browser sandbox: {str(e)}",
    }


def browser_open(url: str) -> Dict[str, Any]:
    """
    Apre un URL nel browser isolato sandbox.
    Operazione in sola lettura: non richiede approvazione esplicita.
    """
    if not url or not str(url).strip():
        return {"status": "error", "message": "URL non specificato o vuoto."}

    target_url = str(url).strip()
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(f"{SANDBOX_BASE_URL}/open", json={"url": target_url})
            if resp.status_code != 200:
                return {"status": "error", "message": f"Errore HTTP sandbox: {resp.status_code}"}
            data = resp.json()

            # Sanitizzazione testo non fidato proveniente dalla pagina
            if "title" in data and data["title"]:
                data["title"] = MemoryManager.sanitize_untrusted_text(data["title"])
            if "message" in data and data["message"]:
                data["message"] = MemoryManager.sanitize_untrusted_text(data["message"])

            return data
    except Exception as e:
        return _handle_request_error(e)


def browser_snapshot(max_chars: int = DEFAULT_MAX_CHARS) -> Dict[str, Any]:
    """
    Restituisce l'albero di accessibilità formattato con riferimenti numerici [ref].
    Operazione in sola lettura: non richiede approvazione esplicita.
    Sanitizza e tronca il testo non fidato della pagina web.
    """
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(f"{SANDBOX_BASE_URL}/snapshot")
            if resp.status_code != 200:
                return {"status": "error", "message": f"Errore HTTP sandbox: {resp.status_code}"}
            data = resp.json()

            raw_tree = data.get("snapshot", "")
            sanitized_tree = MemoryManager.sanitize_untrusted_text(raw_tree)

            if len(sanitized_tree) > max_chars:
                sanitized_tree = (
                    sanitized_tree[:max_chars]
                    + f"\n\n[... Testo dell'albero di accessibilità troncato a {max_chars} caratteri ...]"
                )

            data["snapshot"] = sanitized_tree
            if "title" in data and data["title"]:
                data["title"] = MemoryManager.sanitize_untrusted_text(data["title"])

            return data
    except Exception as e:
        return _handle_request_error(e)


def browser_click(ref: Any, approved: bool = False) -> Dict[str, Any]:
    """
    Esegue un clic sull'elemento specificato tramite il riferimento numerico [ref].
    Azione con effetti esterni: richiede approvazione esplicita dell'utente prima dell'esecuzione fisica.
    """
    if not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": "browser_action",
            "tool_name": "browser_click",
            "ref": ref,
            "message": f"Clic sul riferimento [{ref}] nel browser sandbox richiede l'approvazione dell'utente.",
        }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(f"{SANDBOX_BASE_URL}/click", json={"ref": ref})
            if resp.status_code != 200:
                return {"status": "error", "message": f"Errore HTTP sandbox: {resp.status_code}"}
            data = resp.json()
            if "message" in data and data["message"]:
                data["message"] = MemoryManager.sanitize_untrusted_text(data["message"])
            return data
    except Exception as e:
        return _handle_request_error(e)


def browser_type(ref: Any, text: str, approved: bool = False) -> Dict[str, Any]:
    """
    Inserisce testo in un campo del browser sandbox specificando il riferimento numerico [ref].
    Azione con effetti esterni: richiede approvazione esplicita dell'utente prima dell'esecuzione fisica.
    """
    if not approved:
        return {
            "status": "waiting_approval",
            "requires_approval": True,
            "action_type": "browser_action",
            "tool_name": "browser_type",
            "ref": ref,
            "text": text,
            "message": f"Inserimento testo nel riferimento [{ref}] del browser sandbox richiede l'approvazione dell'utente.",
        }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(f"{SANDBOX_BASE_URL}/type", json={"ref": ref, "text": text})
            if resp.status_code != 200:
                return {"status": "error", "message": f"Errore HTTP sandbox: {resp.status_code}"}
            data = resp.json()
            if "message" in data and data["message"]:
                data["message"] = MemoryManager.sanitize_untrusted_text(data["message"])
            return data
    except Exception as e:
        return _handle_request_error(e)


def browser_close() -> Dict[str, Any]:
    """Chiude la sessione corrente del browser sandbox."""
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(f"{SANDBOX_BASE_URL}/close")
            if resp.status_code != 200:
                return {"status": "error", "message": f"Errore HTTP sandbox: {resp.status_code}"}
            return resp.json()
    except Exception as e:
        return _handle_request_error(e)
