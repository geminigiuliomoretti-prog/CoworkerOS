# 01_BACKEND

--- FILE: backend/main.py ---

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

import database as db
import tools_os
from agent_engine import orchestrator, ENV_PATH

load_dotenv(dotenv_path=ENV_PATH, override=True)

app = FastAPI(title="CoworkerOS Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, chat_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(chat_id, []).append(websocket)

    def disconnect(self, chat_id: str, websocket: WebSocket) -> None:
        if chat_id in self.active_connections:
            self.active_connections[chat_id] = [
                ws for ws in self.active_connections[chat_id] if ws != websocket
            ]

    async def broadcast(self, chat_id: str, payload: Dict[str, Any]) -> None:
        conns = list(self.active_connections.get(chat_id, []))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(chat_id, ws)


manager = ConnectionManager()


class SendMessageRequest(BaseModel):
    content: str
    target_bot_id: Optional[str] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    action_card: Optional[Any] = None


class CreateBotRequest(BaseModel):
    name: str
    role: str
    system_prompt: Optional[str] = ""
    shape: str = "squircle"
    color: str = "#10B981"
    effort: str = "medium"


class CreateChatRequest(BaseModel):
    title: str
    participants: List[str]


class ApiKeyRequest(BaseModel):
    api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    def get_key(self) -> str:
        return (self.api_key or self.gemini_api_key or "").strip()


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    db.seed_db()
    orchestrator.reload_client()


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    return {"status": "ok", "app": "CoworkerOS"}


@app.get("/api/bootstrap")
def api_bootstrap() -> Dict[str, Any]:
    return {
        "bots": db.get_all_bots(),
        "chats": db.get_all_chats(),
        "has_api_key": bool(orchestrator.api_key),
    }


@app.get("/api/chats/{chat_id}/messages")
def api_get_messages(chat_id: str) -> List[Dict[str, Any]]:
    return db.get_chat_messages(chat_id, limit=100)


@app.post("/api/chats/{chat_id}/messages")
async def api_send_message(chat_id: str, req: SendMessageRequest) -> Dict[str, Any]:
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Messaggio vuoto")

    user_msg = db.save_message(
        chat_id=chat_id,
        sender_id="user",
        sender_name=req.sender_name or "You",
        content=content,
        action_card_json=json.dumps(req.action_card) if isinstance(req.action_card, dict) else req.action_card,
    )
    await manager.broadcast(chat_id, {"type": "new_message", "message": user_msg})

    bot_replies = await orchestrator.handle_conversation_turn(
        chat_id=chat_id,
        user_content=content,
        broadcast_fn=manager.broadcast,
        target_bot_id=req.target_bot_id,
    )
    current_chat = db.get_chat(chat_id)
    return {
        "status": "ok",
        "user_message": user_msg,
        "bot_replies": bot_replies,
        "chat": current_chat,
        "updated_chat": current_chat,
    }


@app.post("/api/bots")
def api_create_bot(req: CreateBotRequest) -> Dict[str, Any]:
    bot_id = req.name.lower().strip().replace(" ", "_")
    bot_data = {
        "id": bot_id,
        "name": req.name.strip(),
        "role": req.role.strip(),
        "system_prompt": req.system_prompt or f"Sei {req.name}, {req.role}.",
        "shape": req.shape,
        "color": req.color,
        "effort": req.effort,
    }
    created_bot = db.create_bot(bot_data)
    created_chat = db.create_chat(req.name.strip(), [bot_id], chat_id=f"chat_{bot_id}")
    return {"bot": created_bot, "chat": created_chat}


@app.post("/api/chats")
def api_create_chat(req: CreateChatRequest) -> Dict[str, Any]:
    chat = db.create_chat(req.title.strip(), req.participants)
    return {"chat": chat}


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str) -> Dict[str, Any]:
    if hasattr(db, "delete_chat"):
        db.delete_chat(chat_id)
    return {"status": "ok"}


@app.get("/api/settings")
def api_get_settings() -> Dict[str, Any]:
    masked = ""
    if orchestrator.api_key:
        masked = orchestrator.api_key[:6] + "..." + orchestrator.api_key[-4:]
    return {"has_api_key": bool(orchestrator.api_key), "masked_key": masked}


@app.post("/api/settings/apikey")
def api_set_apikey(req: ApiKeyRequest) -> Dict[str, Any]:
    clean_key = req.get_key()
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"GEMINI_API_KEY={clean_key}\n", encoding="utf-8")
    else:
        set_key(str(ENV_PATH), "GEMINI_API_KEY", clean_key)
    ok = orchestrator.reload_client(clean_key)
    return {"status": "ok" if ok else "error", "has_api_key": ok}


@app.post("/api/settings/reset")
def api_reset_settings() -> Dict[str, Any]:
    if hasattr(db, "reset_db"):
        db.reset_db()
    else:
        db.init_db()
        db.seed_db()
    return {"status": "ok", "message": "Database resettato"}


@app.get("/api/os/screenshot")
async def api_os_screenshot() -> Dict[str, Any]:
    return await asyncio.to_thread(tools_os.capture_screen_b64)


@app.get("/api/os/windows")
async def api_os_windows() -> Dict[str, Any]:
    return await asyncio.to_thread(tools_os.list_open_windows)


@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str) -> None:
    await manager.connect(chat_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "user_message":
                content = str(data.get("content", "")).strip()
                target_bot_id = data.get("target_bot_id")
                if content:
                    user_msg = db.save_message(chat_id, "user", "You", content, None)
                    await manager.broadcast(chat_id, {"type": "new_message", "message": user_msg})
                    asyncio.create_task(
                        orchestrator.handle_conversation_turn(
                            chat_id=chat_id,
                            user_content=content,
                            broadcast_fn=manager.broadcast,
                            target_bot_id=target_bot_id,
                        )
                    )
    except WebSocketDisconnect:
        manager.disconnect(chat_id, websocket)
    except Exception:
        manager.disconnect(chat_id, websocket)


--- FILE: backend/agent_engine.py ---

import os
import re
import json
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from dotenv import load_dotenv

from google import genai
from google.genai import types

import database as db
import tools_os

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
            name="inspect_screen_and_click",
            description="Cattura uno screenshot reale 2880x1920 del PC, lo analizza con Gemini Vision ed esegue opzionalmente clic/testo.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "goal_description": types.Schema(
                        type="STRING",
                        description="Elemento o informazioni da individuare sullo schermo.",
                    ),
                    "perform_click": types.Schema(
                        type="BOOLEAN",
                        description="True per fare clic sulle coordinate individuate.",
                    ),
                    "text_to_paste": types.Schema(
                        type="STRING",
                        description="Testo opzionale da incollare dopo il clic.",
                    ),
                    "press_enter": types.Schema(
                        type="BOOLEAN",
                        description="True per premere Invio dopo l'incollaggio.",
                    ),
                },
                required=["goal_description"],
            ),
        ),
        types.FunctionDeclaration(
            name="focus_and_paste_into_app",
            description="Porta in primo piano una finestra su Windows 11 (es. 'Antigravity' o 'Chrome'), clicca nell'input, incolla il testo con Ctrl+V e preme Invio.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "window_title_substring": types.Schema(
                        type="STRING",
                        description="Nome della finestra (es. 'Antigravity' o 'Chrome').",
                    ),
                    "text_to_paste": types.Schema(
                        type="STRING",
                        description="Testo da incollare.",
                    ),
                    "press_enter": types.Schema(
                        type="BOOLEAN",
                        description="True per premere Invio.",
                    ),
                },
                required=["window_title_substring", "text_to_paste"],
            ),
        ),
        types.FunctionDeclaration(
            name="open_url_or_app",
            description="Apre un URL nel browser o lancia un'applicazione.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "target": types.Schema(type="STRING", description="URL o comando app."),
                },
                required=["target"],
            ),
        ),
        types.FunctionDeclaration(
            name="manage_files",
            description="Gestisce file e cartelle sul PC (list, read, write, mkdir, move, delete).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "action": types.Schema(type="STRING", description="list, read, write, mkdir, move, delete"),
                    "path": types.Schema(type="STRING", description="Percorso file o cartella"),
                    "content": types.Schema(type="STRING", description="Contenuto per write"),
                },
                required=["action", "path"],
            ),
        ),
        types.FunctionDeclaration(
            name="run_terminal_command",
            description="Esegue un comando shell sul PC.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "command": types.Schema(type="STRING", description="Comando shell"),
                },
                required=["command"],
            ),
        ),
    ]
    return [types.Tool(function_declarations=declarations)]


class AgentOrchestrator:
    def __init__(self) -> None:
        self.api_key: str = ""
        self.client: Optional[genai.Client] = None
        self.tools = _build_gemini_tools()
        self.reload_client()

    def reload_client(self, new_api_key: Optional[str] = None) -> bool:
        load_dotenv(dotenv_path=ENV_PATH, override=True)
        key = (new_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if key and key not in ("your_api_key_here", "la_tua_chiave_qui"):
            self.api_key = key
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=10000)
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
        temperature: float = 0.35
    ) -> Tuple[Optional[types.GenerateContentResponse], str, Optional[str]]:
        if not self.client:
            if not self.reload_client():
                return None, MODEL_PRIMARY, "GEMINI_API_KEY non configurata. Inseriscila dalle Impostazioni (icona ingranaggio)."

        models_to_try = [MODEL_PRIMARY] + MODEL_FALLBACKS
        last_error = ""

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            tools=self.tools if enable_tools else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True) if enable_tools else None,
        )

        for model_name in models_to_try:
            for attempt in range(2):
                try:
                    response = await self.client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    return response, model_name, None
                except Exception as exc:
                    err_str = str(exc)
                    last_error = err_str
                    is_transient = any(code in err_str for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "overloaded", "504", "DEADLINE_EXCEEDED"))
                    if "404" in err_str or "NOT_FOUND" in err_str:
                        break
                    if is_transient and attempt == 0:
                        await asyncio.sleep(0.8)
                        continue
                    break

        return None, MODEL_PRIMARY, last_error

    async def _locate_element_with_vision(
        self,
        goal_description: str,
        window_bounds: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
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
                f"La finestra target Ã¨ in [xmin={nl}, ymin={nt}, xmax={nr}, ymax={nb}]. "
                f"La barra di input chat si trova nella parte bassa della finestra (intorno a y={max(nt + 100, nb - 85)})."
            )

        vision_prompt = (
            f"Analizza questo screenshot del desktop Windows 11 ({cap['screen_width']}x{cap['screen_height']}).\n"
            f"Obiettivo: {goal_description}\n{bounds_hint}\n"
            "Rispondi SOLO con un oggetto JSON valido:\n"
            '{"norm_x": <int 0-1000>, "norm_y": <int 0-1000>, "observation": "<descrizione dettagliata di cosa Ã¨ visibile sullo schermo>"}'
        )

        parts = [
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=vision_prompt),
        ]

        resp, _, _ = await self._call_gemini_resilient(
            contents=[types.Content(role="user", parts=parts)],
            system_instruction="Restituisci esclusivamente un JSON valido con norm_x, norm_y e observation.",
            enable_tools=False,
            temperature=0.1,
        )

        norm_x, norm_y = 650, 880
        observation = "Schermo acquisito correttamente."
        if resp and resp.text:
            match = re.search(r"\{.*\}", resp.text.strip(), re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    norm_x = int(parsed.get("norm_x", norm_x))
                    norm_y = int(parsed.get("norm_y", norm_y))
                    observation = str(parsed.get("observation", observation))
                except Exception:
                    pass

        return {
            "norm_x": max(0, min(1000, norm_x)),
            "norm_y": max(0, min(1000, norm_y)),
            "observation": observation,
            "initial_capture": cap,
        }

    def _extract_regex_handoffs(
        self,
        text: str,
        current_bot_id: str,
        already_queued_ids: List[str]
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

    async def handle_conversation_turn(
        self,
        chat_id: str,
        user_content: str,
        broadcast_fn: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
        target_bot_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        all_bots_list = db.get_all_bots()
        bots_map: Dict[str, Dict[str, Any]] = {b["id"]: b for b in all_bots_list}
        chat = db.get_chat(chat_id)
        participants = chat.get("participants", ["chief"]) if chat else ["chief"]

        initial_bot = target_bot_id if (target_bot_id and target_bot_id in bots_map) else (participants[0] if participants else "chief")
        turn_queue: List[Dict[str, str]] = [
            {
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

        try:
            while turn_queue and step < MAX_SWARM_STEPS:
                step += 1
                current_task = turn_queue.pop(0)
                bot_id = current_task["bot_id"]
                bot = bots_map.get(bot_id) or bots_map.get("chief")
                if not bot:
                    continue

                bot_id = bot["id"]
                bot_name = bot["name"]
                db.add_participant_to_chat(chat_id, bot_id)

                await _emit({
                    "type": "bot_status",
                    "bot_id": bot_id,
                    "bot_name": bot_name,
                    "status": "Thinking / Working...",
                })

                history_msgs = db.get_chat_messages(chat_id, limit=16)
                history_lines = [
                    f"[{m.get('sender_name') or m.get('sender_id')}]: {m.get('content', '')}"
                    for m in history_msgs[-10:]
                ]
                windows_snap = await asyncio.to_thread(tools_os.list_open_windows)
                open_wins_str = ", ".join(windows_snap.get("windows", [])[:10]) or "Nessuna finestra"

                system_prompt = (
                    f"{bot.get('system_prompt', '')}\n"
                    f"Il tuo ID Ã¨ '{bot_id}' e il tuo nome Ã¨ '{bot_name}'.\n"
                    f"Finestre aperte sul PC Windows 11 (2880x1920): {open_wins_str}.\n"
                    "REGOLE OBBLIGATORIE:\n"
                    "1. Quando devi coinvolgere un altro bot (architect, builder, scout, archivist), "
                    "INVOCA IL TOOL `delegate_to_coworker`!\n"
                    "2. Se sei Builder o devi guardare lo schermo / interagire con Antigravity o Chrome, "
                    "INVOCA `focus_and_paste_into_app` o `inspect_screen_and_click`!"
                )

                task_prompt = (
                    f"CRONOLOGIA CHAT:\n" + "\n".join(history_lines) + "\n\n"
                    f"COMPITO CORRENTE (da {current_task['caller']}): {current_task['instruction']}\n"
                )
                if current_task.get("shared_data") or last_shared_artifact:
                    task_prompt += f"\nCONTENUTO CONDIVISO:\n{current_task.get('shared_data') or last_shared_artifact}\n"

                resp, used_model, err = await self._call_gemini_resilient(
                    contents=[types.Content(role="user", parts=[types.Part.from_text(text=task_prompt)])],
                    system_instruction=system_prompt,
                    enable_tools=True,
                )

                if err or resp is None:
                    err_msg = db.save_message(
                        chat_id=chat_id,
                        sender_id=bot_id,
                        sender_name=bot_name,
                        content=f"âš ï¸ Errore Gemini ({used_model}): {err}",
                        action_card_json=None,
                    )
                    generated_replies.append(err_msg)
                    await _emit({"type": "new_message", "message": err_msg})
                    break

                function_calls = resp.function_calls or []
                text_parts: List[str] = []
                if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                    for p in resp.candidates[0].content.parts:
                        if getattr(p, "text", None):
                            text_parts.append(p.text)
                assistant_text = "\n".join(text_parts).strip()

                user_lower = (user_content + " " + current_task["instruction"]).lower()
                if not function_calls and bot_id == "builder":
                    if "antigravity" in user_lower or "incolla" in user_lower:
                        function_calls = [
                            types.FunctionCall(
                                name="focus_and_paste_into_app",
                                args={
                                    "window_title_substring": "Antigravity",
                                    "text_to_paste": current_task.get("shared_data") or last_shared_artifact or assistant_text,
                                    "press_enter": True,
                                },
                            )
                        ]
                    else:
                        function_calls = [
                            types.FunctionCall(
                                name="inspect_screen_and_click",
                                args={"goal_description": current_task["instruction"], "perform_click": False},
                            )
                        ]

                if not function_calls and any(k in user_lower for k in ("schermo", "schemro", "screenshot", "finestr", "vedi")):
                    function_calls = [
                        types.FunctionCall(
                            name="inspect_screen_and_click",
                            args={"goal_description": "Ispeziona il contenuto visibile sullo schermo", "perform_click": False},
                        )
                    ]

                action_card: Optional[Dict[str, Any]] = None
                queued_in_this_turn: List[str] = [item["bot_id"] for item in turn_queue]
                tool_summaries: List[str] = []

                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args) if fc.args else {}

                    if fn_name == "delegate_to_coworker":
                        target_id = str(fn_args.get("target_bot_id", "")).lower().strip().replace("@", "")
                        instr = str(fn_args.get("instruction", "Esegui il task."))
                        shared = str(fn_args.get("shared_data", "")) or assistant_text or last_shared_artifact
                        if target_id in bots_map and target_id not in queued_in_this_turn:
                            queued_in_this_turn.append(target_id)
                            turn_queue.append({
                                "bot_id": target_id,
                                "instruction": instr,
                                "shared_data": shared,
                                "caller": bot_name,
                            })
                            db.add_participant_to_chat(chat_id, target_id)
                            tool_summaries.append(f"ðŸ‘‰ Passaggio di consegne a **@{bots_map[target_id]['name']}**: *{instr}*")

                    elif fn_name == "inspect_screen_and_click":
                        goal = str(fn_args.get("goal_description", "Ispezione schermo"))
                        do_click = bool(fn_args.get("perform_click", False))
                        txt_paste = fn_args.get("text_to_paste")
                        press_ent = bool(fn_args.get("press_enter", False))

                        loc = await self._locate_element_with_vision(goal)
                        nx, ny = loc["norm_x"], loc["norm_y"]
                        obs = loc["observation"]

                        if do_click or txt_paste:
                            res_click = await asyncio.to_thread(
                                tools_os.click_at_normalized_coords, nx, ny, False, txt_paste, press_ent
                            )
                            action_card = {
                                "status": "done",
                                "title": f"{goal} ({res_click.get('screen_width')}x{res_click.get('screen_height')})",
                                "screenshot_b64": res_click.get("screenshot_b64"),
                                "x": res_click.get("norm_pct_x", 50),
                                "y": res_click.get("norm_pct_y", 50),
                            }
                            tool_summaries.append(f"ðŸ–¥ï¸ **Azione Schermo:** {obs}\n{res_click.get('message', '')}")
                        else:
                            rx, ry = tools_os.norm_to_physical_coords(nx, ny)
                            cap_marked = await asyncio.to_thread(tools_os.capture_screen_b64, rx, ry, False)
                            action_card = {
                                "status": "done",
                                "title": f"Screenshot analizzato ({cap_marked.get('screen_width')}x{cap_marked.get('screen_height')}) [{cap_marked.get('capture_method')}]",
                                "screenshot_b64": cap_marked.get("screenshot_b64"),
                                "x": cap_marked.get("norm_pct_x", 50),
                                "y": cap_marked.get("norm_pct_y", 50),
                            }
                            tool_summaries.append(f"ðŸ–¥ï¸ **Analisi Visiva Schermo:** {obs}")

                    elif fn_name == "focus_and_paste_into_app":
                        win_sub = str(fn_args.get("window_title_substring", "Antigravity"))
                        txt_paste = str(fn_args.get("text_to_paste", "")) or last_shared_artifact or assistant_text
                        press_ent = bool(fn_args.get("press_enter", True))

                        focus_info = await asyncio.to_thread(tools_os.force_activate_window, win_sub)
                        bounds = focus_info.get("bounds")
                        loc = await self._locate_element_with_vision(
                            f"Barra di input della chat dentro la finestra {win_sub}",
                            window_bounds=bounds,
                        )
                        res_paste = await asyncio.to_thread(
                            tools_os.focus_and_paste_into_app,
                            win_sub, txt_paste, loc["norm_x"], loc["norm_y"], press_ent
                        )
                        action_card = {
                            "status": "done" if res_paste.get("status") == "ok" else "error",
                            "title": res_paste.get("message", f"Incollato in {win_sub}"),
                            "screenshot_b64": res_paste.get("screenshot_b64"),
                            "x": res_paste.get("norm_pct_x", 75),
                            "y": res_paste.get("norm_pct_y", 88),
                        }
                        tool_summaries.append(f"âœ… **Computer Use ({win_sub}):** {res_paste.get('message')}")

                    elif fn_name == "open_url_or_app":
                        target = str(fn_args.get("target", ""))
                        res_open = await asyncio.to_thread(tools_os.open_url_or_app, target)
                        action_card = {
                            "status": "done",
                            "title": f"Aperto: {target}",
                            "screenshot_b64": res_open.get("screenshot_b64"),
                            "x": 50,
                            "y": 50,
                        }
                        tool_summaries.append(f"ðŸŒ {res_open.get('message')}")

                    elif fn_name == "manage_files":
                        res_file = await asyncio.to_thread(
                            tools_os.manage_files,
                            str(fn_args.get("action", "list")),
                            str(fn_args.get("path", ".")),
                            fn_args.get("content"),
                        )
                        tool_summaries.append(f"ðŸ“ **File System:** `{json.dumps(res_file, ensure_ascii=False)[:600]}`")

                    elif fn_name == "run_terminal_command":
                        res_cmd = await asyncio.to_thread(
                            tools_os.run_terminal_command,
                            str(fn_args.get("command", "echo ok")),
                        )
                        tool_summaries.append(f"ðŸ’» **Terminale:** `{res_cmd.get('stdout') or res_cmd.get('stderr')}`")

                if assistant_text and len(assistant_text) > 40:
                    last_shared_artifact = assistant_text

                regex_handoffs = self._extract_regex_handoffs(assistant_text, bot_id, queued_in_this_turn)
                for rh in regex_handoffs:
                    turn_queue.append({
                        "bot_id": rh["target_bot_id"],
                        "instruction": rh["instruction"],
                        "shared_data": last_shared_artifact or rh["shared_data"],
                        "caller": bot_name,
                    })
                    db.add_participant_to_chat(chat_id, rh["target_bot_id"])

                final_content_parts = [p for p in [assistant_text, "\n".join(tool_summaries)] if p]
                final_content = "\n\n".join(final_content_parts).strip() or "Operazione completata."

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

        finally:
            await _emit({
                "type": "bot_status",
                "bot_id": initial_bot,
                "bot_name": bots_map.get(initial_bot, {}).get("name", "Chief"),
                "status": "idle",
            })

        return generated_replies


orchestrator = AgentOrchestrator()


--- FILE: backend/tools_os.py ---

import os
import sys
import time
import base64
import shutil
import ctypes
import subprocess
import webbrowser
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# CONFIGURAZIONE IMMEDIATA HIGH-DPI WINDOWS 11 (2880x1920 @ 200% SCALING)
if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.user32.SetProcessDPIAware = lambda: 1
    except Exception:
        pass

import pyautogui
import pyperclip
import pygetwindow as gw
from PIL import Image, ImageDraw, ImageStat, ImageGrab
import mss

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.08

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0
BI_RGB = 0
SW_RESTORE = 9
SW_SHOW = 5
VK_MENU = 0x12
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", ctypes.c_uint32 * 3),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def get_physical_screen_size() -> Tuple[int, int]:
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return int(w), int(h)
        except Exception:
            pass
    size = pyautogui.size()
    return int(size.width), int(size.height)


def _is_image_black(img: Optional[Image.Image]) -> bool:
    if img is None:
        return True
    try:
        gray = img.convert("L")
        stat = ImageStat.Stat(gray)
        min_val, max_val = stat.extrema[0]
        mean_val = stat.mean[0]
        std_val = stat.stddev[0]
        if max_val < 10 or (mean_val < 1.8 and std_val < 1.2):
            return True
        return False
    except Exception:
        return True


def _capture_via_win32_bitblt_captureblt(width: int, height: int) -> Optional[Image.Image]:
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hdesktop = user32.GetDesktopWindow()
    hdc_screen = user32.GetWindowDC(hdesktop)
    if not hdc_screen:
        return None
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    if not hbmp:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hdesktop, hdc_screen)
        return None

    old_obj = gdi32.SelectObject(hdc_mem, hbmp)
    try:
        ok = gdi32.BitBlt(
            hdc_mem, 0, 0, width, height,
            hdc_screen, 0, 0, SRCCOPY | CAPTUREBLT
        )
        if not ok:
            return None

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_len = width * height * 4
        buffer = ctypes.create_string_buffer(buf_len)
        lines = gdi32.GetDIBits(
            hdc_mem, hbmp, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS
        )
        if lines != height:
            return None

        img = Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)
        return img.copy()
    except Exception:
        return None
    finally:
        gdi32.SelectObject(hdc_mem, old_obj)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hdesktop, hdc_screen)


def _capture_via_powershell_dotnet() -> Optional[Image.Image]:
    if sys.platform != "win32":
        return None
    try:
        tmp_path = Path(os.environ.get("TEMP", ".")) / "coworkeros_cap.png"
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
            f"$bmp.Save('{str(tmp_path)}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose();"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            timeout=3.5,
            check=False,
            creationflags=creationflags
        )
        if tmp_path.exists():
            img = Image.open(tmp_path).convert("RGB")
            return img.copy()
    except Exception:
        pass
    return None


def _draw_som_grid_and_crosshair(
    img: Image.Image,
    real_w: int,
    real_h: int,
    highlight_x: Optional[int] = None,
    highlight_y: Optional[int] = None,
    draw_grid: bool = False
) -> Image.Image:
    annotated = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", annotated.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    out_w, out_h = annotated.size

    if draw_grid:
        for step in range(100, 1000, 100):
            gx = int((step / 1000.0) * out_w)
            gy = int((step / 1000.0) * out_h)
            draw.line([(gx, 0), (gx, out_h)], fill=(255, 255, 255, 45), width=1)
            draw.line([(0, gy), (out_w, gy)], fill=(255, 255, 255, 45), width=1)
        for nx in range(200, 1000, 200):
            for ny in range(200, 1000, 200):
                px = int((nx / 1000.0) * out_w)
                py = int((ny / 1000.0) * out_h)
                label = f"{nx},{ny}"
                draw.rectangle([px - 22, py - 8, px + 22, py + 8], fill=(17, 24, 39, 155))
                draw.text((px - 19, py - 6), label, fill=(255, 255, 255, 230))

    if highlight_x is not None and highlight_y is not None and real_w > 0 and real_h > 0:
        cx = int((highlight_x / float(real_w)) * out_w)
        cy = int((highlight_y / float(real_h)) * out_h)
        r_outer = 22
        r_inner = 7
        draw.ellipse(
            [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
            fill=(249, 115, 22, 75),
            outline=(249, 115, 22, 245),
            width=3
        )
        draw.ellipse(
            [cx - r_inner - 2, cy - r_inner - 2, cx + r_inner + 2, cy + r_inner + 2],
            fill=(255, 255, 255, 255)
        )
        draw.ellipse(
            [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
            fill=(249, 115, 22, 255)
        )
        draw.line([(cx - 30, cy), (cx + 30, cy)], fill=(249, 115, 22, 230), width=2)
        draw.line([(cx, cy - 30), (cx, cy + 30)], fill=(249, 115, 22, 230), width=2)

    return Image.alpha_composite(annotated, overlay).convert("RGB")


def capture_screen_b64(
    highlight_x: Optional[int] = None,
    highlight_y: Optional[int] = None,
    draw_som_grid: bool = False
) -> Dict[str, Any]:
    real_w, real_h = get_physical_screen_size()
    captured_img: Optional[Image.Image] = None
    capture_method = "none"

    try:
        img1 = ImageGrab.grab(all_screens=False, include_layered_windows=True)
        if not _is_image_black(img1):
            captured_img = img1.convert("RGB")
            capture_method = "PIL.ImageGrab(layered)"
    except Exception:
        pass

    if captured_img is None:
        try:
            img2 = _capture_via_win32_bitblt_captureblt(real_w, real_h)
            if not _is_image_black(img2):
                captured_img = img2
                capture_method = "Win32.BitBlt(CAPTUREBLT)"
        except Exception:
            pass

    if captured_img is None:
        try:
            import dxcam  # type: ignore
            camera = dxcam.create(output_color="RGB")
            frame = camera.grab(new_frame_only=False)
            if frame is not None:
                img3 = Image.fromarray(frame)
                if not _is_image_black(img3):
                    captured_img = img3
                    capture_method = "DXcam.DXGI"
        except Exception:
            pass

    if captured_img is None:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img_mss = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                if not _is_image_black(img_mss):
                    captured_img = img_mss
                    capture_method = "mss"
        except Exception:
            pass

    if captured_img is None:
        img4 = _capture_via_powershell_dotnet()
        if not _is_image_black(img4):
            captured_img = img4
            capture_method = "PowerShell.CopyFromScreen"

    if captured_img is None:
        captured_img = Image.new("RGB", (real_w, real_h), (28, 32, 42))
        d = ImageDraw.Draw(captured_img)
        d.text((60, 50), f"Desktop Map ({real_w}x{real_h})", fill=(255, 255, 255))
        for w_info in list_open_windows().get("windows_detailed", [])[:8]:
            b = w_info.get("bounds", {})
            l, t, r, btm = b.get("left", 100), b.get("top", 100), b.get("right", 800), b.get("bottom", 600)
            d.rectangle([l, t, r, btm], outline=(96, 165, 250), fill=(38, 45, 64), width=3)
            d.text((l + 20, t + 20), w_info.get("title", "Window"), fill=(255, 255, 255))
        capture_method = "Win32.WindowMapFallback"

    real_w, real_h = captured_img.size
    preview_img = captured_img.copy()
    preview_img.thumbnail((1440, 960), Image.Resampling.LANCZOS)

    annotated_img = _draw_som_grid_and_crosshair(
        preview_img,
        real_w=real_w,
        real_h=real_h,
        highlight_x=highlight_x,
        highlight_y=highlight_y,
        draw_grid=draw_som_grid
    )

    buf = BytesIO()
    annotated_img.save(buf, format="JPEG", quality=84)
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

    norm_pct_x = round((highlight_x / float(real_w)) * 100.0, 1) if highlight_x is not None else 50.0
    norm_pct_y = round((highlight_y / float(real_h)) * 100.0, 1) if highlight_y is not None else 50.0

    return {
        "status": "ok",
        "capture_method": capture_method,
        "screenshot_b64": b64_str,
        "screen_width": real_w,
        "screen_height": real_h,
        "x": highlight_x,
        "y": highlight_y,
        "norm_pct_x": norm_pct_x,
        "norm_pct_y": norm_pct_y,
    }


def list_open_windows() -> Dict[str, Any]:
    windows_detailed: List[Dict[str, Any]] = []
    titles: List[str] = []

    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title and title not in ("Program Manager", "Settings", "Windows Input Experience"):
                        rect = RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 80 and h > 80:
                            titles.append(title)
                            windows_detailed.append({
                                "hwnd": int(hwnd),
                                "title": title,
                                "bounds": {
                                    "left": int(rect.left),
                                    "top": int(rect.top),
                                    "right": int(rect.right),
                                    "bottom": int(rect.bottom),
                                    "width": int(w),
                                    "height": int(h),
                                }
                            })
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
    else:
        try:
            for w in gw.getAllWindows():
                if w.title and w.visible:
                    titles.append(w.title)
        except Exception:
            pass

    return {
        "status": "ok",
        "count": len(titles),
        "windows": titles,
        "windows_detailed": windows_detailed,
    }


def force_activate_window(window_title_substring: str) -> Dict[str, Any]:
    target_sub = window_title_substring.strip().lower()
    win_data = list_open_windows().get("windows_detailed", [])

    candidates = [
        w for w in win_data
        if target_sub in w["title"].lower() and "coworkeros" not in w["title"].lower()
    ]
    if not candidates:
        candidates = [w for w in win_data if target_sub in w["title"].lower()]

    if not candidates:
        return {
            "status": "error",
            "message": f"Finestra '{window_title_substring}' non trovata.",
            "available_windows": [w["title"] for w in win_data[:12]],
        }

    chosen = candidates[0]
    hwnd = chosen["hwnd"]

    if sys.platform == "win32":
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
                time.sleep(0.25)
            else:
                user32.ShowWindow(hwnd, SW_SHOW)

            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY, 0)
            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)

            fg_hwnd = user32.GetForegroundWindow()
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
            target_tid = user32.GetWindowThreadProcessId(hwnd, None)
            cur_tid = kernel32.GetCurrentThreadId()

            if fg_tid and fg_tid != cur_tid:
                user32.AttachThreadInput(fg_tid, cur_tid, True)
            if target_tid and target_tid != cur_tid:
                user32.AttachThreadInput(target_tid, cur_tid, True)

            try:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                if fg_tid and fg_tid != cur_tid:
                    user32.AttachThreadInput(fg_tid, cur_tid, False)
                if target_tid and target_tid != cur_tid:
                    user32.AttachThreadInput(target_tid, cur_tid, False)

            time.sleep(0.55)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            chosen["bounds"] = {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
                "width": int(rect.right - rect.left),
                "height": int(rect.bottom - rect.top),
            }
        except Exception as e:
            return {"status": "error", "message": f"Errore attivazione finestra: {e}"}

    return {
        "status": "ok",
        "window_title": chosen["title"],
        "hwnd": hwnd,
        "bounds": chosen["bounds"],
    }


def norm_to_physical_coords(norm_x: int, norm_y: int) -> Tuple[int, int]:
    real_w, real_h = get_physical_screen_size()
    clamped_x = max(0, min(1000, int(norm_x)))
    clamped_y = max(0, min(1000, int(norm_y)))
    phys_x = int((clamped_x / 1000.0) * (real_w - 1))
    phys_y = int((clamped_y / 1000.0) * (real_h - 1))
    return phys_x, phys_y


def click_at_normalized_coords(
    norm_x: int,
    norm_y: int,
    double_click: bool = False,
    text_to_type: Optional[str] = None,
    press_enter: bool = False
) -> Dict[str, Any]:
    try:
        real_x, real_y = norm_to_physical_coords(norm_x, norm_y)
        pyautogui.moveTo(real_x, real_y, duration=0.28)
        if double_click:
            pyautogui.doubleClick(real_x, real_y)
        else:
            pyautogui.click(real_x, real_y)

        if text_to_type:
            time.sleep(0.18)
            pyperclip.copy(text_to_type)
            paste_key = "command" if sys.platform == "darwin" else "ctrl"
            pyautogui.hotkey(paste_key, "v")
            time.sleep(0.25)

        if press_enter:
            pyautogui.press("enter")
            time.sleep(0.35)

        cap = capture_screen_b64(highlight_x=real_x, highlight_y=real_y)
        return {
            "status": "ok",
            "message": f"Clic eseguito a ({real_x}, {real_y}) [norm: {norm_x}, {norm_y}]",
            "real_x": real_x,
            "real_y": real_y,
            **cap,
        }
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Errore clic: {e}", **cap}


def focus_and_paste_into_app(
    window_title_substring: str,
    text_to_paste: str,
    click_norm_x: Optional[int] = None,
    click_norm_y: Optional[int] = None,
    press_enter: bool = True
) -> Dict[str, Any]:
    focus_res = force_activate_window(window_title_substring)
    if focus_res.get("status") != "ok":
        cap = capture_screen_b64()
        return {**focus_res, **cap}

    bounds = focus_res["bounds"]
    real_w, real_h = get_physical_screen_size()

    if click_norm_x is not None and click_norm_y is not None:
        target_x, target_y = norm_to_physical_coords(click_norm_x, click_norm_y)
    else:
        win_left = max(0, bounds["left"])
        win_top = max(0, bounds["top"])
        win_w = min(real_w - win_left, bounds["width"])
        win_h = min(real_h - win_top, bounds["height"])
        target_x = int(win_left + win_w * 0.78)
        target_y = int(win_top + win_h * 0.88)

    try:
        pyperclip.copy(text_to_paste)
        pyautogui.moveTo(target_x, target_y, duration=0.3)
        pyautogui.click(target_x, target_y)
        time.sleep(0.22)

        paste_mod = "command" if sys.platform == "darwin" else "ctrl"
        pyautogui.hotkey(paste_mod, "v")
        time.sleep(0.35)

        if press_enter:
            pyautogui.press("enter")
            time.sleep(0.45)

        cap = capture_screen_b64(highlight_x=target_x, highlight_y=target_y)
        return {
            "status": "ok",
            "message": f"Finestra '{focus_res['window_title']}' attivata e testo incollato a ({target_x}, {target_y}).",
            "window_title": focus_res["window_title"],
            "real_x": target_x,
            "real_y": target_y,
            **cap,
        }
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Errore incollaggio: {e}", **cap}


def open_url_or_app(target: str) -> Dict[str, Any]:
    try:
        target_clean = target.strip()
        if target_clean.startswith("http://") or target_clean.startswith("https://"):
            webbrowser.open(target_clean)
            time.sleep(1.8)
        else:
            subprocess.Popen(target_clean, shell=True)
            time.sleep(1.5)
        cap = capture_screen_b64()
        return {"status": "ok", "message": f"Aperto target: {target_clean}", **cap}
    except Exception as e:
        cap = capture_screen_b64()
        return {"status": "error", "message": f"Impossibile aprire '{target}': {e}", **cap}


def manage_files(
    action: str,
    path: str,
    content: Optional[str] = None,
    destination: Optional[str] = None
) -> Dict[str, Any]:
    try:
        p = Path(path).expanduser().resolve()
        act = action.lower().strip()
        if act == "list":
            if not p.exists():
                return {"status": "error", "message": f"Percorso non trovato: {p}"}
            items = [
                {"name": item.name, "is_dir": item.is_dir(), "size": item.stat().st_size if item.is_file() else 0}
                for item in list(p.iterdir())[:100]
            ]
            return {"status": "ok", "path": str(p), "items": items}
        elif act == "read":
            text = p.read_text(encoding="utf-8", errors="replace")
            return {"status": "ok", "path": str(p), "content": text[:15000]}
        elif act == "write":
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content or "", encoding="utf-8")
            return {"status": "ok", "path": str(p), "message": f"Scritto file ({len(content or '')} caratteri)."}
        elif act == "mkdir":
            p.mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "path": str(p), "message": "Cartella creata."}
        elif act == "move" and destination:
            dest_p = Path(destination).expanduser().resolve()
            shutil.move(str(p), str(dest_p))
            return {"status": "ok", "message": f"Spostato in {dest_p}."}
        elif act == "delete":
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            return {"status": "ok", "message": f"Eliminato {p}."}
        return {"status": "error", "message": f"Azione non supportata: {action}"}
    except Exception as e:
        return {"status": "error", "message": f"Errore file system: {e}"}


def run_terminal_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    try:
        res = subprocess.run(
            command,
            shell=True,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            timeout=25,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "status": "ok" if res.returncode == 0 else "error",
            "returncode": res.returncode,
            "stdout": res.stdout[:8000],
            "stderr": res.stderr[:4000],
        }
    except Exception as e:
        return {"status": "error", "message": f"Errore comando: {e}"}


--- FILE: backend/database.py ---

"""
CoworkerOS SQLite Database Layer
Handles bots, chats, messages, and initial seeding.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

DB_PATH = Path(__file__).parent / "coworkers.db"

DEFAULT_BOTS = [
    {
        "id": "chief",
        "name": "Chief",
        "role": "Coordinator & Chief of Staff",
        "system_prompt": (
            "Sei Chief. Analizzi le richieste dell utente, pianifichi il lavoro e usi il tool "
            "delegate_to_coworker per passare i compiti agli altri bot (architect, builder, scout, archivist) "
            "senza che l utente debba fare nulla."
        ),
        "shape": "squircle",
        "color": "#00BA88",
        "effort": "high",
    },
    {
        "id": "architect",
        "name": "Architect",
        "role": "Product & Roadmap Strategist",
        "system_prompt": (
            "Sei Architect. Crei roadmap tecniche, prompt dettagliati per Antigravity e architetture software. "
            "Puoi usare il browser o consultare Gemini e poi passare il risultato a Builder tramite delegate_to_coworker."
        ),
        "shape": "circle",
        "color": "#FF6B00",
        "effort": "high",
    },
    {
        "id": "builder",
        "name": "Builder",
        "role": "PC & Antigravity Operator",
        "system_prompt": (
            "Sei Builder. Controlli fisicamente il PC dell utente: fai screenshot, trovi finestre come Antigravity o Chrome, "
            "le porti in primo piano, clicchi col mouse, copi e incolli codice o prompt nella chat di Antigravity e premi Invio."
        ),
        "shape": "triangle",
        "color": "#FF2E93",
        "effort": "low",
    },
    {
        "id": "scout",
        "name": "Scout",
        "role": "Web & Deep Researcher",
        "system_prompt": (
            "Sei Scout. Esegui ricerche web approfondite, raccogli documentazione e analizzi fonti esterne "
            "per fornire sintesi pronte all uso per il team."
        ),
        "shape": "cloud",
        "color": "#FFB800",
        "effort": "medium",
    },
    {
        "id": "archivist",
        "name": "Archivist",
        "role": "File System & Archive Manager",
        "system_prompt": (
            "Sei Archivist. Gestisci il file system locale, archivi e recuperi file di progetto, "
            "verifichi log e mantieni in ordine la memoria del workspace."
        ),
        "shape": "cylinder",
        "color": "#1D7AFC",
        "effort": "low",
    },
]


def get_connection() -> sqlite3.Connection:
    """Creates and returns a connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Initializes tables for bots, chats, and messages."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bots (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    shape TEXT NOT NULL,
                    color TEXT NOT NULL,
                    effort TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    is_group INTEGER DEFAULT 0,
                    participants_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    action_card_json TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_chat_timestamp ON messages(chat_id, timestamp);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON chats(updated_at);"
            )
    finally:
        conn.close()


def seed_db() -> None:
    """Populates default bots and individual initial chats idempotently."""
    conn = get_connection()
    try:
        with conn:
            for bot in DEFAULT_BOTS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO bots (id, name, role, system_prompt, shape, color, effort)
                    VALUES (:id, :name, :role, :system_prompt, :shape, :color, :effort);
                    """,
                    bot,
                )
                chat_id = f"chat_{bot['id']}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO chats (id, title, is_group, participants_json, updated_at)
                    VALUES (?, ?, 0, ?, CURRENT_TIMESTAMP);
                    """,
                    (chat_id, bot["name"], json.dumps([bot["id"]])),
                )
    finally:
        conn.close()


def get_all_bots() -> list[dict[str, Any]]:
    """Retrieves all bots from the database."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, name, role, system_prompt, shape, color, effort FROM bots ORDER BY id ASC;"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_bot(bot_id: str) -> dict[str, Any] | None:
    """Retrieves a single bot by ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, name, role, system_prompt, shape, color, effort FROM bots WHERE id = ?;",
            (bot_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_bot(data: dict[str, Any]) -> dict[str, Any]:
    """Creates a new bot record and returns it."""
    bot_id = data.get("id") or str(uuid.uuid4())[:8]
    bot_record = {
        "id": bot_id,
        "name": data["name"],
        "role": data["role"],
        "system_prompt": data["system_prompt"],
        "shape": data.get("shape", "circle"),
        "color": data.get("color", "#00BA88"),
        "effort": data.get("effort", "medium"),
    }
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO bots (id, name, role, system_prompt, shape, color, effort)
                VALUES (:id, :name, :role, :system_prompt, :shape, :color, :effort);
                """,
                bot_record,
            )
        return bot_record
    finally:
        conn.close()


def get_all_chats() -> list[dict[str, Any]]:
    """Retrieves all chats ordered by most recently updated first."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, title, is_group, participants_json, updated_at FROM chats ORDER BY updated_at DESC;"
        )
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            try:
                item["participants"] = json.loads(item["participants_json"])
            except Exception:
                item["participants"] = []
            results.append(item)
        return results
    finally:
        conn.close()


def get_chat(chat_id: str) -> dict[str, Any] | None:
    """Retrieves a single chat by ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, title, is_group, participants_json, updated_at FROM chats WHERE id = ?;",
            (chat_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["participants"] = json.loads(item["participants_json"])
        except Exception:
            item["participants"] = []
        return item
    finally:
        conn.close()


def create_chat(
    title: str,
    participants: list[str],
    is_group: bool = False,
    chat_id: str | None = None,
) -> dict[str, Any]:
    """Creates a new chat and returns its details."""
    if not chat_id:
        chat_id = f"chat_{uuid.uuid4().hex[:12]}"
    participants_json = json.dumps(participants)
    is_group_int = 1 if is_group else 0

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO chats (id, title, is_group, participants_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (chat_id, title, is_group_int, participants_json),
            )
            cursor = conn.execute(
                "SELECT id, title, is_group, participants_json, updated_at FROM chats WHERE id = ?;",
                (chat_id,),
            )
            row = cursor.fetchone()
            item = dict(row)
            item["participants"] = participants
            return item
    finally:
        conn.close()


def delete_chat(chat_id: str) -> bool:
    """Deletes a chat and its messages completely."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?;", (chat_id,))
            cursor = conn.execute("DELETE FROM chats WHERE id = ?;", (chat_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def reset_db() -> None:
    """Wipes all chats and messages, re-seeds default bots and clean individual chats."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM messages;")
            conn.execute("DELETE FROM chats;")
    finally:
        conn.close()
    seed_db()


def add_participant_to_chat(chat_id: str, bot_id: str) -> bool:
    """Adds a participant bot ID to a chat if not already present."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT participants_json FROM chats WHERE id = ?;",
            (chat_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False
        try:
            participants = json.loads(row["participants_json"])
        except Exception:
            participants = []

        if bot_id not in participants:
            participants.append(bot_id)
            with conn:
                conn.execute(
                    """
                    UPDATE chats
                    SET participants_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (json.dumps(participants), chat_id),
                )
            return True
        return False
    finally:
        conn.close()


def save_message(
    chat_id: str,
    sender_id: str,
    sender_name: str,
    content: str,
    action_card_json: str | dict[str, Any] | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    """Saves a new message to the chat and updates chat's updated_at timestamp."""
    if not message_id:
        message_id = str(uuid.uuid4())

    if isinstance(action_card_json, dict):
        action_card_str = json.dumps(action_card_json)
    elif isinstance(action_card_json, str):
        action_card_str = action_card_json
    else:
        action_card_str = None

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO messages (id, chat_id, sender_id, sender_name, content, action_card_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (message_id, chat_id, sender_id, sender_name, content, action_card_str),
            )
            conn.execute(
                "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (chat_id,),
            )
            cursor = conn.execute(
                """
                SELECT id, chat_id, sender_id, sender_name, content, action_card_json, timestamp
                FROM messages WHERE id = ?;
                """,
                (message_id,),
            )
            row = cursor.fetchone()
            msg = dict(row)
            if msg.get("action_card_json"):
                try:
                    msg["action_card"] = json.loads(msg["action_card_json"])
                except Exception:
                    msg["action_card"] = None
            else:
                msg["action_card"] = None
            return msg
    finally:
        conn.close()


def get_chat_messages(chat_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Returns the latest messages for a chat in chronological order (ASC).
    Deserializes action_card_json into action_card field if present.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, chat_id, sender_id, sender_name, content, action_card_json, timestamp
            FROM (
                SELECT rowid, id, chat_id, sender_id, sender_name, content, action_card_json, timestamp
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
            )
            ORDER BY timestamp ASC, rowid ASC;
            """,
            (chat_id, limit),
        )
        messages = []
        for row in cursor.fetchall():
            msg = dict(row)
            if msg.get("action_card_json"):
                try:
                    msg["action_card"] = json.loads(msg["action_card_json"])
                except Exception:
                    msg["action_card"] = None
            else:
                msg["action_card"] = None
            messages.append(msg)
        return messages
    finally:
        conn.close()


# Automatically initialize and seed database on import
init_db()
seed_db()


--- FILE: backend/requirements.txt ---

fastapi==0.115.0
uvicorn[standard]==0.30.6
websockets==13.0
google-genai>=1.0.0
python-dotenv==1.0.1
mss==9.0.2
pyautogui==0.9.54
pygetwindow==0.0.9
pyperclip==1.9.0
pillow==10.4.0
psutil==6.0.0
pydantic==2.9.2


--- FILE: backend/.env.example ---

# CoworkerOS Environment Configuration
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000
HOST=0.0.0.0

