"""
CoworkerOS Fast Path Router (Fase 4)
Router deterministico per richieste semplici, esplicite e non ambigue.
Esegue direttamente i tool backend in sola lettura senza overhead LLM (<150ms).
Bypassa immediatamente verso Qwen per compiti che richiedono ragionamento, sintesi, interpretazione o multi-step.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional, Tuple

import tools_os
from local_model_manager import local_model_mgr, get_system_ram_info, get_system_power_info


# Parole chiave che indicano necessità di ragionamento, analisi, sintesi o interpretazione
REASONING_VERBS = (
    "analizza", "spiega", "perché", "perche", "riassumi", "sintetizza", "confronta",
    "correggi", "cosa ne pensi", "cosa significa", "valuta", "consiglia", "opinione",
    "elabora", "commenta", "interpreta", "dimmi qual è la parola chiave",
    "parola chiave segreta", "trova il significato", "pianifica", "progetta",
    "secondo te", "come mai", "istruzioni", "cosa c'è", "cosa ce", "dimmi cosa", "estrai"
)

# Parole chiave che indicano modifiche fisiche o distruttive (NON ammesse in fast path)
MUTATION_KEYWORDS = (
    "scrivi", "elimina", "cancella", "rimuovi", "sposta", "crea", "sovrascrivi",
    "modifica", "clicca", "premi", "incolla", "apri app", "avvia"
)


class FastPathRouter:
    """Valuta le richieste in modo deterministico e sicuro."""

    @staticmethod
    def is_fast_path_candidate(text: str) -> bool:
        t_clean = text.strip().lower()
        if not t_clean or len(t_clean) > 220:
            return False

        # Se ci sono richieste di interpretazione o verbi di ragionamento -> Qwen
        if any(v in t_clean for v in REASONING_VERBS):
            return False

        # Se ci sono azioni di scrittura o modifiche -> human-in-the-loop / Qwen
        if any(m in t_clean for m in MUTATION_KEYWORDS):
            return False

        # Se sono presenti connettori multi-step ("poi", "quindi", "dopo", "e poi", "inoltre") -> Qwen
        if any(conn in t_clean for conn in (" poi ", " e poi ", " quindi ", " successivamente ", " dopodiché ", " dopodiche ")):
            return False

        return True

    @classmethod
    def try_route(cls, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Analizza la richiesta deterministica.
        Se c'è corrispondenza univoca, restituisce (action_type, params).
        Altrimenti restituisce None.
        """
        if not cls.is_fast_path_candidate(text):
            return None

        t = text.strip().lower()
        # Rimuove punteggiatura finale
        t_norm = re.sub(r"[?!.]+$", "", t).strip()

        greetings = {
            "ciao": "Ciao! Come posso aiutarti?",
            "salve": "Salve! Dimmi cosa vuoi fare.",
            "buongiorno": "Buongiorno! Come posso aiutarti?",
            "buonasera": "Buonasera! Come posso aiutarti?",
        }

        if t_norm in greetings:
            return ("direct_reply", {"content": greetings[t_norm]})

        # 1. Elenco finestre aperte
        if re.search(r"^(?:elenca|mostra|quali sono le|lista delle?|quali app sono|visualizza)\s+(?:le\s+)?finestre(?:\s+aperte|\s+attive)?(?:\s+sul\s+desktop)?$", t_norm):
            return ("list_windows", {})
        if t_norm in ("finestre aperte", "finestre attive", "mostrami le finestre", "mostra finestre", "elenca finestre", "elenca le finestre"):
            return ("list_windows", {})

        # 2. Stato CoworkerOS / Sistema / RAM / Modello
        if re.search(r"^(?:stato|status)\s+(?:del\s+sistema|di\s+coworkeros|di\s+qwen|del\s+modello|della\s+ram)$", t_norm):
            return ("system_status", {})
        if t_norm in ("quanta ram è libera", "quanta ram abbiamo", "ram disponibile", "stato modello", "stato sistema", "stato coworkerOS", "stato di coworkerOS"):
            return ("system_status", {})

        # 3. Ricerca di un file per nome
        # Es: "cerca il file sample_doc.txt all'interno della cartella test_data"
        m_search = re.search(
            r"^(?:cerca|trova|dove si trova)\s+(?:il\s+)?file\s+['\"]?([\w\.\-]+)['\"]?(?:\s+(?:all'interno|dentro|nella\s+cartella|in)\s+['\"]?([\w\.\-/]+)['\"]?)?$",
            t_norm
        )
        if m_search:
            q = m_search.group(1).strip()
            p = (m_search.group(2) or ".").strip()
            return ("search_files", {"query": q, "path": p})

        # Es: "cerca sample_doc.txt nella cartella test_data"
        m_search2 = re.search(r"^cerca\s+['\"]?([\w\.\-]+)['\"]?\s+(?:nella\s+cartella|in)\s+['\"]?([\w\.\-/]+)['\"]?$", t_norm)
        if m_search2:
            return ("search_files", {"query": m_search2.group(1).strip(), "path": m_search2.group(2).strip()})

        # 4. Lettura file con percorso esplicito
        # Es: "leggi il file test_data/sample_doc.txt" o "leggi test_data/sample_doc.txt"
        m_read = re.search(
            r"^(?:leggi|mostra\s+il\s+contenuto\s+di|apri\s+in\s+lettura|leggi\s+il\s+contenuto\s+di)\s+(?:il\s+)?(?:file\s+)?['\"]?([\w\.\-/\\]+\.\w+)['\"]?$",
            t_norm
        )
        if m_read:
            return ("read_document", {"path": m_read.group(1).strip()})

        # 5. Elenco cartella
        # Es: "elenca i file nella cartella test_data", "elenca la cartella backend"
        m_dir = re.search(
            r"^(?:elenca|mostra)\s+(?:il\s+contenuto\s+della|i\s+file\s+nella|la)?\s*cartella\s+['\"]?([\w\.\-/\\]+)['\"]?$",
            t_norm
        )
        if m_dir:
            return ("list_directory", {"path": m_dir.group(1).strip()})

        # 6. Ispezione archivio ZIP
        # Es: "ispeziona l'archivio test_data/sample_archive.zip"
        m_zip = re.search(
            r"^(?:elenca\s+i\s+file\s+nello\s+zip|ispeziona\s+l'archivio|mostra\s+i\s+file\s+nell'archivio|ispeziona\s+lo\s+zip)\s+['\"]?([\w\.\-/\\]+\.zip)['\"]?$",
            t_norm
        )
        if m_zip:
            return ("inspect_zip", {"zip_path": m_zip.group(1).strip(), "action": "list"})

        return None

    @classmethod
    async def execute_fast_path(
        cls,
        action: str,
        params: Dict[str, Any],
        bot_id: str = "chief"
    ) -> Dict[str, Any]:
        """
        Esegue l'operazione in modalità Fast Path ultra-veloce senza passare per l'LLM.
        """
        t0 = time.time()

        if action == "direct_reply":
            return {
                "handled": True,
                "tool_name": "direct_reply",
                "content": params["content"],
                "duration_ms": 0,
            }

        if action == "list_windows":
            res = tools_os.list_windows()
            dur_ms = int((time.time() - t0) * 1000)
            wins = res.get("windows", [])
            w_preview = "\n".join([f"- `{w}`" for w in wins[:8]]) or "*Nessuna finestra rilevata.*"
            content = (
                f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                f"🪟 **Finestre Windows Attive ({len(wins)}):**\n{w_preview}"
            )
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "list_windows",
                "tool_result": res,
                "duration_ms": dur_ms,
            }

        elif action == "system_status":
            ram = get_system_ram_info()
            power = get_system_power_info()
            m_status = local_model_mgr.get_status()
            dur_ms = int((time.time() - t0) * 1000)

            p_state = "In carica / Alimentazione AC 🔌" if power.get("ac_power") else f"Batteria ({power.get('battery_percent', 0)}%) 🔋"
            content = (
                f"⚡ **Fast Path — Stato del Sistema CoworkerOS (0s LLM):**\n\n"
                f"- **RAM Totale:** {ram.get('total_gb', 0)} GB\n"
                f"- **RAM Disponibile:** {ram.get('available_gb', 0)} GB ({ram.get('used_percent', 0)}% occupata)\n"
                f"- **Alimentazione:** {p_state}\n"
                f"- **Modello Locale:** Qwen3.5-4B Q4_K_M (`llama-server` PID: {m_status.get('server_pid') or 'Non attivo'})\n"
                f"- **Stato Server:** {'Attivo e pronto' if m_status.get('server_running') else 'Spento (avvio on-demand)'}\n"
                f"- **RSS Memoria Server:** {m_status.get('server_rss_mb', 0)} MB\n"
                f"- **Configurazione CPU:** 6 thread calcolo, 8 thread batch, priorità alta (--prio 2)"
            )
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "system_status",
                "tool_result": {"ram": ram, "power": power, "model": m_status},
                "duration_ms": dur_ms,
            }

        elif action == "search_files":
            q = params.get("query", "")
            p = params.get("path", ".")
            res = tools_os.search_files(q, p)
            dur_ms = int((time.time() - t0) * 1000)
            tot = res.get("total_matches", 0)
            matches = res.get("matches", [])
            if tot > 0:
                list_str = "\n".join([f"- `{m['relative_path']}` ({m['size_bytes']} bytes)" for m in matches[:6]])
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"🔎 **File trovato ('{q}'):**\n{list_str}"
                )
            else:
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"🔎 Nessun file corrispondente a '{q}' trovato nel percorso `{p}`."
                )
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "search_files",
                "tool_result": res,
                "duration_ms": dur_ms,
            }

        elif action == "read_document":
            p = params.get("path", "")
            res = tools_os.read_document(p, max_lines=200)
            dur_ms = int((time.time() - t0) * 1000)
            if res.get("status") == "ok":
                content_text = res.get("content", "").strip()
                if len(content_text) > 800:
                    content_text = content_text[:800] + "\n... [troncato per brevità]"
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"📄 **Lettura Documento (`{p}`, {res.get('line_count')} righe):**\n```text\n{content_text}\n```"
                )
            else:
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"⚠️ **Errore lettura documento:** {res.get('message')}"
                )
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "read_document",
                "tool_result": res,
                "duration_ms": dur_ms,
            }

        elif action == "list_directory":
            p = params.get("path", ".")
            res = tools_os.manage_files(action="list", path=p, approved=False)
            dur_ms = int((time.time() - t0) * 1000)
            if res.get("status") == "ok":
                entries = res.get("entries", [])
                e_str = "\n".join([f"- `{'[DIR]' if e.get('is_dir') else '[FILE]'} {e.get('name')}`" for e in entries[:10]])
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"📁 **Contenuto Cartella (`{p}`):**\n{e_str}"
                )
            else:
                content = f"⚡ **Fast Path:** ⚠️ {res.get('message')}"
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "manage_files",
                "tool_result": res,
                "duration_ms": dur_ms,
            }

        elif action == "inspect_zip":
            zp = params.get("zip_path", "")
            res = tools_os.inspect_zip(zp, action="list")
            dur_ms = int((time.time() - t0) * 1000)
            if res.get("status") == "ok":
                files = res.get("entries", [])
                f_str = "\n".join([f"- `{f['filename']}` ({f.get('file_size', f.get('size_bytes', 0))} bytes)" for f in files[:8]])
                content = (
                    f"⚡ **Fast Path (Esecuzione Istantanea — 0s LLM):**\n\n"
                    f"📦 **Archivio ZIP (`{zp}`, {res.get('total_entries')} elementi):**\n{f_str}"
                )
            else:
                content = f"⚡ **Fast Path:** ⚠️ {res.get('message')}"
            return {
                "handled": True,
                "action": action,
                "content": content,
                "tool_name": "inspect_zip",
                "tool_result": res,
                "duration_ms": dur_ms,
            }

        return {
            "handled": False,
            "error": "Azione fast path non supportata."
        }
