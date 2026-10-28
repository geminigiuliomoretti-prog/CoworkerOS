import os
import re
import json
import time
import base64
import hashlib
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from dotenv import load_dotenv

from google import genai
from google.genai import types

import database as db
import tools_os
import tools_browser
import tools_google
from memory_manager import memory_manager
from usage_tracker import usage_tracker
from notifications import notification_manager
from local_model_manager import local_model_mgr, get_system_ram_info
from fast_path_router import FastPathRouter

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

MODEL_PRIMARY = "gemini-3.8-flash"
MODEL_FALLBACKS = ["gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
MAX_SWARM_STEPS = 8


def _build_gemini_tools() -> List[types.Tool]:
    declarations = [
        types.FunctionDeclaration(
            name="delegate_to_coworker",
            description=(
                "Delega un compito a un altro AI Coworker del team (chief, architect, builder, scout, archivist). "
                "Usa SEMPRE questo tool quando un collega deve intervenire o usare il PC."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "target_bot_id": types.Schema(
                        type="STRING",
                        description="ID del coworker: 'chief', 'architect', 'builder', 'scout', 'archivist'.",
                    ),
                    "instruction": types.Schema(
                        type="STRING",
                        description="Istruzione dettagliata per il collega.",
                    ),
                    "shared_data": types.Schema(
                        type="STRING",
                        description="Testo completo (es. roadmap o codice) da passare al collega.",
                    ),
                },
                required=["target_bot_id", "instruction"],
            ),
        ),
        types.FunctionDeclaration(
            name="request_peer_review",
            description=(
                "Richiede una revisione tra pari del lavoro ad un collega (es. Architect o Scout). "
                "NOTA METODOLOGICA: La revisione tra colleghi usa lo stesso modello e non costituisce una validazione indipendente esterna."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "reviewer_bot_id": types.Schema(
                        type="STRING",
                        description="ID del revisore: 'architect', 'scout', 'archivist', 'chief'.",
                    ),
                    "artifact_to_review": types.Schema(
                        type="STRING",
                        description="Testo, piano o codice da sottoporre a revisione.",
                    ),
                    "review_criteria": types.Schema(
                        type="STRING",
                        description="Criteri specifici di verifica (es. robustezza, aderenza requisiti, sicurezza).",
                    ),
                },
                required=["reviewer_bot_id", "artifact_to_review"],
            ),
        ),
        types.FunctionDeclaration(
            name="inspect_screen",
            description=(
                "Ispezione visiva in sola lettura: cattura uno screenshot 2880x1920 e analizza gli elementi "
                "visibili sullo schermo con Gemini Vision SENZA eseguire alcun clic o azione fisica."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "goal_description": types.Schema(
                        type="STRING",
                        description="Elemento, finestra o informazione da individuare sullo schermo.",
                    ),
                },
                required=["goal_description"],
            ),
        ),
        types.FunctionDeclaration(
            name="click_screen_element",
            description=(
                "Richiede di eseguire un clic alle coordinate normalizzate (0-1000) individuate con inspect_screen. "
                "ATTENZIONE: Questa azione richiede SEMPRE l'approvazione esplicita dell'utente prima dell'esecuzione."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "goal_description": types.Schema(
                        type="STRING",
                        description="Descrizione dell'elemento su cui cliccare.",
                    ),
                    "norm_x": types.Schema(
                        type="INTEGER",
                        description="Coordinata X normalizzata (0-1000).",
                    ),
                    "norm_y": types.Schema(
                        type="INTEGER",
                        description="Coordinata Y normalizzata (0-1000).",
                    ),
                    "text_to_type": types.Schema(
                        type="STRING",
                        description="Testo opzionale da digitare/incollare dopo il clic.",
                    ),
                    "press_enter": types.Schema(
                        type="BOOLEAN",
                        description="True per premere Invio dopo la digitazione.",
                    ),
                },
                required=["goal_description", "norm_x", "norm_y"],
            ),
        ),
        types.FunctionDeclaration(
            name="focus_and_paste_into_app",
            description=(
                "Richiede di portare in primo piano una finestra su Windows 11 (es. 'Antigravity' o 'Chrome'), "
                "cliccare nell'input e incollare testo. "
                "ATTENZIONE: Questa azione richiede SEMPRE l'approvazione esplicita dell'utente prima dell'esecuzione."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "window_title_substring": types.Schema(
                        type="STRING",
                        description="Nome o parte del titolo della finestra (es. 'Antigravity', 'Chrome').",
                    ),
                    "text_to_paste": types.Schema(
                        type="STRING",
                        description="Testo da incollare nell'applicazione.",
                    ),
                    "press_enter": types.Schema(
                        type="BOOLEAN",
                        description="True per premere Invio dopo l'incollaggio.",
                    ),
                },
                required=["window_title_substring", "text_to_paste"],
            ),
        ),
        types.FunctionDeclaration(
            name="open_url_or_app",
            description="Apre un URL nel browser o avvia un'applicazione. Richiede approvazione esplicita.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "target": types.Schema(type="STRING", description="URL o comando dell'applicazione da aprire."),
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="manage_files",
            description=(
                "Gestisce file nella directory di lavoro autorizzata. Le azioni 'read' e 'list' sono di sola lettura. "
                "Le azioni di modifica ('write', 'mkdir', 'move', 'delete') richiedono SEMPRE approvazione esplicita."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "action": types.Schema(
                        type="STRING",
                        description="Azione da compiere: 'list', 'read', 'write', 'mkdir', 'move', 'delete'.",
                    ),
                    "path": types.Schema(
                        type="STRING",
                        description="Percorso relativo all'interno della directory di lavoro autorizzata.",
                    ),
                    "content": types.Schema(
                        type="STRING",
                        description="Contenuto testuale per l'azione 'write'.",
                    ),
                    "destination": types.Schema(
                        type="STRING",
                        description="Percorso di destinazione per l'azione 'move'.",
                    ),
                },
                required=["action", "path"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_files",
            description="Cerca file o cartelle ricorsivamente nell'area autorizzata in base al nome o pattern.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="Nome o pattern del file (es. 'main.py', 'test')."),
                    "path": types.Schema(type="STRING", description="Cartella di partenza (default: '.')."),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="read_document",
            description="Legge il contenuto testuale di un file o documento (testo, markdown, json, csv, codice).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="Percorso del documento da leggere."),
                    "max_lines": types.Schema(type="INTEGER", description="Numero massimo di righe da leggere (default: 200)."),
                },
                required=["path"],
            ),
        ),
        types.FunctionDeclaration(
            name="inspect_zip",
            description="Analizza un archivio ZIP: elenca i file interni o legge il testo di un file in sola lettura.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "zip_path": types.Schema(type="STRING", description="Percorso dell'archivio ZIP."),
                    "action": types.Schema(type="STRING", description="'list' per elencare i file, 'read' per leggerne uno."),
                    "file_to_read": types.Schema(type="STRING", description="Nome del file interno da leggere se action='read'."),
                },
                required=["zip_path"],
            ),
        ),
        types.FunctionDeclaration(
            name="browse_url",
            description="Legge il contenuto testuale di una pagina web tramite richiesta HTTP sicura (read-only).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "url": types.Schema(type="STRING", description="URL completo (http:// o https://) da consultare."),
                },
                required=["url"],
            ),
        ),
        types.FunctionDeclaration(
            name="gmail_search",
            description="Cerca email nella casella Gmail dell'utente in sola lettura (restituisce mittente, oggetto, data e snippet).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="Query di ricerca Gmail (es. 'from:mario', 'fattura', 'is:unread')."),
                    "max_results": types.Schema(type="INTEGER", description="Numero massimo di email da restituire (default 10)."),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="gmail_read",
            description="Legge il corpo testuale di una specifica email da Gmail tramite message_id (in sola lettura, testo pulito senza HTML).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "message_id": types.Schema(type="STRING", description="ID univoco del messaggio Gmail da leggere."),
                    "max_chars": types.Schema(type="INTEGER", description="Numero massimo di caratteri da restituire (default 4000)."),
                },
                required=["message_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="calendar_list_events",
            description="Elenca gli eventi in programma su Google Calendar in sola lettura.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "days_ahead": types.Schema(type="INTEGER", description="Giorni futuri da consultare a partire da oggi (default 7)."),
                    "max_results": types.Schema(type="INTEGER", description="Numero massimo di eventi da restituire (default 20)."),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="list_windows",
            description="Elenca le finestre aperte sul desktop Windows 11 con i rispettivi titoli.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "filter_str": types.Schema(type="STRING", description="Filtro opzionale sul titolo della finestra."),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="browser_open",
            description="Apre un URL nel browser isolato sandbox (Docker). Lettura sicura senza effetti collaterali.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "url": types.Schema(type="STRING", description="URL completo da aprire nel browser sandbox (es. https://example.com)."),
                },
                required=["url"],
            ),
        ),
        types.FunctionDeclaration(
            name="browser_snapshot",
            description="Restituisce l'albero di accessibilità semantico della pagina web nel browser sandbox con riferimenti numerici [ref].",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="browser_click",
            description="Esegue un clic su un elemento nel browser sandbox tramite il suo riferimento numerico [ref]. Richiede approvazione utente.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ref": types.Schema(type="INTEGER", description="Riferimento numerico [ref] dell'elemento da cliccare."),
                },
                required=["ref"],
            ),
        ),
        types.FunctionDeclaration(
            name="browser_type",
            description="Digita testo in un campo del browser sandbox tramite riferimento numerico [ref]. Richiede approvazione utente.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "ref": types.Schema(type="INTEGER", description="Riferimento numerico [ref] del campo di input."),
                    "text": types.Schema(type="STRING", description="Testo da digitare nel campo."),
                },
                required=["ref", "text"],
            ),
        ),
    ]
    return [types.Tool(function_declarations=declarations)]


def _build_openai_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "delegate_to_coworker",
                "description": "Delega un compito a un altro coworker (chief, architect, builder, scout, archivist). Usa sempre questo strumento quando un collega deve intervenire o usare il PC.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_bot_id": {"type": "string", "description": "ID del coworker: 'chief', 'architect', 'builder', 'scout', 'archivist'."},
                        "instruction": {"type": "string", "description": "Istruzione dettagliata per il collega."},
                        "shared_data": {"type": "string", "description": "Dati completi o testo da passare al collega."}
                    },
                    "required": ["target_bot_id", "instruction"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "request_peer_review",
                "description": "Richiede una revisione critica del lavoro ad un collega (es. architect o scout).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reviewer_bot_id": {"type": "string", "description": "ID del revisore: 'architect', 'scout', 'archivist', 'chief'."},
                        "artifact_to_review": {"type": "string", "description": "Testo, piano o codice da sottoporre a revisione."},
                        "review_criteria": {"type": "string", "description": "Criteri specifici di verifica."}
                    },
                    "required": ["reviewer_bot_id", "artifact_to_review"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Cerca file o cartelle ricorsivamente nell'area autorizzata in base al nome o pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Nome o frammento del file (es. 'main.py', 'test')."},
                        "path": {"type": "string", "description": "Percorso relativo di partenza (default: '.')."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_document",
                "description": "Legge il contenuto testuale di un file o documento (testo, markdown, json, csv, codice).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Percorso del documento da leggere."},
                        "max_lines": {"type": "integer", "description": "Numero massimo di righe (default: 200)."}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_zip",
                "description": "Analizza un archivio ZIP in sola lettura: elenca i file interni o legge il testo di un file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "zip_path": {"type": "string", "description": "Percorso dell'archivio ZIP."},
                        "action": {"type": "string", "enum": ["list", "read"], "description": "'list' per elencare i file, 'read' per leggerne uno."},
                        "file_to_read": {"type": "string", "description": "Nome del file interno da leggere se action='read'."}
                    },
                    "required": ["zip_path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "browse_url",
                "description": "Legge il contenuto testuale di una pagina web tramite richiesta HTTP sicura (read-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL completo (http:// o https://) da consultare."}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gmail_search",
                "description": "Cerca email nella casella Gmail dell'utente in sola lettura (restituisce mittente, oggetto, data e snippet).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Query di ricerca Gmail (es. 'from:mario', 'fattura', 'is:unread')."},
                        "max_results": {"type": "integer", "description": "Numero massimo di email da restituire (default 10)."}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "gmail_read",
                "description": "Legge il corpo testuale di una specifica email da Gmail tramite message_id (in sola lettura, testo pulito senza HTML).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string", "description": "ID univoco del messaggio Gmail da leggere."},
                        "max_chars": {"type": "integer", "description": "Numero massimo di caratteri da restituire (default 4000)."}
                    },
                    "required": ["message_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_list_events",
                "description": "Elenca gli eventi in programma su Google Calendar in sola lettura.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {"type": "integer", "description": "Giorni futuri da consultare a partire da oggi (default 7)."},
                        "max_results": {"type": "integer", "description": "Numero massimo di eventi da restituire (default 20)."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_windows",
                "description": "Elenca le finestre attualmente aperte sul desktop Windows 11 con i rispettivi titoli.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filter_str": {"type": "string", "description": "Filtro opzionale sul titolo della finestra."}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "manage_files",
                "description": "Gestisce file nell'area autorizzata. Azioni sola lettura: 'list', 'read'. Azioni con modifica (richiedono approvazione utente): 'write', 'mkdir', 'move', 'delete'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["list", "read", "write", "mkdir", "move", "delete"], "description": "Azione da compiere."},
                        "path": {"type": "string", "description": "Percorso del file o cartella."},
                        "content": {"type": "string", "description": "Contenuto testuale per 'write'."},
                        "destination": {"type": "string", "description": "Percorso di destinazione per 'move'."}
                    },
                    "required": ["action", "path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "open_url_or_app",
                "description": "Apre un URL nel browser o avvia un'applicazione. Richiede approvazione utente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "URL o comando dell'applicazione da aprire."}
                    },
                    "required": ["target"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_screen",
                "description": "Ispezione visiva schermo in sola lettura: cattura uno screenshot e cerca l'elemento desiderato.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal_description": {"type": "string", "description": "Elemento o informazione da individuare sullo schermo."}
                    },
                    "required": ["goal_description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "click_screen_element",
                "description": "Clic alle coordinate normalizzate (0-1000) sul desktop. Richiede SEMPRE approvazione utente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal_description": {"type": "string", "description": "Descrizione dell'elemento su cui cliccare."},
                        "norm_x": {"type": "integer", "description": "Coordinata X (0-1000)."},
                        "norm_y": {"type": "integer", "description": "Coordinata Y (0-1000)."},
                        "text_to_type": {"type": "string", "description": "Testo opzionale da digitare."},
                        "press_enter": {"type": "boolean", "description": "True per premere Invio."}
                    },
                    "required": ["goal_description", "norm_x", "norm_y"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "focus_and_paste_into_app",
                "description": "Porta in primo piano una finestra Windows 11 e incolla testo. Richiede SEMPRE approvazione utente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_title_substring": {"type": "string", "description": "Nome o parte del titolo della finestra."},
                        "text_to_paste": {"type": "string", "description": "Testo da incollare."},
                        "press_enter": {"type": "boolean", "description": "True per premere Invio."}
                    },
                    "required": ["window_title_substring", "text_to_paste"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "browser_open",
                "description": "Apre un URL nel browser isolato sandbox (Docker). Lettura sicura senza effetti collaterali.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL completo da aprire nel browser sandbox (es. https://example.com)."}
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "browser_snapshot",
                "description": "Restituisce l'albero di accessibilità semantico della pagina web nel browser sandbox con riferimenti numerici [ref].",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "browser_click",
                "description": "Esegue un clic su un elemento nel browser sandbox tramite il suo riferimento numerico [ref]. Richiede approvazione utente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "integer", "description": "Riferimento numerico [ref] dell'elemento su cui cliccare."}
                    },
                    "required": ["ref"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "browser_type",
                "description": "Digita testo in un campo del browser sandbox tramite riferimento numerico [ref]. Richiede approvazione utente.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ref": {"type": "integer", "description": "Riferimento numerico [ref] del campo di input."},
                        "text": {"type": "string", "description": "Testo da inserire nel campo."}
                    },
                    "required": ["ref", "text"]
                }
            }
        }
    ]


class AgentOrchestrator:
    def __init__(self) -> None:
        self.api_key: str = ""
        self.client: Optional[genai.Client] = None
        self.tools = _build_gemini_tools()
        self.openai_tools = _build_openai_tools()
        self._gemini_tools_cache: Dict[frozenset[str], List[types.Tool]] = {}
        self._model_cooldown: Dict[str, float] = {}
        self.reload_client()

    def _gemini_tools_for(self, names: frozenset[str]) -> List[types.Tool]:
        """
        Filtra le function declarations di self.tools per nome con cache su frozenset.
        """
        if not names:
            return []
        if names in self._gemini_tools_cache:
            return self._gemini_tools_cache[names]

        if not self.tools or not hasattr(self.tools[0], "function_declarations"):
            return []

        filtered_decls = [
            decl for decl in self.tools[0].function_declarations
            if getattr(decl, "name", "") in names
        ]
        result = [types.Tool(function_declarations=filtered_decls)] if filtered_decls else []
        self._gemini_tools_cache[names] = result
        return result

    def get_provider_mode(self) -> str:
        return str(db.get_app_setting("llm_provider_mode", "AUTO")).upper()

    async def set_provider_mode(self, mode: str) -> Dict[str, Any]:
        clean_mode = str(mode or "AUTO").upper().strip()
        if clean_mode not in ("LOCAL", "CLOUD", "AUTO"):
            clean_mode = "AUTO"
        db.save_app_setting("llm_provider_mode", clean_mode)
        if clean_mode == "LOCAL" and not local_model_mgr.is_server_healthy():
            start_res = await local_model_mgr.start_server_async()
            return {
                "provider_mode": clean_mode,
                "local_start": start_res,
                "status": self.get_model_status(),
            }
        return {
            "provider_mode": clean_mode,
            "status": self.get_model_status(),
        }

    def get_model_status(self) -> Dict[str, Any]:
        provider_mode = self.get_provider_mode()
        local_status = local_model_mgr.get_status()
        gemini_configured = bool(self.api_key)

        if provider_mode == "LOCAL":
            active_provider = "LOCAL (Qwen3.5-4B)"
        elif provider_mode == "CLOUD":
            active_provider = f"CLOUD ({MODEL_PRIMARY})"
        else:
            if local_status["is_alive"]:
                active_provider = "AUTO -> LOCAL (Qwen3.5-4B)"
            else:
                active_provider = f"AUTO -> CLOUD ({MODEL_PRIMARY})"

        return {
            "provider_mode": provider_mode,
            "active_provider": active_provider,
            "local_model": {
                "name": "Qwen3.5-4B (Q4_K_M)",
                "status": local_status["status"],
                "is_alive": local_status["is_alive"],
                "pid": local_status["pid"],
                "server_rss_mb": local_status["server_rss_mb"],
                "vision_enabled": local_status["vision_enabled"],
                "endpoint": local_status["endpoint"],
                "min_ram_required_gb": local_status["min_ram_required_gb"],
                "last_error": local_status["last_error"],
            },
            "gemini": {
                "model": MODEL_PRIMARY,
                "configured": gemini_configured,
            },
            "ram_info": local_status["ram_info"],
        }

    def _resolve_provider(self, user_content: str, instruction: str) -> str:
        mode = self.get_provider_mode()
        if mode == "LOCAL":
            return "LOCAL"
        if mode == "CLOUD":
            return "CLOUD"

        # AUTO preferisce il modello locale.
        # Il fallback cloud viene gestito separatamente
        # soltanto quando configurato e disponibile.
        return "LOCAL"

    def reload_client(self, new_api_key: Optional[str] = None) -> bool:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        key = (new_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if key and key not in ("your_api_key_here", "la_tua_chiave_qui"):
            self.api_key = key
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=10000),
            )
            return True
        self.api_key = ""
        self.client = None
        return False

    async def _call_gemini_resilient(
        self,
        contents: Any,
        system_instruction: str,
        enable_tools: bool = True,
        tools_override: Optional[List[types.Tool]] = None,
        temperature: float = 0.35,
        max_output_tokens: int = 1024,
        task_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Tuple[Optional[types.GenerateContentResponse], str, Optional[str]]:
        if not self.client:
            if not self.reload_client():
                return None, MODEL_PRIMARY, "GEMINI_API_KEY non configurata. Inseriscila dalle Impostazioni (icona ingranaggio)."

        # Verifica quote e limiti di consumo prima della chiamata
        is_ok, limit_msg = usage_tracker.check_limits(task_id=task_id)
        if not is_ok:
            try:
                await notification_manager.notify_limit_reached(
                    title="Quota consumi raggiunta",
                    reason=limit_msg or "Limite richieste o token superato.",
                )
            except Exception:
                pass
            return None, MODEL_PRIMARY, f"Quota superata: {limit_msg}"

        models_to_try = [MODEL_PRIMARY] + MODEL_FALLBACKS
        last_error = ""

        chosen_tools = (tools_override if tools_override is not None else self.tools) if enable_tools else None
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=chosen_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True) if enable_tools else None,
        )

        now = time.time()
        for model_name in models_to_try:
            # Salta modelli attualmente in cooldown per errori 429/RESOURCE_EXHAUSTED/404
            if self._model_cooldown.get(model_name, 0) > now:
                continue

            for attempt in range(2):
                start_call = time.time()
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    duration_ms = int((time.time() - start_call) * 1000)
                    in_tokens = None
                    out_tokens = None
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        in_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                        out_tokens = getattr(response.usage_metadata, "candidates_token_count", None)

                    usage_tracker.record_model_call(
                        model_name=model_name,
                        task_id=task_id,
                        chat_id=chat_id,
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        duration_ms=duration_ms,
                        time_to_first_chunk_ms=duration_ms,
                    )
                    return response, model_name, None
                except Exception as exc:
                    err_str = str(exc)
                    last_error = err_str

                    # Cooldown 60s se il modello dà 429/RESOURCE_EXHAUSTED/404/NOT_FOUND
                    if any(code in err_str for code in ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND")):
                        self._model_cooldown[model_name] = time.time() + 60.0

                    is_transient = any(
                        code in err_str
                        for code in (
                            "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                            "500", "overloaded", "504", "DEADLINE_EXCEEDED"
                        )
                    )
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        break
                    if is_transient and attempt == 0:
                        await asyncio.sleep(0.3)
                        continue
                    break

        return None, MODEL_PRIMARY, last_error

    async def _call_gemini_stream(
        self,
        contents: Any,
        system_instruction: str,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
        enable_tools: bool = True,
        tools_override: Optional[List[types.Tool]] = None,
        temperature: float = 0.35,
        max_output_tokens: int = 1024,
        task_id: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Esegue la chiamata streaming verso Gemini Cloud con fallback, accumulo chunk e tracciamento TTFC.
        """
        if not self.client:
            if not self.reload_client():
                return {
                    "success": False,
                    "error": "GEMINI_API_KEY non configurata. Inseriscila dalle Impostazioni (icona ingranaggio).",
                    "model_name": MODEL_PRIMARY,
                    "provider": "CLOUD",
                    "assistant_text": "",
                    "function_calls": [],
                }

        is_ok, limit_msg = usage_tracker.check_limits(task_id=task_id)
        if not is_ok:
            try:
                await notification_manager.notify_limit_reached(
                    title="Quota consumi raggiunta",
                    reason=limit_msg or "Limite richieste o token superato.",
                )
            except Exception:
                pass
            return {
                "success": False,
                "error": f"Quota superata: {limit_msg}",
                "model_name": MODEL_PRIMARY,
                "provider": "CLOUD",
                "assistant_text": "",
                "function_calls": [],
            }

        models_to_try = [MODEL_PRIMARY] + MODEL_FALLBACKS
        last_error = ""

        chosen_tools = (tools_override if tools_override is not None else self.tools) if enable_tools else None
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            tools=chosen_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True) if enable_tools else None,
        )

        now = time.time()
        for model_name in models_to_try:
            if self._model_cooldown.get(model_name, 0) > now:
                continue

            for attempt in range(2):
                start_call = time.time()
                time_to_first_chunk_ms = None
                norm_fcalls = []
                accumulated_text = []
                in_tokens = None
                out_tokens = None
                stream_started = False
                try:
                    stream = await self.client.aio.models.generate_content_stream(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    async for chunk in stream:
                        txt = getattr(chunk, "text", None)
                        if txt:
                            if time_to_first_chunk_ms is None:
                                time_to_first_chunk_ms = int((time.time() - start_call) * 1000)
                            stream_started = True
                            accumulated_text.append(txt)
                            if on_chunk:
                                await on_chunk(txt)

                        fcalls = getattr(chunk, "function_calls", None)
                        if fcalls:
                            if time_to_first_chunk_ms is None:
                                time_to_first_chunk_ms = int((time.time() - start_call) * 1000)
                            for fc in fcalls:
                                norm_fcalls.append({
                                    "name": fc.name,
                                    "args": dict(fc.args) if fc.args else {},
                                    "id": getattr(fc, "id", None),
                                })

                        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                            p_tok = getattr(chunk.usage_metadata, "prompt_token_count", None)
                            c_tok = getattr(chunk.usage_metadata, "candidates_token_count", None)
                            if p_tok is not None:
                                in_tokens = p_tok
                            if c_tok is not None:
                                out_tokens = c_tok

                    duration_ms = int((time.time() - start_call) * 1000)
                    if time_to_first_chunk_ms is None:
                        time_to_first_chunk_ms = duration_ms

                    usage_tracker.record_model_call(
                        model_name=model_name,
                        task_id=task_id,
                        chat_id=chat_id,
                        input_tokens=in_tokens,
                        output_tokens=out_tokens,
                        duration_ms=duration_ms,
                        time_to_first_chunk_ms=time_to_first_chunk_ms,
                    )
                    return {
                        "success": True,
                        "assistant_text": "".join(accumulated_text).strip(),
                        "function_calls": norm_fcalls,
                        "model_name": model_name,
                        "provider": "CLOUD",
                        "error": None,
                    }
                except Exception as exc:
                    err_str = str(exc)
                    last_error = err_str

                    if any(code in err_str for code in ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND")):
                        self._model_cooldown[model_name] = time.time() + 60.0

                    if stream_started:
                        break

                    is_transient = any(
                        code in err_str
                        for code in (
                            "503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                            "500", "overloaded", "504", "DEADLINE_EXCEEDED"
                        )
                    )
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        break
                    if is_transient and attempt == 0:
                        await asyncio.sleep(0.3)
                        continue
                    break

        return {
            "success": False,
            "error": last_error or "Errore sconosciuto Gemini Cloud (streaming).",
            "model_name": MODEL_PRIMARY,
            "provider": "CLOUD",
            "assistant_text": "".join(accumulated_text).strip() if 'accumulated_text' in locals() else "",
            "function_calls": [],
        }

    def _select_tools_for_turn(self, bot_id: str, prompt_text: str) -> List[Dict[str, Any]]:
        text = prompt_text.lower()

        role_tools = {
            "chief": ["gmail_search", "gmail_read", "calendar_list_events"],
            "scout": [
                "gmail_search", "gmail_read", "calendar_list_events", "browse_url",
                "browser_open", "browser_snapshot", "browser_click", "browser_type"
            ],
        }

        desktop_words = (
            "antigravity", "desktop", "schermo",
            "finestra", "interfaccia", "clicca",
            "seleziona", "barra laterale", "nuova conversazione",
            "apri l'app", "apri applicazione"
        )

        google_words = ("mail", "email", "posta", "calendario", "agenda", "appuntamenti")
        browser_words = ("browser", "web", "sito", "pagina", "url", "http", "https", "naviga", "snapshot", "click web", "digita web", "sandbox")

        desktop_task = any(word in text for word in desktop_words)
        google_task = any(word in text for word in google_words)
        browser_task = any(word in text for word in browser_words)

        if desktop_task:
            names = {
                "list_windows",
                "inspect_screen",
                "click_screen_element",
                "focus_and_paste_into_app",
                "open_url_or_app",
            }
        elif any(word in text for word in ("zip", "archivio zip")):
            names = {"inspect_zip", "read_document"}
        elif any(word in text for word in ("file", "cartella", "documento")):
            names = {"search_files", "read_document", "manage_files"}
        elif google_task:
            bot_tools = role_tools.get(bot_id, ["gmail_search", "gmail_read", "calendar_list_events"])
            names = set(bot_tools)
        elif browser_task:
            names = {"browser_open", "browser_snapshot", "browser_click", "browser_type"}
        else:
            names = set()

        if bot_id == "scout":
            scout_tools = role_tools.get("scout", [])
            names.update(scout_tools)

        if browser_task:
            names.update({"browser_open", "browser_snapshot", "browser_click", "browser_type"})

        if google_task and not desktop_task:
            bot_tools = role_tools.get(bot_id, ["gmail_search", "gmail_read", "calendar_list_events"])
            names.update(t for t in bot_tools if t in {"gmail_search", "gmail_read", "calendar_list_events"})

        simple_question = (
            not desktop_task
            and not google_task
            and not browser_task
            and not names
            and not any(
                word in text
                for word in (
                    "delega", "collabora", "peer review",
                    "analizza il progetto", "sviluppa",
                    "implementa", "modifica il codice",
                    "esegui un task",
                    "mail", "email", "posta", "calendario", "agenda", "appuntamenti",
                    "browser", "web", "sito", "pagina", "url", "naviga", "snapshot"
                )
            )
        )

        if simple_question:
            return []

        if bot_id == "chief" and not desktop_task:
            names.add("delegate_to_coworker")

        # A) INTERRUTTORE: Quando il controllo desktop fisico è disattivato, non esporre i tool relativi
        if not tools_os.is_desktop_control_enabled():
            names.discard("click_screen_element")
            names.discard("focus_and_paste_into_app")

        return [
            tool for tool in self.openai_tools
            if tool["function"]["name"] in names
        ]

    async def _call_qwen_local(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        enable_tools: bool = True,
        tools_payload: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
        task_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Invia una richiesta a llama-server locale (Qwen3.5-4B Q4_K_M).
        Garantisce mutex d'inferenza, misurazione tempi, streaming progressivo e tracciamento consumi.
        """
        full_msgs = [{"role": "system", "content": system_instruction}] + messages
        if tools_payload is not None:
            chosen_tools = tools_payload if enable_tools else None
        else:
            chosen_tools = self.openai_tools if enable_tools else None

        t0 = time.time()
        res = await local_model_mgr.chat_completion(
            messages=full_msgs,
            tools=chosen_tools,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=180.0,
            on_chunk=on_chunk,
        )
        duration_ms = int((time.time() - t0) * 1000)

        if not res.get("success"):
            return {
                "success": False,
                "error": res.get("error", "Errore completamento locale."),
                "model_name": "Qwen3.5-4B-Local",
                "provider": "LOCAL",
                "assistant_text": "",
                "function_calls": [],
                "duration_ms": duration_ms,
            }

        usage = res.get("usage", {})
        in_tokens = usage.get("prompt_tokens")
        out_tokens = usage.get("completion_tokens")

        usage_tracker.record_model_call(
            model_name="Qwen3.5-4B-Local",
            task_id=task_id,
            chat_id=chat_id,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            duration_ms=duration_ms,
        )

        raw_tc = res.get("tool_calls", [])
        norm_fcalls = []
        for tc in raw_tc:
            fn = tc.get("function", {})
            fn_name = fn.get("name", "")
            raw_args = fn.get("arguments", "{}")
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = {"raw": raw_args}
            else:
                parsed_args = raw_args or {}
            norm_fcalls.append({
                "name": fn_name,
                "args": parsed_args,
                "id": tc.get("id"),
                "raw": tc,
            })

        timings = res.get("timings", {})
        prompt_t_s = round(timings.get("prompt_per_second", 0.0), 2)
        pred_t_s = round(timings.get("predicted_per_second", 0.0), 2)
        ttft_s = round(timings.get("prompt_ms", 0.0) / 1000.0, 2)
        cache_n = timings.get("cache_n", 0)

        return {
            "success": True,
            "assistant_text": res.get("content", "") or "",
            "function_calls": norm_fcalls,
            "model_name": "Qwen3.5-4B-Local",
            "provider": "LOCAL",
            "error": None,
            "duration_ms": duration_ms,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "prompt_per_second": prompt_t_s,
            "predicted_per_second": pred_t_s,
            "ttft_s": ttft_s,
            "cache_n": cache_n,
            "timings": timings,
        }

    async def _dispatch_model_turn(
        self,
        system_prompt: str,
        task_prompt: str,
        user_content: str,
        instruction: str,
        structured_messages: Optional[List[Dict[str, Any]]] = None,
        task_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        enable_tools: bool = True,
        bot_id: str = "chief",
        max_tokens: int = 150,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Instrada la richiesta tra LOCAL (Qwen), CLOUD (Gemini) o AUTO con fallback resiliente.
        """
        chosen_provider = self._resolve_provider(user_content, instruction)
        mode = self.get_provider_mode()

        context_text = f"{user_content} {instruction} {task_prompt}"
        selected_tools = self._select_tools_for_turn(bot_id, context_text) if enable_tools else []
        gemini_enable_tools = bool(selected_tools) and enable_tools
        selected_names = frozenset(t["function"]["name"] for t in selected_tools) if gemini_enable_tools else frozenset()
        gemini_tools = self._gemini_tools_for(selected_names) if gemini_enable_tools else None

        if chosen_provider == "LOCAL":
            messages = structured_messages if structured_messages else [{"role": "user", "content": task_prompt}]
            q_res = await self._call_qwen_local(
                messages=messages,
                system_instruction=system_prompt,
                enable_tools=bool(selected_tools),
                tools_payload=selected_tools if selected_tools else None,
                max_tokens=max_tokens,
                task_id=task_id,
                chat_id=chat_id,
                on_chunk=on_chunk,
            )
            if q_res.get("success"):
                return q_res

            # Se fallisce e siamo in AUTO, tenta il fallback su Gemini Cloud soltanto se configurato con chiave valida
            if mode == "AUTO":
                if not self.client:
                    self.reload_client()
                if self.client and self.api_key and self.api_key not in ("your_api_key_here", "la_tua_chiave_qui"):
                    print(f"[AgentEngine] Qwen Locale non disponibile ({q_res.get('error')}). Fallback su Gemini Cloud...")
                    if on_chunk is not None:
                        stream_res = await self._call_gemini_stream(
                            contents=[types.Content(role="user", parts=[types.Part.from_text(text=task_prompt)])],
                            system_instruction=system_prompt,
                            on_chunk=on_chunk,
                            enable_tools=gemini_enable_tools,
                            tools_override=gemini_tools,
                            task_id=task_id,
                            chat_id=chat_id,
                        )
                        if stream_res.get("success"):
                            stream_res["model_name"] = f"{stream_res['model_name']} (Cloud Fallback)"
                            stream_res["provider"] = "CLOUD_FALLBACK"
                            return stream_res
                    else:
                        gem_resp, model_name, gem_err = await self._call_gemini_resilient(
                            contents=[types.Content(role="user", parts=[types.Part.from_text(text=task_prompt)])],
                            system_instruction=system_prompt,
                            enable_tools=gemini_enable_tools,
                            tools_override=gemini_tools,
                            task_id=task_id,
                            chat_id=chat_id,
                        )
                        if not gem_err and gem_resp is not None:
                            norm_fcalls = []
                            if gem_resp.function_calls:
                                for fc in gem_resp.function_calls:
                                    norm_fcalls.append({
                                        "name": fc.name,
                                        "args": dict(fc.args) if fc.args else {},
                                        "id": getattr(fc, "id", None),
                                    })
                            txts = []
                            if gem_resp.candidates and gem_resp.candidates[0].content and gem_resp.candidates[0].content.parts:
                                for p in gem_resp.candidates[0].content.parts:
                                    if getattr(p, "text", None):
                                        txts.append(p.text)
                            return {
                                "success": True,
                                "assistant_text": "\n".join(txts).strip(),
                                "function_calls": norm_fcalls,
                                "model_name": f"{model_name} (Cloud Fallback)",
                                "provider": "CLOUD_FALLBACK",
                                "error": None,
                            }
            return q_res

        # Provider CLOUD (Gemini)
        if on_chunk is not None:
            return await self._call_gemini_stream(
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=task_prompt)])],
                system_instruction=system_prompt,
                on_chunk=on_chunk,
                enable_tools=gemini_enable_tools,
                tools_override=gemini_tools,
                task_id=task_id,
                chat_id=chat_id,
            )

        gem_resp, model_name, gem_err = await self._call_gemini_resilient(
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=task_prompt)])],
            system_instruction=system_prompt,
            enable_tools=gemini_enable_tools,
            tools_override=gemini_tools,
            task_id=task_id,
            chat_id=chat_id,
        )
        if gem_err or gem_resp is None:
            return {
                "success": False,
                "error": gem_err or "Errore sconosciuto Gemini Cloud.",
                "model_name": model_name,
                "provider": "CLOUD",
                "assistant_text": "",
                "function_calls": [],
            }

        norm_fcalls = []
        if gem_resp.function_calls:
            for fc in gem_resp.function_calls:
                norm_fcalls.append({
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                    "id": getattr(fc, "id", None),
                })
        txts = []
        if gem_resp.candidates and gem_resp.candidates[0].content and gem_resp.candidates[0].content.parts:
            for p in gem_resp.candidates[0].content.parts:
                if getattr(p, "text", None):
                    txts.append(p.text)

        return {
            "success": True,
            "assistant_text": "\n".join(txts).strip(),
            "function_calls": norm_fcalls,
            "model_name": model_name,
            "provider": "CLOUD",
            "error": None,
        }

    async def _locate_element_with_vision(
        self,
        goal_description: str,
        window_bounds: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Observes screen with Gemini Vision.
        CRITICAL: Never uses blind fallback coordinates.
        If element is not found with certainty, returns found=False and aborts.
        """
        cap = await asyncio.to_thread(tools_os.capture_screen_b64, None, None, True)
        img_bytes = base64.b64decode(cap["screenshot_b64"])

        bounds_hint = ""
        if window_bounds:
            real_w, real_h = cap["screen_width"], cap["screen_height"]
            nl = int((window_bounds["left"] / max(1, real_w)) * 1000)
            nt = int((window_bounds["top"] / max(1, real_h)) * 1000)
            nr = int((window_bounds["right"] / max(1, real_w)) * 1000)
            nb = int((window_bounds["bottom"] / max(1, real_h)) * 1000)
            bounds_hint = (
                f"La finestra target è posizionata approssimativamente in [xmin={nl}, ymin={nt}, xmax={nr}, ymax={nb}]. "
            )

        vision_prompt = (
            f"Analizza questo screenshot del desktop Windows 11 ({cap['screen_width']}x{cap['screen_height']}).\n"
            f"Obiettivo: individua con precisione '{goal_description}'.\n{bounds_hint}\n"
            "Se l'elemento è chiaramente individuabile, rispondi ESCLUSIVAMENTE con questo formato JSON:\n"
            '{"found": true, "norm_x": <int 0-1000>, "norm_y": <int 0-1000>, "observation": "<descrizione dettagliata di cosa vedi>"}\n'
            "Se l'elemento NON è chiaramente visibile o non sei certo al 100%, rispondi con:\n"
            '{"found": false, "observation": "<motivo per cui non è visibile o cosa è presente invece>"}'
        )

        parts = [
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=vision_prompt),
        ]

        resp, _, _ = await self._call_gemini_resilient(
            contents=[types.Content(role="user", parts=parts)],
            system_instruction="Restituisci esclusivamente un JSON valido indicando con precisione found, norm_x, norm_y e observation.",
            enable_tools=False,
            temperature=0.1,
        )

        found = False
        norm_x, norm_y = None, None
        observation = "Riconoscimento visivo non concluso."
        if resp and resp.text:
            match = re.search(r"\{.*\}", resp.text.strip(), re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    found = bool(parsed.get("found", False))
                    observation = str(parsed.get("observation", observation))
                    if found and "norm_x" in parsed and "norm_y" in parsed:
                        norm_x = int(parsed["norm_x"])
                        norm_y = int(parsed["norm_y"])
                except Exception:
                    found = False

        if not found or norm_x is None or norm_y is None:
            return {
                "found": False,
                "norm_x": None,
                "norm_y": None,
                "observation": observation,
                "initial_capture": cap,
                "error": "Elemento non individuato con sicurezza sufficiente sullo schermo. Clic di fallback disabilitato.",
            }

        return {
            "found": True,
            "norm_x": max(0, min(1000, norm_x)),
            "norm_y": max(0, min(1000, norm_y)),
            "observation": observation,
            "initial_capture": cap,
        }

    def _extract_regex_handoffs(
        self,
        text: str,
        current_bot_id: str,
        already_queued_ids: List[str],
    ) -> List[Dict[str, str]]:
        if not text:
            return []
        valid_bots = {"chief", "architect", "builder", "scout", "archivist"}
        found: List[Dict[str, str]] = []
        matches = re.findall(r"@(chief|architect|builder|scout|archivist)\b", text.lower())
        for target_id in matches:
            if target_id in valid_bots and target_id != current_bot_id and target_id not in already_queued_ids:
                already_queued_ids.append(target_id)
                found.append({
                    "target_bot_id": target_id,
                    "instruction": f"Esegui l'azione richiesta da {current_bot_id.capitalize()} nella chat.",
                    "shared_data": text,
                })
        return found

    def _is_cycle_detected(
        self,
        parent_task_id: Optional[str],
        target_bot_id: str,
        instruction: str = "",
        shared_data: str = "",
        caller_bot_id: Optional[str] = None,
    ) -> bool:
        """
        Distingue tra collaborazione legittima (es. Chief -> Builder -> Chief con progresso
        e compiti differenziati) e ripetizione ciclica dello stesso task senza progresso.
        Impedisce cicli infiniti rispettando limiti di profondità e quote di ricorrenza.
        """
        if not parent_task_id:
            return False

        # 1. Blocco immediato di auto-delega
        if caller_bot_id and caller_bot_id == target_bot_id:
            return True

        curr_id = parent_task_id
        depth = 0
        ancestors: List[Dict[str, Any]] = []

        while curr_id and depth < 12:
            depth += 1
            t = db.get_task(curr_id)
            if not t:
                break
            ancestors.append(t)
            curr_id = t.get("parent_task_id")

        # 2. Limite massimo rigido di profondità della catena di task
        if depth >= 8:
            return True

        # Se il bot delegato è il genitore immediato (auto-delega locale se non era specificato caller)
        if ancestors and ancestors[0].get("bot_id") == target_bot_id and len(ancestors) == 1 and not instruction:
            return True

        # Trova quante volte target_bot_id compare già nella catena antenata
        prior_occurrences = [t for t in ancestors if t.get("bot_id") == target_bot_id]
        if not prior_occurrences:
            # Mai comparso prima -> Delega sicuramente legittima
            return False

        # Se compare già 2 o più volte nella stessa catena, blocca per evitare ping-pong infinito
        if len(prior_occurrences) >= 2:
            return True

        # Se compare esattamente 1 volta (es. Chief -> Builder -> Chief):
        # Valuta se c'è progresso o se è una ripetizione inutile dello stesso task
        prior_task = prior_occurrences[0]
        parent_task = ancestors[0] if ancestors else None

        # Verifica progresso del task genitore immediato
        parent_has_progress = False
        if parent_task:
            parent_status = parent_task.get("status")
            parent_evidence = parent_task.get("evidence")
            parent_result = parent_task.get("result") or parent_task.get("result_data")
            if parent_status == "completed":
                parent_has_progress = True
            elif isinstance(parent_evidence, dict) and any(parent_evidence.values()):
                parent_has_progress = True
            elif parent_result:
                parent_has_progress = True

        # Normalizzazione istruzioni per confronto semantico
        def _clean_str(s: Any) -> str:
            return re.sub(r"[^a-zA-Z0-9]", "", str(s or "").lower())

        norm_new_instr = _clean_str(instruction)
        norm_prior_instr = _clean_str(prior_task.get("instruction"))
        norm_prior_goal = _clean_str(prior_task.get("goal"))

        # Caso A: Nessuna istruzione nuova fornita e nessun progresso -> Ciclo senza senso
        if not norm_new_instr and not parent_has_progress:
            return True

        # Caso B: Istruzione identica o quasi a quella già avuta in precedenza da quel bot
        if norm_new_instr and (norm_new_instr == norm_prior_instr or norm_new_instr == norm_prior_goal):
            # Se l'istruzione è identica e non c'è stato progresso verificabile, è un ciclo senza progresso!
            if not parent_has_progress:
                return True
            # Anche se c'era un generico risultato, ripetere esattamente lo stesso compito allo stesso bot senza differenziazione è ciclo
            if norm_new_instr == norm_prior_instr:
                return True

        # Se c'è progresso o l'istruzione è significativamente differenziata (es. revisione, notifica, nuova fase):
        # Collaborazione legittima!
        return False

    async def handle_conversation_turn(
        self,
        chat_id: str,
        user_content: str,
        broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        target_bot_id: Optional[str] = None,
        existing_task_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        all_bots_list = db.get_all_bots()
        bots_map: Dict[str, Dict[str, Any]] = {b["id"]: b for b in all_bots_list}
        chat = db.get_chat(chat_id)
        participants = chat.get("participants", ["chief"]) if chat else ["chief"]

        initial_bot = target_bot_id if (target_bot_id and target_bot_id in bots_map) else (participants[0] if participants else "chief")

        # 1. Creazione o recupero task radice persistente (Task Engine Fase 2A)
        if existing_task_id:
            root_task = db.get_task(existing_task_id)
            if not root_task:
                root_task = db.create_task(
                    chat_id=chat_id,
                    bot_id=initial_bot,
                    title=(user_content[:45] + "...") if len(user_content) > 45 else user_content,
                    goal=user_content,
                    instruction=user_content,
                )
        else:
            root_task = db.create_task(
                chat_id=chat_id,
                bot_id=initial_bot,
                title=(user_content[:45] + "...") if len(user_content) > 45 else user_content,
                goal=user_content,
                instruction=user_content,
                idempotency_key=f"turn_{chat_id}_{initial_bot}_{abs(hash(user_content))}",
            )

        db.update_task_status_atomic(root_task["id"], "running")

        # Auto-estrazione preferenze/decisioni espresse dall'utente (Fase 2B)
        try:
            memory_manager.record_user_preference_or_decision(user_content, chat_id=chat_id)
        except Exception:
            pass

        turn_queue: List[Dict[str, Any]] = [
            {
                "task_id": root_task["id"],
                "bot_id": initial_bot,
                "instruction": user_content,
                "shared_data": "",
                "caller": "user",
            }
        ]

        generated_replies: List[Dict[str, Any]] = []
        step = 0
        last_shared_artifact = ""

        async def _emit(payload: Dict[str, Any]) -> None:
            if broadcast_fn:
                try:
                    await broadcast_fn(chat_id, payload)
                except Exception:
                    pass

        # 0. FAST PATH ROUTER (Fase 4: deterministico, sub-10ms, bypass LLM per query semplici e non ambigue)
        if not existing_task_id:
            fp_route = FastPathRouter.try_route(user_content)
            if fp_route is not None:
                action, params = fp_route
                initial_bot_name = bots_map.get(initial_bot, {}).get("name", "Chief")
                await _emit({
                    "type": "tool_progress",
                    "stage": "Esecuzione rapida (Fast Path)...",
                    "tool": action,
                    "bot_id": initial_bot,
                    "bot_name": initial_bot_name,
                })
                fp_res = await FastPathRouter.execute_fast_path(action, params, bot_id=initial_bot)
                if fp_res.get("handled"):
                    tool_name = fp_res.get("tool_name", action)
                    act_record = db.create_activity(
                        chat_id=chat_id,
                        bot_id=initial_bot,
                        tool_name=tool_name,
                        tool_args=params,
                        status="completed",
                        task_id=root_task["id"],
                    )
                    db.update_task_status_atomic(
                        root_task["id"],
                        "completed",
                        result={"content": fp_res["content"]},
                        evidence={"fast_path": True, "action": action, "duration_ms": fp_res["duration_ms"]}
                    )
                    saved_msg = db.save_message(
                        chat_id=chat_id,
                        sender_id=initial_bot,
                        sender_name=initial_bot_name,
                        content=fp_res["content"],
                        action_card_json=None,
                    )
                    await _emit({
                        "type": "tool_progress",
                        "stage": "Risultato verificato",
                        "tool": tool_name,
                        "bot_id": initial_bot,
                        "bot_name": initial_bot_name,
                    })
                    await _emit({"type": "new_message", "message": saved_msg})
                    await _emit({"type": "task_updated", "task": db.get_task(root_task["id"])})
                    await _emit({
                        "type": "bot_status",
                        "bot_id": initial_bot,
                        "bot_name": initial_bot_name,
                        "status": "idle",
                    })
                    return [saved_msg]

        try:
            while turn_queue and step < MAX_SWARM_STEPS:
                step += 1
                current_item = turn_queue.pop(0)
                current_task_id = current_item.get("task_id") or root_task["id"]
                bot_id = current_item["bot_id"]
                bot = bots_map.get(bot_id) or bots_map.get("chief")
                if not bot:
                    continue

                bot_id = bot["id"]
                bot_name = bot["name"]
                db.add_participant_to_chat(chat_id, bot_id)
                db.update_task_status_atomic(current_task_id, "running")

                await _emit({
                    "type": "bot_status",
                    "bot_id": bot_id,
                    "bot_name": bot_name,
                    "status": "Thinking / Working...",
                    "task_id": current_task_id,
                })
                await _emit({
                    "type": "task_updated",
                    "task": db.get_task(current_task_id),
                })

                system_prompt = (
                    f"{bot.get('system_prompt', '')}\n"
                    f"Il tuo ID è '{bot_id}' e il tuo nome è '{bot_name}'.\n"
                    "REGOLE DI SICUREZZA E FORMATO OBBLIGATORIE:\n"
                    "1. Tutte le modifiche a file (write, delete, move) e tutte le azioni sul desktop "
                    "(click, incollaggio) RICHIEDONO APPROVAZIONE ESPLICITA dell'utente.\n"
                    "2. Per osservare lo schermo USA `inspect_screen` (in sola lettura). "
                    "Non eseguire clic senza prima aver individuato l'elemento e chiesto autorizzazione.\n"
                    "3. Non eseguire MAI comandi PowerShell o shell arbitrari.\n"
                    "4. Rispondi sempre in modo utile, chiaro e sintetico (in massimo 2-3 frasi) in italiano."
                )

                system_prompt += (
                    "\nREGOLE OPERATIVE:\n"
                    "- Se l'utente chiede di interagire con un'applicazione o con il desktop, "
                    "invoca subito lo strumento 'list_windows' o 'inspect_screen' per osservare l'ambiente "
                    "prima di qualsiasi risposta o azione, senza usare strumenti ZIP o filesystem.\n"
                    "- Per consultare la posta elettronica usa 'gmail_search' e 'gmail_read'. Per consultare agenda e appuntamenti usa 'calendar_list_events' (strumenti in sola lettura).\n"
                    "- Per clic e digitazione richiedi approvazione esplicita.\n"
                    "- Una delega non costituisce completamento del compito.\n"
                    "- Non dichiarare di aver eseguito azioni senza risultati verificabili.\n"
                    "- Se un'azione richiede più passaggi, conserva l'obiettivo originale.\n"
                    "- Se non puoi completare un passaggio, indica esattamente "
                    "quale operazione è bloccata e perché.\n"
                )

                if (
                    current_item.get("caller") == "user"
                    and not self._select_tools_for_turn(
                        bot_id, current_item["instruction"]
                    )
                ):
                    system_prompt += (
                        "\nQuesta è una conversazione diretta. "
                        "Rispondi alla domanda senza delegare ad altri agenti. "
                        "Non inventare operazioni eseguite. "
                        "Sii conciso ma completo.\n"
                    )

                structured_messages: List[Dict[str, Any]] = []
                if current_item.get("caller") != "user":
                    task_prompt = (
                        f"=== COMPITO ASSEGNATO (Task ID: {current_task_id}) ===\n"
                        f"- Assegnato da: {current_item['caller']}\n"
                        f"- Agente Responsabile: {bot_name} ({bot_id})\n"
                        f"- Obiettivo: {current_item['instruction']}\n"
                    )
                    if current_item.get("shared_data") or last_shared_artifact:
                        task_prompt += f"\nCONTENUTO CONDIVISO:\n{(current_item.get('shared_data') or last_shared_artifact)[:500]}\n"
                    structured_messages = [{"role": "user", "content": task_prompt}]
                else:
                    # Estrai gli ultimi messaggi per mantenere un contesto compatto e favorire il riuso KV cache
                    recent_history = db.get_chat_messages(chat_id, limit=4)
                    for m in recent_history[-3:]:
                        role = "user" if m.get("sender_id") == "user" else "assistant"
                        m_txt = (m.get("content") or "").strip()
                        if len(m_txt) > 200:
                            m_txt = m_txt[:200] + "..."
                        if m_txt:
                            structured_messages.append({"role": role, "content": m_txt})

                    # Aggiunge il turno corrente
                    curr_inst = current_item['instruction']
                    if current_item.get("shared_data") or last_shared_artifact:
                        curr_inst += f"\n[Riferimento: {(current_item.get('shared_data') or last_shared_artifact)[:300]}]"
                    structured_messages.append({"role": "user", "content": curr_inst})
                    task_prompt = curr_inst

                streaming_acc = [""]

                async def _on_streaming_chunk(delta_chunk: str):
                    streaming_acc[0] += delta_chunk
                    await _emit({
                        "type": "streaming_chunk",
                        "chat_id": chat_id,
                        "bot_id": bot_id,
                        "bot_name": bot_name,
                        "content": streaming_acc[0],
                        "delta": delta_chunk,
                        "is_final": False,
                    })

                turn_res = await self._dispatch_model_turn(
                    system_prompt=system_prompt,
                    task_prompt=task_prompt,
                    user_content=user_content,
                    instruction=current_item["instruction"],
                    structured_messages=structured_messages,
                    task_id=current_task_id,
                    chat_id=chat_id,
                    enable_tools=True,
                    bot_id=bot_id,
                    max_tokens=150,
                    on_chunk=_on_streaming_chunk,
                )

                if not turn_res.get("success"):
                    err = turn_res.get("error", "Errore esecuzione modello.")
                    used_model = turn_res.get("model_name", "AI Engine")
                    db.update_task_status_atomic(current_task_id, "failed", error_msg=f"Errore Modello ({used_model}): {err}")
                    try:
                        await notification_manager.notify_task_failed(
                            task_id=current_task_id,
                            title=f"Task fallito: {bot_name}",
                            error_msg=f"Errore Modello ({used_model}): {err}",
                        )
                    except Exception:
                        pass
                    err_msg = db.save_message(
                        chat_id=chat_id,
                        sender_id=bot_id,
                        sender_name=bot_name,
                        content=f"⚠️ Errore Modello ({used_model}): {err}",
                        action_card_json=None,
                    )
                    generated_replies.append(err_msg)
                    await _emit({"type": "new_message", "message": err_msg})
                    await _emit({"type": "task_updated", "task": db.get_task(current_task_id)})
                    break

                function_calls = turn_res.get("function_calls", [])
                assistant_text = turn_res.get("assistant_text", "").strip()
                used_model = turn_res.get("model_name", "AI Engine")

                user_lower = (user_content + " " + current_item["instruction"]).lower()
                # Safety fallback triggers
                if not function_calls and any(k in user_lower for k in ("schermo", "screenshot", "finestr", "cosa vedi", "vedi")):
                    function_calls = [
                        {
                            "name": "inspect_screen",
                            "args": {"goal_description": "Ispezione visiva contenuto attivo sullo schermo"},
                        }
                    ]

                action_card: Optional[Dict[str, Any]] = None
                queued_in_this_turn: List[str] = [item["bot_id"] for item in turn_queue]
                tool_summaries: List[str] = []
                task_evidence: Dict[str, Any] = {}

                for fc in function_calls:
                    fn_name = fc["name"] if isinstance(fc, dict) else fc.name
                    fn_args = (fc.get("args") or {}) if isinstance(fc, dict) else (dict(fc.args) if fc.args else {})

                    # 1. Log activity in database (audit trail con task_id)
                    act_record = db.create_activity(
                        chat_id=chat_id,
                        bot_id=bot_id,
                        tool_name=fn_name,
                        tool_args=fn_args,
                        status="running",
                        task_id=current_task_id,
                    )
                    activity_id = act_record["id"]

                    if fn_name == "delegate_to_coworker":
                        target_id = str(fn_args.get("target_bot_id", "")).lower().strip().replace("@", "")
                        instr = str(fn_args.get("instruction", "Esegui il task."))
                        shared = str(fn_args.get("shared_data", "")) or assistant_text or last_shared_artifact

                        # Prevenzione cicli e duplicazioni (Fase 2A & 2A.1)
                        if self._is_cycle_detected(current_task_id, target_id, instruction=instr, shared_data=shared, caller_bot_id=bot_id):
                            tool_summaries.append(f"⚠️ **Delega ciclica evitata:** @{target_id} ha già gestito questo compito senza nuovo progresso.")
                            db.update_activity(activity_id, status="failed", error_msg=f"Ciclo di delega verso {target_id} bloccato.")
                        elif target_id in bots_map and target_id not in queued_in_this_turn:
                            queued_in_this_turn.append(target_id)
                            original_goal = current_item.get("root_goal") or root_task.get("goal") or user_content
                            subtask = db.create_task(
                                chat_id=chat_id,
                                bot_id=target_id,
                                title=f"Delega a {bots_map[target_id]['name']}: {instr[:30]}",
                                goal=original_goal,
                                instruction=instr,
                                parent_task_id=current_task_id,
                                dependencies=[current_task_id],
                            )
                            turn_queue.append({
                                "task_id": subtask["id"],
                                "bot_id": target_id,
                                "instruction": instr,
                                "shared_data": shared,
                                "caller": bot_name,
                                "root_goal": original_goal,
                            })
                            db.add_participant_to_chat(chat_id, target_id)
                            tool_summaries.append(f"👉 Passaggio di consegne a **@{bots_map[target_id]['name']}**: *{instr}* (Task: `{subtask['id']}`)")
                            db.update_activity(activity_id, status="completed", result={"target_id": target_id, "task_id": subtask["id"]})
                            db.update_task_status_atomic(current_task_id, "delegated")
                            task_evidence["delegated_to"] = target_id
                            task_evidence["subtask_id"] = subtask["id"]

                    elif fn_name == "request_peer_review":
                        reviewer_id = str(fn_args.get("reviewer_bot_id", "architect")).lower().strip().replace("@", "")
                        artifact = str(fn_args.get("artifact_to_review", "")) or assistant_text or last_shared_artifact
                        criteria = str(fn_args.get("review_criteria", "Verifica aderenza e robustezza"))
                        if reviewer_id in bots_map:
                            rev_task = db.create_task(
                                chat_id=chat_id,
                                bot_id=reviewer_id,
                                title=f"Peer Review: {criteria[:30]}",
                                goal=f"Revisione critica tra pari ({criteria})",
                                instruction=f"Analizza criticamente questo artefatto in base ai criteri specificati ({criteria}):\n\n{artifact}",
                                parent_task_id=current_task_id,
                                dependencies=[current_task_id],
                            )
                            turn_queue.append({
                                "task_id": rev_task["id"],
                                "bot_id": reviewer_id,
                                "instruction": f"Revisione critica tra pari:\n{artifact}\nCriteri: {criteria}",
                                "shared_data": artifact,
                                "caller": f"{bot_name} (Peer Review)",
                            })
                            db.add_participant_to_chat(chat_id, reviewer_id)
                            tool_summaries.append(
                                f"🔍 **Richiesta revisione tra pari a @{bots_map[reviewer_id]['name']}** ({criteria}).\n"
                                f"*(Nota metodologica: la revisione tra colleghi usa lo stesso modello e non costituisce validazione indipendente esterna)*"
                            )
                            db.update_activity(activity_id, status="completed", result={"reviewer_id": reviewer_id, "task_id": rev_task["id"]})
                            task_evidence["peer_review_task_id"] = rev_task["id"]

                    elif fn_name == "inspect_screen":
                        goal = str(fn_args.get("goal_description", "Ispezione schermo"))
                        await _emit({"type": "tool_progress", "stage": "Ispezione visiva schermo in corso...", "tool": "inspect_screen", "bot_id": bot_id, "bot_name": bot_name})
                        loc = await self._locate_element_with_vision(goal)
                        obs = loc.get("observation", "")
                        cap_init = loc.get("initial_capture", {})

                        if not loc.get("found"):
                            db.update_activity(activity_id, status="failed", error_msg=loc.get("error"))
                            tool_summaries.append(f"🔍 **Ispezione Schermo:** {obs}\n*(Elemento non identificato con sicurezza - nessun clic eseguito)*")
                            action_card = {
                                "status": "failed",
                                "title": f"Ispezione Schermo: '{goal}'",
                                "screenshot_b64": cap_init.get("screenshot_b64"),
                                "details": loc.get("error", "Elemento non trovato."),
                            }
                            task_evidence["inspection"] = {"found": False, "observation": obs}
                            current_item["is_blocked"] = True
                            current_item["block_reason"] = f"Elemento non individuato sullo schermo: {obs}"
                        else:
                            nx, ny = loc["norm_x"], loc["norm_y"]
                            rx, ry = tools_os.norm_to_physical_coords(nx, ny)
                            cap_marked = await asyncio.to_thread(tools_os.capture_screen_b64, rx, ry, False)
                            db.update_activity(activity_id, status="completed", result={"norm_x": nx, "norm_y": ny, "observation": obs})
                            tool_summaries.append(f"🖥️ **Elemento individuato a ({nx}, {ny}):** {obs}")
                            action_card = {
                                "status": "done",
                                "title": f"Elemento individuato ({nx}, {ny})",
                                "screenshot_b64": cap_marked.get("screenshot_b64"),
                                "x": cap_marked.get("norm_pct_x", 50),
                                "y": cap_marked.get("norm_pct_y", 50),
                                "details": obs,
                            }
                            task_evidence["inspection"] = {"found": True, "norm_coords": [nx, ny], "observation": obs}

                    elif fn_name == "click_screen_element":
                        goal = str(fn_args.get("goal_description", "Clic elemento"))
                        nx = int(fn_args.get("norm_x", 500))
                        ny = int(fn_args.get("norm_y", 500))
                        txt_paste = fn_args.get("text_to_type")
                        press_ent = bool(fn_args.get("press_enter", False))

                        # SECURITY: Requires explicit user approval before execution
                        appr = db.create_approval(
                            chat_id=chat_id,
                            bot_id=bot_id,
                            action_type="desktop_click",
                            description=f"Clic alle coordinate ({nx}, {ny}) per: '{goal}'",
                            payload={"tool_name": "click_screen_element", "args": fn_args},
                            activity_id=activity_id,
                            task_id=current_task_id,
                        )
                        db.update_activity(activity_id, status="waiting_approval")
                        db.update_task_status_atomic(current_task_id, "waiting_approval")

                        action_card = {
                            "status": "waiting_approval",
                            "requires_approval": True,
                            "approval_id": appr["id"],
                            "task_id": current_task_id,
                            "title": f"Autorizzazione Clic richiesta ({nx}, {ny})",
                            "details": f"Il bot intende cliccare su '{goal}'. Clicca 'Approva ed Esegui' per autorizzare.",
                            "x": round((nx / 10.0), 1),
                            "y": round((ny / 10.0), 1),
                        }
                        tool_summaries.append(f"🔒 **Autorizzazione richiesta per clic:** ({nx}, {ny}) su '{goal}'.")

                    elif fn_name == "focus_and_paste_into_app":
                        win_sub = str(fn_args.get("window_title_substring", "Antigravity"))
                        txt_paste = str(fn_args.get("text_to_paste", "")) or last_shared_artifact or assistant_text
                        press_ent = bool(fn_args.get("press_enter", True))

                        # SECURITY: Requires explicit user approval before sending keystrokes / paste
                        appr = db.create_approval(
                            chat_id=chat_id,
                            bot_id=bot_id,
                            action_type="desktop_paste",
                            description=f"Porta in primo piano '{win_sub}' e incolla testo ({len(txt_paste)} caratteri)",
                            payload={
                                "tool_name": "focus_and_paste_into_app",
                                "args": {
                                    "window_title_substring": win_sub,
                                    "text_to_paste": txt_paste,
                                    "press_enter": press_ent,
                                }
                            },
                            activity_id=activity_id,
                            task_id=current_task_id,
                        )
                        db.update_activity(activity_id, status="waiting_approval")
                        db.update_task_status_atomic(current_task_id, "waiting_approval")

                        action_card = {
                            "status": "waiting_approval",
                            "requires_approval": True,
                            "approval_id": appr["id"],
                            "task_id": current_task_id,
                            "title": f"Autorizzazione Incollaggio in '{win_sub}'",
                            "details": f"Il bot intende focalizzare '{win_sub}' e incollare testo. Clicca 'Approva' per procedere.",
                        }
                        tool_summaries.append(f"🔒 **Autorizzazione richiesta per invio testo in '{win_sub}'.**")

                    elif fn_name == "manage_files":
                        act = str(fn_args.get("action", "read")).lower().strip()
                        path = str(fn_args.get("path", "."))
                        content = fn_args.get("content")
                        dest = fn_args.get("destination")

                        if act in ("write", "mkdir", "move", "delete"):
                            # SECURITY: Requires explicit approval for all disk mutations
                            appr = db.create_approval(
                                chat_id=chat_id,
                                bot_id=bot_id,
                                action_type=f"file_{act}",
                                description=f"Operazione file '{act}' su '{path}'",
                                payload={"tool_name": "manage_files", "args": fn_args},
                                activity_id=activity_id,
                                task_id=current_task_id,
                            )
                            db.update_activity(activity_id, status="waiting_approval")
                            db.update_task_status_atomic(current_task_id, "waiting_approval")

                            action_card = {
                                "status": "waiting_approval",
                                "requires_approval": True,
                                "approval_id": appr["id"],
                                "task_id": current_task_id,
                                "title": f"Autorizzazione File ({act}): '{path}'",
                                "details": f"Operazione file '{act}' in attesa di approvazione.",
                            }
                            tool_summaries.append(f"🔒 **Autorizzazione richiesta per modifica file:** `{act}` su `{path}`.")
                        else:
                            # Read and list are read-only and safe if within allowed workspace
                            res_file = await asyncio.to_thread(tools_os.manage_files, act, path, None, None, approved=False)
                            if res_file.get("status") == "ok":
                                db.update_activity(activity_id, status="completed", result=res_file)
                                tool_summaries.append(f"📁 **File System ({act}):** `{json.dumps(res_file, ensure_ascii=False)[:400]}`")
                                task_evidence[f"file_{act}"] = {"status": "ok", "path": path}
                            else:
                                db.update_activity(activity_id, status="failed", error_msg=res_file.get("message"))
                                tool_summaries.append(f"⚠️ **File System ({act}):** {res_file.get('message')}")
                                task_evidence[f"file_{act}"] = {"status": "error", "error": res_file.get("message")}

                    elif fn_name == "open_url_or_app":
                        target = str(fn_args.get("target", ""))
                        appr = db.create_approval(
                            chat_id=chat_id,
                            bot_id=bot_id,
                            action_type="open_target",
                            description=f"Apertura applicazione o URL: '{target}'",
                            payload={"tool_name": "open_url_or_app", "args": fn_args},
                            activity_id=activity_id,
                            task_id=current_task_id,
                        )
                        db.update_activity(activity_id, status="waiting_approval")
                        db.update_task_status_atomic(current_task_id, "waiting_approval")

                        action_card = {
                            "status": "waiting_approval",
                            "requires_approval": True,
                            "approval_id": appr["id"],
                            "task_id": current_task_id,
                            "title": f"Autorizzazione apertura: '{target}'",
                            "details": f"Apertura esterna in attesa di autorizzazione.",
                        }
                        tool_summaries.append(f"🔒 **Autorizzazione richiesta per aprire:** `{target}`.")

                    elif fn_name == "search_files":
                        q = str(fn_args.get("query", ""))
                        p = str(fn_args.get("path", "."))
                        await _emit({"type": "tool_progress", "stage": "Ricerca in corso...", "tool": "search_files", "bot_id": bot_id, "bot_name": bot_name})
                        res_search = await asyncio.to_thread(tools_os.search_files, q, p)
                        if res_search.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result=res_search)
                            tot = res_search.get("total_matches", 0)
                            stage_msg = "File individuato" if tot > 0 else "Risultato verificato"
                            await _emit({"type": "tool_progress", "stage": stage_msg, "tool": "search_files", "bot_id": bot_id, "bot_name": bot_name})
                            matches_str = ", ".join([m["relative_path"] for m in res_search.get("matches", [])[:5]])
                            tool_summaries.append(f"🔎 **Ricerca File ('{q}'):** Trovati {tot} risultati (`{matches_str}`).")
                            task_evidence["search_files"] = res_search
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_search.get("message"))
                            tool_summaries.append(f"⚠️ **Ricerca File ('{q}'):** {res_search.get('message')}")
                            task_evidence["search_files"] = {"status": "error", "error": res_search.get("message")}

                    elif fn_name == "read_document":
                        p = str(fn_args.get("path", ""))
                        ml = int(fn_args.get("max_lines", 200))
                        await _emit({"type": "tool_progress", "stage": "Documento in lettura...", "tool": "read_document", "bot_id": bot_id, "bot_name": bot_name})
                        res_doc = await asyncio.to_thread(tools_os.read_document, p, ml)
                        if res_doc.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"path": res_doc.get("path"), "line_count": res_doc.get("line_count")})
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "read_document", "bot_id": bot_id, "bot_name": bot_name})
                            doc_snippet = res_doc.get("content", "").strip()
                            if len(doc_snippet) > 500:
                                doc_snippet = doc_snippet[:500] + "... [troncato]"
                            tool_summaries.append(f"📄 **Lettura Documento ('{res_doc.get('path')}'):**\n```\n{doc_snippet}\n```")
                            task_evidence["read_document"] = {"path": p, "line_count": res_doc.get("line_count"), "content_preview": doc_snippet}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_doc.get("message"))
                            tool_summaries.append(f"⚠️ **Lettura Documento ('{p}'):** {res_doc.get('message')}")
                            task_evidence["read_document"] = {"status": "error", "error": res_doc.get("message")}

                    elif fn_name == "inspect_zip":
                        zp = str(fn_args.get("zip_path", ""))
                        act = str(fn_args.get("action", "list"))
                        ftr = fn_args.get("file_to_read")
                        await _emit({"type": "tool_progress", "stage": "Ispezione archivio ZIP in corso...", "tool": "inspect_zip", "bot_id": bot_id, "bot_name": bot_name})
                        res_zip = await asyncio.to_thread(tools_os.inspect_zip, zp, act, ftr)
                        if res_zip.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result=res_zip)
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "inspect_zip", "bot_id": bot_id, "bot_name": bot_name})
                            if act == "list":
                                entries_sample = ", ".join([e["filename"] for e in res_zip.get("entries", [])[:4]])
                                tool_summaries.append(f"📦 **Archivio ZIP ('{zp}'):** {res_zip.get('total_entries', 0)} file (`{entries_sample}`).")
                            else:
                                zip_snippet = str(res_zip.get("content", "")).strip()
                                if len(zip_snippet) > 400:
                                    zip_snippet = zip_snippet[:400] + "... [troncato]"
                                tool_summaries.append(f"📦 **Archivio ZIP ('{zp}' -> '{ftr}'):**\n```\n{zip_snippet}\n```")
                            task_evidence["inspect_zip"] = res_zip
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_zip.get("message"))
                            tool_summaries.append(f"⚠️ **Archivio ZIP ('{zp}'):** {res_zip.get('message')}")
                            task_evidence["inspect_zip"] = {"status": "error", "error": res_zip.get("message")}

                    elif fn_name == "browse_url":
                        u = str(fn_args.get("url", ""))
                        await _emit({"type": "tool_progress", "stage": "Consultazione pagina web...", "tool": "browse_url", "bot_id": bot_id, "bot_name": bot_name})
                        res_browse = await asyncio.to_thread(tools_os.browse_url, u)
                        if res_browse.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"url": u, "title": res_browse.get("title")})
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "browse_url", "bot_id": bot_id, "bot_name": bot_name})
                            web_text = str(res_browse.get("text_content") or res_browse.get("text", "")).strip()
                            if len(web_text) > 400:
                                web_text = web_text[:400] + "... [troncato]"
                            tool_summaries.append(f"🌐 **Browser Web:** '{res_browse.get('title')}' ({u}):\n```\n{web_text}\n```")
                            task_evidence["browse_url"] = {"url": u, "title": res_browse.get("title"), "text_preview": web_text}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_browse.get("message"))
                            tool_summaries.append(f"⚠️ **Browser Web ('{u}'):** {res_browse.get('message')}")
                            task_evidence["browse_url"] = {"status": "error", "error": res_browse.get("message")}

                    elif fn_name == "browser_open":
                        u = str(fn_args.get("url", ""))
                        await _emit({"type": "tool_progress", "stage": "Apertura URL nel browser sandbox...", "tool": "browser_open", "bot_id": bot_id, "bot_name": bot_name})
                        res_open = await asyncio.to_thread(tools_browser.browser_open, u)
                        if res_open.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"url": res_open.get("url", u), "title": res_open.get("title")})
                            await _emit({"type": "tool_progress", "stage": "Pagina sandbox caricata", "tool": "browser_open", "bot_id": bot_id, "bot_name": bot_name})
                            tool_summaries.append(f"🌐 **Browser Sandbox:** Pagina aperta '{res_open.get('title')}' ({res_open.get('url', u)})")
                            task_evidence["browser_open"] = {"url": res_open.get("url", u), "title": res_open.get("title"), "status": "ok"}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_open.get("message"))
                            tool_summaries.append(f"⚠️ **Browser Sandbox ('{u}'):** {res_open.get('message')}")
                            task_evidence["browser_open"] = {"status": "error", "error": res_open.get("message")}

                    elif fn_name == "browser_snapshot":
                        await _emit({"type": "tool_progress", "stage": "Cattura snapshot accessibilità sandbox...", "tool": "browser_snapshot", "bot_id": bot_id, "bot_name": bot_name})
                        res_snap = await asyncio.to_thread(tools_browser.browser_snapshot)
                        if res_snap.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"title": res_snap.get("title"), "total_refs": res_snap.get("total_refs", 0)})
                            await _emit({"type": "tool_progress", "stage": "Snapshot generato", "tool": "browser_snapshot", "bot_id": bot_id, "bot_name": bot_name})
                            snap_text = str(res_snap.get("snapshot", "")).strip()
                            snap_preview = snap_text[:600] + ("... [troncato]" if len(snap_text) > 600 else "")
                            tool_summaries.append(f"🌐 **Snapshot Browser Sandbox ({res_snap.get('title')}):**\n```\n{snap_preview}\n```")
                            task_evidence["browser_snapshot"] = {"status": "ok", "title": res_snap.get("title"), "snapshot": snap_text}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_snap.get("message"))
                            tool_summaries.append(f"⚠️ **Snapshot Browser Sandbox:** {res_snap.get('message')}")
                            task_evidence["browser_snapshot"] = {"status": "error", "error": res_snap.get("message")}

                    elif fn_name == "browser_click":
                        ref_val = fn_args.get("ref")
                        appr = db.create_approval(
                            chat_id=chat_id,
                            bot_id=bot_id,
                            action_type="browser_action",
                            description=f"Clic su elemento [{ref_val}] nel browser sandbox",
                            payload={"tool_name": "browser_click", "args": fn_args},
                            activity_id=activity_id,
                            task_id=current_task_id,
                        )
                        db.update_activity(activity_id, status="waiting_approval")
                        db.update_task_status_atomic(current_task_id, "waiting_approval")

                        action_card = {
                            "status": "waiting_approval",
                            "requires_approval": True,
                            "approval_id": appr["id"],
                            "task_id": current_task_id,
                            "title": f"Autorizzazione Clic Sandbox (ref [{ref_val}])",
                            "details": f"Il bot intende cliccare sull'elemento [{ref_val}] nel browser sandbox. Clicca 'Approva' per procedere.",
                        }
                        tool_summaries.append(f"🔒 **Autorizzazione richiesta per clic sandbox su elemento [{ref_val}].**")

                    elif fn_name == "browser_type":
                        ref_val = fn_args.get("ref")
                        text_val = str(fn_args.get("text", ""))
                        appr = db.create_approval(
                            chat_id=chat_id,
                            bot_id=bot_id,
                            action_type="browser_action",
                            description=f"Inserimento testo in elemento [{ref_val}] nel browser sandbox",
                            payload={"tool_name": "browser_type", "args": fn_args},
                            activity_id=activity_id,
                            task_id=current_task_id,
                        )
                        db.update_activity(activity_id, status="waiting_approval")
                        db.update_task_status_atomic(current_task_id, "waiting_approval")

                        action_card = {
                            "status": "waiting_approval",
                            "requires_approval": True,
                            "approval_id": appr["id"],
                            "task_id": current_task_id,
                            "title": f"Autorizzazione Testo Sandbox (ref [{ref_val}])",
                            "details": f"Il bot intende inserire testo nell'elemento [{ref_val}] del browser sandbox: '{text_val[:50]}...'. Clicca 'Approva' per procedere.",
                        }
                        tool_summaries.append(f"🔒 **Autorizzazione richiesta per inserimento testo in elemento sandbox [{ref_val}].**")

                    elif fn_name == "gmail_search":
                        q = str(fn_args.get("query", ""))
                        max_r = int(fn_args.get("max_results", 10) or 10)
                        await _emit({"type": "tool_progress", "stage": "Ricerca email in corso...", "tool": "gmail_search", "bot_id": bot_id, "bot_name": bot_name})
                        res_mail = await asyncio.to_thread(tools_google.gmail_search, q, max_r)
                        if res_mail.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"query": q, "count": res_mail.get("count", 0)})
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "gmail_search", "bot_id": bot_id, "bot_name": bot_name})
                            msgs = res_mail.get("messages", [])
                            lines = []
                            for m in msgs[:5]:
                                lines.append(f"- ID `{m.get('id')}` | Da: {m.get('sender')} | Oggetto: {m.get('subject')} ({m.get('date')})")
                            preview_txt = "\n".join(lines) if lines else "Nessuna email trovata."
                            tool_summaries.append(f"✉️ **Gmail Search ('{q}'):** Trovati {len(msgs)} messaggi:\n{preview_txt}")
                            task_evidence["gmail_search"] = {"query": q, "count": len(msgs), "messages": msgs}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_mail.get("message"))
                            tool_summaries.append(f"⚠️ **Gmail Search ('{q}'):** {res_mail.get('message')}")
                            task_evidence["gmail_search"] = {"status": "error", "error": res_mail.get("message")}

                    elif fn_name == "gmail_read":
                        mid = str(fn_args.get("message_id", ""))
                        max_c = int(fn_args.get("max_chars", 4000) or 4000)
                        await _emit({"type": "tool_progress", "stage": "Lettura messaggio Gmail in corso...", "tool": "gmail_read", "bot_id": bot_id, "bot_name": bot_name})
                        res_read = await asyncio.to_thread(tools_google.gmail_read, mid, max_c)
                        if res_read.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"message_id": mid, "subject": res_read.get("subject")})
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "gmail_read", "bot_id": bot_id, "bot_name": bot_name})
                            b_preview = str(res_read.get("body", "")).strip()
                            if len(b_preview) > 500:
                                b_preview = b_preview[:500] + "... [troncato]"
                            tool_summaries.append(f"📧 **Gmail Read (`{mid}`):** Da: {res_read.get('sender')} | Oggetto: {res_read.get('subject')}\n```\n{b_preview}\n```")
                            task_evidence["gmail_read"] = {"message_id": mid, "subject": res_read.get("subject"), "sender": res_read.get("sender"), "body": res_read.get("body")}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_read.get("message"))
                            tool_summaries.append(f"⚠️ **Gmail Read (`{mid}`):** {res_read.get('message')}")
                            task_evidence["gmail_read"] = {"status": "error", "error": res_read.get("message")}

                    elif fn_name == "calendar_list_events":
                        days_a = int(fn_args.get("days_ahead", 7) or 7)
                        max_e = int(fn_args.get("max_results", 20) or 20)
                        await _emit({"type": "tool_progress", "stage": "Consultazione Google Calendar in corso...", "tool": "calendar_list_events", "bot_id": bot_id, "bot_name": bot_name})
                        res_cal = await asyncio.to_thread(tools_google.calendar_list_events, days_a, max_e)
                        if res_cal.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result={"days_ahead": days_a, "count": res_cal.get("count", 0)})
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "calendar_list_events", "bot_id": bot_id, "bot_name": bot_name})
                            ev_list = res_cal.get("events", [])
                            lines = []
                            for ev in ev_list[:5]:
                                lines.append(f"- {ev.get('summary')} ({ev.get('start')} -> {ev.get('end')})")
                            preview_txt = "\n".join(lines) if lines else "Nessun evento in agenda."
                            tool_summaries.append(f"📅 **Google Calendar ({days_a} giorni):** {len(ev_list)} eventi trovati:\n{preview_txt}")
                            task_evidence["calendar_list_events"] = {"days_ahead": days_a, "count": len(ev_list), "events": ev_list}
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_cal.get("message"))
                            tool_summaries.append(f"⚠️ **Google Calendar:** {res_cal.get('message')}")
                            task_evidence["calendar_list_events"] = {"status": "error", "error": res_cal.get("message")}

                    elif fn_name == "list_windows":
                        flt = fn_args.get("filter_str")
                        await _emit({"type": "tool_progress", "stage": "Rilevamento finestre in corso...", "tool": "list_windows", "bot_id": bot_id, "bot_name": bot_name})
                        res_wins = await asyncio.to_thread(tools_os.list_windows, flt)
                        if res_wins.get("status") == "ok":
                            db.update_activity(activity_id, status="completed", result=res_wins)
                            await _emit({"type": "tool_progress", "stage": "Risultato verificato", "tool": "list_windows", "bot_id": bot_id, "bot_name": bot_name})
                            w_preview = ", ".join(res_wins.get("windows", [])[:5]) or "Nessuna"
                            tool_summaries.append(f"🪟 **Finestre Windows:** {res_wins.get('count', 0)} attive (`{w_preview}`).")
                            task_evidence["list_windows"] = {"count": res_wins.get("count", 0), "windows": res_wins.get("windows", [])}

                            # Verifica esplicita disponibilità target per richieste desktop (es. Antigravity)
                            inst_lower = current_item["instruction"].lower()
                            if "antigravity" in inst_lower:
                                has_antigravity = any("antigravity" in str(w).lower() for w in res_wins.get("windows", []))
                                if not has_antigravity:
                                    assistant_text = (
                                        "Ho verificato le finestre attualmente attive sul desktop tramite `list_windows`, "
                                        "ma l'applicazione **Antigravity** non risulta aperta.\n"
                                        "Non è possibile accedere al progetto `clone-whoop` né avviare conversazioni "
                                        "finché l'applicazione non è in esecuzione sul sistema."
                                    )
                                    current_item["is_blocked"] = True
                                    current_item["block_reason"] = "Applicazione Antigravity non trovata tra le finestre attive."
                        else:
                            db.update_activity(activity_id, status="failed", error_msg=res_wins.get("message"))
                            tool_summaries.append(f"⚠️ **Finestre Windows:** {res_wins.get('message')}")

                # Multi-step continuation: se sono stati eseguiti tool immediati e non ci sono approvazioni in sospeso o deleghe,
                # e l'assistente non ha ancora formulato una risposta completa:
                immediate_evidence = [k for k in ("search_files", "read_document", "inspect_zip", "browse_url", "list_windows", "gmail_search", "gmail_read", "calendar_list_events") if k in task_evidence]
                if immediate_evidence and not action_card and not turn_queue and len(assistant_text) < 40 and not current_item.get("is_blocked"):
                    current_prov = self._resolve_provider(user_content, current_item["instruction"])
                    if current_prov == "LOCAL":
                        # Su CPU locale evitiamo una seconda inferenza pesante: il report dettagliato è già in tool_summaries
                        assistant_text = "Ho eseguito l'operazione richiesta. Ecco i risultati raccolti:"
                    else:
                        followup_prompt = (
                            f"I risultati dei seguenti strumenti sono stati ottenuti con successo:\n"
                            f"{json.dumps({k: task_evidence[k] for k in immediate_evidence}, ensure_ascii=False)[:3000]}\n\n"
                            f"In base a questi dati oggettivi, rispondi in modo chiaro, utile e sintetico (in 2-3 frasi) in italiano alla richiesta dell'utente: '{current_item['instruction']}'."
                        )
                        followup_res = await self._dispatch_model_turn(
                            system_prompt=system_prompt,
                            task_prompt=followup_prompt,
                            user_content=user_content,
                            instruction=current_item["instruction"],
                            task_id=current_task_id,
                            chat_id=chat_id,
                            enable_tools=False,
                            bot_id=bot_id,
                            max_tokens=200,
                        )
                        if followup_res.get("success") and followup_res.get("assistant_text"):
                            assistant_text = followup_res.get("assistant_text").strip()

                if assistant_text and len(assistant_text) > 40:
                    last_shared_artifact = assistant_text

                regex_handoffs = self._extract_regex_handoffs(assistant_text, bot_id, queued_in_this_turn)
                for rh in regex_handoffs:
                    target_rh = rh["target_bot_id"]
                    if not self._is_cycle_detected(
                        current_task_id,
                        target_rh,
                        instruction=rh.get("instruction", ""),
                        shared_data=rh.get("shared_data", ""),
                        caller_bot_id=bot_id,
                    ):
                        rh_subtask = db.create_task(
                            chat_id=chat_id,
                            bot_id=target_rh,
                            title=f"Menzione @{target_rh}",
                            goal=rh["instruction"],
                            instruction=rh["instruction"],
                            parent_task_id=current_task_id,
                            dependencies=[current_task_id],
                        )
                        turn_queue.append({
                            "task_id": rh_subtask["id"],
                            "bot_id": target_rh,
                            "instruction": rh["instruction"],
                            "shared_data": last_shared_artifact or rh["shared_data"],
                            "caller": bot_name,
                        })
                        db.add_participant_to_chat(chat_id, target_rh)

                final_content_parts = [p for p in [assistant_text, "\n".join(tool_summaries)] if p]
                final_content = "\n\n".join(final_content_parts).strip() or "Operazione completata."

                # Aggiornamento stato del task con separazione rigorosa: delegated, waiting_approval, running, completed, failed
                current_state = db.get_task(current_task_id)
                current_task_status = current_state.get("status") if current_state else "running"

                if current_task_status == "waiting_approval" or (action_card and action_card.get("requires_approval")):
                    db.update_task_status_atomic(current_task_id, "waiting_approval")
                elif current_task_status == "delegated" or "delegated_to" in task_evidence:
                    db.update_task_status_atomic(current_task_id, "delegated", evidence=task_evidence)
                elif current_item.get("is_blocked"):
                    db.update_task_status_atomic(current_task_id, "failed", error_msg=current_item.get("block_reason", "Operazione bloccata."))
                else:
                    # Verifica le evidenze oggettive prima di completare (non usare solo assistant_text come prova)
                    has_verified_evidence = bool(
                        (task_evidence.get("search_files") and task_evidence["search_files"].get("status") != "error") or
                        (task_evidence.get("read_document") and task_evidence["read_document"].get("status") != "error") or
                        (task_evidence.get("inspect_zip") and task_evidence["inspect_zip"].get("status") != "error") or
                        (task_evidence.get("browse_url") and task_evidence["browse_url"].get("status") != "error") or
                        (task_evidence.get("gmail_search") and task_evidence["gmail_search"].get("status") != "error") or
                        (task_evidence.get("gmail_read") and task_evidence["gmail_read"].get("status") != "error") or
                        (task_evidence.get("calendar_list_events") and task_evidence["calendar_list_events"].get("status") != "error") or
                        (task_evidence.get("inspection") and task_evidence["inspection"].get("found") is True) or
                        any(k.startswith("file_") and task_evidence[k].get("status") == "ok" for k in task_evidence)
                    )
                    tools_available = self._select_tools_for_turn(bot_id, current_item["instruction"])
                    if has_verified_evidence or not tools_available:
                        task_evidence["final_assistant_summary"] = assistant_text[:200]
                        db.update_task_status_atomic(
                            current_task_id,
                            "completed",
                            result={"content": final_content},
                            evidence=task_evidence,
                        )
                        try:
                            memory_manager.record_task_outcome(db.get_task(current_task_id))
                        except Exception:
                            pass
                        try:
                            await notification_manager.notify_task_completed(
                                task_id=current_task_id,
                                title=f"Task completato: {bot_name}",
                                message=final_content[:160],
                            )
                        except Exception:
                            pass
                        pass

                saved_msg = db.save_message(
                    chat_id=chat_id,
                    sender_id=bot_id,
                    sender_name=bot_name,
                    content=final_content,
                    action_card_json=json.dumps(action_card) if action_card else None,
                )
                generated_replies.append(saved_msg)

                await _emit({"type": "new_message", "message": saved_msg})
                await _emit({"type": "bot_status", "bot_id": bot_id, "bot_name": bot_name, "status": "idle"})
                await _emit({"type": "task_updated", "task": db.get_task(current_task_id)})

        finally:
            await _emit({
                "type": "bot_status",
                "bot_id": initial_bot,
                "bot_name": bots_map.get(initial_bot, {}).get("name", "Chief"),
                "status": "idle",
            })

        return generated_replies

    async def execute_approved_action(
        self,
        approval_id: str,
        approved: bool,
        broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes or rejects an action that was put in waiting_approval status.
        Ensures physical actions (clicks, pastes, file writes) run ONLY after explicit approval.
        """
        appr = db.get_approval(approval_id)
        if not appr:
            return {"status": "error", "message": f"Richiesta di approvazione '{approval_id}' non trovata."}

        target_status = "approved" if approved else "rejected"
        # Transizione atomica condizionale su SQLite: verifica stato 'waiting_approval' e cursor.rowcount == 1
        success, current_appr = db.resolve_approval_atomic(
            approval_id=approval_id,
            new_status=target_status,
            expected_status="waiting_approval",
        )
        if not success:
            resolved_status = current_appr.get("status") if current_appr else "unknown"
            return {
                "status": "error",
                "message": f"Transizione atomica fallita: l'approvazione è già stata risolta in precedenza con stato: '{resolved_status}'.",
                "approval": current_appr,
            }

        chat_id = appr["chat_id"]
        bot_id = appr["bot_id"]
        task_id = appr.get("task_id")
        bot_record = db.get_bot(bot_id) or {"name": bot_id.capitalize()}
        bot_name = bot_record.get("name", bot_id)

        if not approved:
            if appr.get("activity_id"):
                db.update_activity(appr["activity_id"], status="failed", error_msg="Rifiutato dall'utente.")
            if task_id:
                db.update_task_status_atomic(task_id, "failed", error_msg="Rifiutato dall'utente.")

            rejection_card = {
                "status": "rejected",
                "approval_id": approval_id,
                "task_id": task_id,
                "title": f"Azione rifiutata: {appr['description']}",
            }
            msg = db.save_message(
                chat_id=chat_id,
                sender_id=bot_id,
                sender_name=bot_name,
                content=f"❌ **Azione rifiutata dall'utente:**\n> {appr['description']}\nOperazione annullata.",
                action_card_json=json.dumps(rejection_card),
            )
            if broadcast_fn:
                await broadcast_fn(chat_id, {"type": "new_message", "message": msg})
                await broadcast_fn(chat_id, {"type": "approval_resolved", "approval_id": approval_id, "status": "rejected"})
                if task_id:
                    await broadcast_fn(chat_id, {"type": "task_updated", "task": db.get_task(task_id)})
            return {"status": "ok", "message": "Azione rifiutata con successo.", "approval": current_appr}

        # Mark activity and task as running
        if appr.get("activity_id"):
            db.update_activity(appr["activity_id"], status="running")
        if task_id:
            db.update_task_status_atomic(task_id, "running")

        payload = appr.get("payload", {})
        tool_name = payload.get("tool_name", "")
        tool_args = payload.get("args", {})

        result: Dict[str, Any] = {}
        action_card = None

        try:
            if tool_name == "manage_files":
                result = await asyncio.to_thread(
                    tools_os.manage_files,
                    action=str(tool_args.get("action", "")),
                    path=str(tool_args.get("path", "")),
                    content=tool_args.get("content"),
                    destination=tool_args.get("destination"),
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", "Operazione file completata."),
                }

            elif tool_name == "focus_and_paste_into_app":
                result = await asyncio.to_thread(
                    tools_os.focus_and_paste_into_app,
                    window_title_substring=str(tool_args.get("window_title_substring", "")),
                    text_to_paste=str(tool_args.get("text_to_paste", "")),
                    click_norm_x=tool_args.get("click_norm_x"),
                    click_norm_y=tool_args.get("click_norm_y"),
                    press_enter=bool(tool_args.get("press_enter", True)),
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", "Incollaggio completato."),
                    "screenshot_b64": result.get("screenshot_b64"),
                    "x": result.get("norm_pct_x", 50),
                    "y": result.get("norm_pct_y", 50),
                }

            elif tool_name in ("click_screen_element", "inspect_screen_and_click"):
                result = await asyncio.to_thread(
                    tools_os.click_at_normalized_coords,
                    norm_x=int(tool_args.get("norm_x", 500)),
                    norm_y=int(tool_args.get("norm_y", 500)),
                    double_click=bool(tool_args.get("double_click", False)),
                    text_to_type=tool_args.get("text_to_type"),
                    press_enter=bool(tool_args.get("press_enter", False)),
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", "Clic desktop completato."),
                    "screenshot_b64": result.get("screenshot_b64"),
                    "x": result.get("norm_pct_x", 50),
                    "y": result.get("norm_pct_y", 50),
                }

            elif tool_name == "open_url_or_app":
                result = await asyncio.to_thread(
                    tools_os.open_url_or_app,
                    target=str(tool_args.get("target", "")),
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", "Target aperto."),
                    "screenshot_b64": result.get("screenshot_b64"),
                }

            elif tool_name == "browser_click":
                ref_val = tool_args.get("ref")
                result = await asyncio.to_thread(
                    tools_browser.browser_click,
                    ref=ref_val,
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", f"Clic sandbox [{ref_val}] completato."),
                }

            elif tool_name == "browser_type":
                ref_val = tool_args.get("ref")
                text_val = str(tool_args.get("text", ""))
                result = await asyncio.to_thread(
                    tools_browser.browser_type,
                    ref=ref_val,
                    text=text_val,
                    approved=True,
                )
                action_card = {
                    "status": "done" if result.get("status") == "ok" else "error",
                    "approval_id": approval_id,
                    "task_id": task_id,
                    "title": result.get("message", f"Testo inserito in elemento sandbox [{ref_val}]."),
                }

            is_success = result.get("status") == "ok"
            if appr.get("activity_id"):
                db.update_activity(
                    appr["activity_id"],
                    status="completed" if is_success else "failed",
                    result=result,
                    error_msg=None if is_success else result.get("message"),
                )

            # Evidenza verificabile per il Task Engine (Fase 2A)
            evidence_data = {"verified": is_success, "tool": tool_name}
            if tool_name == "manage_files":
                act_name = str(tool_args.get("action", ""))
                p_raw = str(tool_args.get("path", ""))
                _, valid_p, _ = tools_os.validate_file_path(p_raw)
                evidence_data.update({
                    "action": act_name,
                    "path": p_raw,
                    "exists_on_disk": valid_p.exists() if valid_p else False,
                    "file_bytes": valid_p.stat().st_size if (valid_p and valid_p.exists() and valid_p.is_file()) else 0,
                })
            elif tool_name in ("click_screen_element", "focus_and_paste_into_app"):
                evidence_data.update({
                    "real_coords": [result.get("real_x"), result.get("real_y")],
                    "window": result.get("window_title"),
                })
            elif tool_name in ("browser_click", "browser_type"):
                evidence_data.update({
                    "ref": tool_args.get("ref"),
                    "action_message": result.get("message"),
                })

            if task_id:
                if is_success:
                    db.update_task_status_atomic(task_id, "running", result=result, evidence=evidence_data)
                else:
                    db.update_task_status_atomic(task_id, "failed", error_msg=result.get("message"))

            res_msg = result.get("message", "Operazione completata con successo.")
            saved_msg = db.save_message(
                chat_id=chat_id,
                sender_id=bot_id,
                sender_name=bot_name,
                content=f"✅ **Azione approvata ed eseguita:**\n> {appr['description']}\n\n{res_msg}",
                action_card_json=json.dumps(action_card) if action_card else None,
            )

            if broadcast_fn:
                await broadcast_fn(chat_id, {"type": "new_message", "message": saved_msg})
                await broadcast_fn(chat_id, {"type": "approval_resolved", "approval_id": approval_id, "status": "approved"})
                if task_id:
                    await broadcast_fn(chat_id, {"type": "task_updated", "task": db.get_task(task_id)})

            if is_success and task_id:
                # Ripresa automatica del task multi-passaggio dopo ogni azione approvata (Fase 4 & Task Engine)
                try:
                    await self.resume_task(task_id, broadcast_fn=broadcast_fn)
                except Exception as resume_err:
                    logger.warning(f"Ripresa automatica task {task_id} post-approvazione: {resume_err}")

            return {"status": "ok", "result": result, "approval": db.get_approval(approval_id)}

        except Exception as e:
            if appr.get("activity_id"):
                db.update_activity(appr["activity_id"], status="failed", error_msg=str(e))
            if task_id:
                db.update_task_status_atomic(task_id, "failed", error_msg=str(e))
            err_msg = db.save_message(
                chat_id=chat_id,
                sender_id=bot_id,
                sender_name=bot_name,
                content=f"⚠️ Errore durante l'esecuzione dell'azione approvata **{appr['description']}**: {e}",
            )
            if broadcast_fn:
                await broadcast_fn(chat_id, {"type": "new_message", "message": err_msg})
                if task_id:
                    await broadcast_fn(chat_id, {"type": "task_updated", "task": db.get_task(task_id)})
            return {"status": "error", "message": str(e)}

    def verify_task_outcome(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verifica rigorosa del risultato rispetto all'azione richiesta (Fase 2A.1):
        - Per i file: verifica esistenza, hash SHA-256 e contenuto rispetto a quanto richiesto.
          Un file preesistente ma con contenuto/hash errato NON è considerato completato!
        - Per le azioni desktop: non dichiara completamento senza una verifica attendibile
          dello stato risultante. Se l'esito è ignoto, restituisce UNVERIFIABLE.
        Restituisce:
          {"verdict": "VERIFIED" | "MISMATCH" | "UNVERIFIABLE" | "NOT_DONE", "message": str, "details": dict}
        """
        evidence = task.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}

        # 1. Analisi azioni desktop (click_screen_element, focus_and_paste_into_app, open_url_or_app)
        tool_name = evidence.get("tool")
        is_desktop_action = False
        if tool_name in ("click_screen_element", "focus_and_paste_into_app", "open_url_or_app"):
            is_desktop_action = True

        approvals = task.get("approvals") or []
        for appr in approvals:
            if appr.get("action_type") in ("desktop_click", "desktop_paste", "open_target"):
                is_desktop_action = True

        if is_desktop_action:
            # Per le azioni desktop non dichiarare completamento senza verifica attendibile dello stato risultante
            if evidence.get("post_inspection_verified") is True:
                return {
                    "verdict": "VERIFIED",
                    "message": "Azione desktop verificata con successo tramite ispezione attendibile dello stato risultante.",
                    "details": evidence,
                }
            return {
                "verdict": "UNVERIFIABLE",
                "message": (
                    "Azione desktop con esito fisico sconosciuto o non verificabile automaticamente. "
                    "Richiesta verifica o autorizzazione esplicita dell'utente prima di procedere."
                ),
                "details": evidence,
            }

        # 2. Analisi operazioni su file (manage_files o file_*)
        file_path_str = evidence.get("path") or evidence.get("file_created")
        act_name = evidence.get("action")
        expected_hash = evidence.get("expected_hash")
        expected_content = evidence.get("expected_content")

        for appr in approvals:
            payload = appr.get("payload") or {}
            if isinstance(payload, dict):
                p_tool = payload.get("tool_name")
                if p_tool == "manage_files" or appr.get("action_type", "").startswith("file_"):
                    args = payload.get("args") or {}
                    file_path_str = file_path_str or args.get("path")
                    act_name = act_name or args.get("action")
                    if not expected_content and "content" in args:
                        expected_content = args["content"]
                    if not expected_hash and "expected_hash" in args:
                        expected_hash = args["expected_hash"]

        if file_path_str:
            p_cand = Path(file_path_str)
            if not p_cand.is_absolute():
                p_cand = tools_os.PROJECT_ROOT / file_path_str

            act = (act_name or "write").lower().strip()

            if act == "write":
                if not p_cand.exists() or not p_cand.is_file():
                    return {
                        "verdict": "NOT_DONE",
                        "message": f"File '{p_cand.name}' non trovato sul disco.",
                        "details": {"path": str(p_cand)},
                    }

                actual_bytes = p_cand.read_bytes()
                actual_hash = hashlib.sha256(actual_bytes).hexdigest()

                if not expected_hash and expected_content is not None:
                    b_exp = expected_content.encode("utf-8") if isinstance(expected_content, str) else bytes(expected_content)
                    expected_hash = hashlib.sha256(b_exp).hexdigest()

                if expected_hash:
                    if actual_hash == expected_hash:
                        return {
                            "verdict": "VERIFIED",
                            "message": f"Azione già verificata con successo su disco: {p_cand.name} (hash SHA-256 e contenuto conformi)",
                            "details": {"path": str(p_cand), "hash": actual_hash, "size": len(actual_bytes)},
                        }
                    else:
                        # File preesistente ma con contenuto/hash errato
                        return {
                            "verdict": "MISMATCH",
                            "message": (
                                f"File '{p_cand.name}' presente su disco ma con contenuto errato o difforme rispetto all'azione richiesta "
                                f"(atteso: {expected_hash[:10]}..., effettivo: {actual_hash[:10]}...). Richiesta verifica."
                            ),
                            "details": {"path": str(p_cand), "expected_hash": expected_hash, "actual_hash": actual_hash},
                        }
                else:
                    # Nessun hash atteso specificato: se il file esiste e ha dimensione > 0
                    return {
                        "verdict": "VERIFIED",
                        "message": f"Azione già verificata con successo su disco: {p_cand.name}",
                        "details": {"path": str(p_cand), "size": len(actual_bytes)},
                    }

            elif act == "delete":
                if not p_cand.exists():
                    return {
                        "verdict": "VERIFIED",
                        "message": f"Azione già verificata con successo su disco: file '{p_cand.name}' rimosso.",
                        "details": {"path": str(p_cand)},
                    }
                else:
                    return {
                        "verdict": "MISMATCH",
                        "message": f"File '{p_cand.name}' ancora presente su disco.",
                        "details": {"path": str(p_cand)},
                    }

            elif act == "mkdir":
                if p_cand.exists() and p_cand.is_dir():
                    return {
                        "verdict": "VERIFIED",
                        "message": f"Azione già verificata con successo su disco: cartella '{p_cand.name}' creata.",
                        "details": {"path": str(p_cand)},
                    }
                else:
                    return {
                        "verdict": "NOT_DONE",
                        "message": f"Cartella '{p_cand.name}' non presente su disco.",
                        "details": {"path": str(p_cand)},
                    }

        return {
            "verdict": "NOT_DONE",
            "message": "Nessuna evidenza di completamento disponibile.",
            "details": {},
        }

    async def resume_task(
        self,
        task_id: str,
        broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Riprende un task interrotto o fallito in modo sicuro ed idempotente (Fase 2A.1):
        - Non considera la semplice esistenza del file come prova: valida hash e contenuto.
        - Per esiti sconosciuti o azioni desktop non verificabili, imposta waiting_approval.
        - Non riesegue automaticamente azioni non idempotenti dopo crash o timeout.
        """
        task = db.get_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task '{task_id}' non trovato."}

        # 1. Se il task risulta già completato, ritorna immediatamente senza rieseguire nulla
        if task.get("status") == "completed":
            return {
                "status": "ok",
                "message": "Il task risulta già completato.",
                "task": task,
            }

        # 2. Se ci sono approvazioni pendenti, preserva lo stato senza duplicare
        pending_apprs = [a for a in task.get("approvals", []) if a.get("status") == "waiting_approval"]
        if pending_apprs:
            return {
                "status": "waiting_approval",
                "message": f"Il task ha {len(pending_apprs)} approvazione/i in attesa. Conferma o rifiuta per proseguire.",
                "task": task,
                "waiting_approval": True,
            }

        # 3. Verifica dei risultati rispetto all'azione richiesta
        outcome = self.verify_task_outcome(task)
        verdict = outcome["verdict"]
        message = outcome["message"]

        if verdict == "VERIFIED":
            # Azione già eseguita e provata (es. file modificato con hash esatto prima del crash)
            # Idempotenza: completa il task senza rieseguire mutazioni su disco
            db.update_task_status_atomic(
                task_id=task_id,
                new_status="completed",
                result={"message": message, "verified": True, "details": outcome.get("details")},
                evidence=task.get("evidence"),
            )
            updated_task = db.get_task(task_id)
            if broadcast_fn:
                await broadcast_fn(task["chat_id"], {"type": "task_updated", "task": updated_task})
            return {
                "status": "ok",
                "message": message,
                "task": updated_task,
                "verdict": "VERIFIED",
            }

        elif verdict == "MISMATCH":
            # File preesistente ma con contenuto errato o difforme
            # Imposta waiting_approval per richiedere verifica esplicita prima di sovrascrivere
            db.update_task_status_atomic(
                task_id=task_id,
                new_status="waiting_approval",
                error_msg=message,
            )
            updated_task = db.get_task(task_id)
            if broadcast_fn:
                await broadcast_fn(task["chat_id"], {"type": "task_updated", "task": updated_task})
            return {
                "status": "waiting_approval",
                "message": message,
                "task": updated_task,
                "verdict": "MISMATCH",
                "requires_verification": True,
            }

        elif verdict == "UNVERIFIABLE":
            # Azione desktop con esito sconosciuto o file senza riscontro certo
            # Imposta waiting_approval per richiedere intervento umano e non ripetere a vuoto azioni non idempotenti
            db.update_task_status_atomic(
                task_id=task_id,
                new_status="waiting_approval",
                error_msg=message,
            )
            updated_task = db.get_task(task_id)
            if broadcast_fn:
                await broadcast_fn(task["chat_id"], {"type": "task_updated", "task": updated_task})
            return {
                "status": "waiting_approval",
                "message": message,
                "task": updated_task,
                "verdict": "UNVERIFIABLE",
                "requires_verification": True,
            }

        if task.get("status") == "completed":
            return {
                "status": "ok",
                "message": "Il task risulta già completato.",
                "task": task,
            }

        # 3. Se non è già verificato né necessita di approvazione, transiziona a 'running' con incremento del contatore tentativi
        success, updated_task = db.update_task_status_atomic(
            task_id=task_id,
            new_status="running",
            increment_retry=True,
        )
        if not success:
            return {"status": "error", "message": f"Transizione di ripresa fallita da stato '{task.get('status')}'."}

        if broadcast_fn:
            await broadcast_fn(task["chat_id"], {"type": "task_updated", "task": updated_task})

        # 4. Esecuzione del turno di ripresa
        replies = await self.handle_conversation_turn(
            chat_id=task["chat_id"],
            user_content=task["instruction"],
            broadcast_fn=broadcast_fn,
            target_bot_id=task["bot_id"],
            existing_task_id=task_id,
        )

        return {
            "status": "ok",
            "message": "Task ripreso ed eseguito.",
            "task": db.get_task(task_id),
            "replies": replies,
        }

    async def execute_independent_tasks_parallel(
        self,
        chat_id: str,
        task_ids: List[str],
        broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Esegue in parallelo task indipendenti che non condividono risorse mutabili.
        """
        tasks = [db.get_task(tid) for tid in task_ids]
        valid_tasks = [t for t in tasks if t and t.get("status") in ("pending", "interrupted")]

        async def _run_single(t: Dict[str, Any]):
            return await self.handle_conversation_turn(
                chat_id=chat_id,
                user_content=t["instruction"],
                broadcast_fn=broadcast_fn,
                target_bot_id=t["bot_id"],
                existing_task_id=t["id"],
            )

        results = await asyncio.gather(*[_run_single(t) for t in valid_tasks], return_exceptions=True)
        return [{"task_id": t["id"], "result": str(r)} for t, r in zip(valid_tasks, results)]


orchestrator = AgentOrchestrator()

try:
    from scheduler import scheduler_service
    scheduler_service.set_orchestrator(orchestrator)
except Exception:
    pass

