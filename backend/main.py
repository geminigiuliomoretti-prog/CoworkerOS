import os
import hmac
import time
import json
import secrets
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Query, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

import database as db
import tools_os
from agent_engine import orchestrator, ENV_PATH
from memory_manager import memory_manager
from scheduler import scheduler_service
from usage_tracker import usage_tracker
from notifications import notification_manager
from local_model_manager import local_model_mgr

# 1. Caricamento e inizializzazione token di sicurezza locale
load_dotenv(dotenv_path=ENV_PATH, override=True)

AUTH_TOKEN = os.getenv("COWORKEROS_AUTH_TOKEN", "").strip()
if not AUTH_TOKEN or AUTH_TOKEN in ("your_token_here", "null"):
    AUTH_TOKEN = secrets.token_hex(32)
    os.environ["COWORKEROS_AUTH_TOKEN"] = AUTH_TOKEN
    set_key(str(ENV_PATH), "COWORKEROS_AUTH_TOKEN", AUTH_TOKEN)

HOST = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.getenv("PORT", "8000"))

app = FastAPI(title="CoworkerOS Engine - Hardened")

# Store in-memory dei ticket effimeri monouso per WebSocket (validità 15 secondi)
_WS_TICKETS: Dict[str, float] = {}


def create_ws_ticket() -> str:
    """Genera un ticket monouso con validità di 15 secondi."""
    now = time.time()
    for t, exp in list(_WS_TICKETS.items()):
        if exp < now:
            _WS_TICKETS.pop(t, None)
    ticket = secrets.token_urlsafe(32)
    _WS_TICKETS[ticket] = now + 15.0
    return ticket


def consume_ws_ticket(ticket_candidate: Optional[str]) -> bool:
    """Verifica e consuma immediatamente un ticket monouso."""
    if not ticket_candidate:
        return False
    now = time.time()
    expiry = _WS_TICKETS.pop(ticket_candidate.strip(), None)
    if expiry and expiry >= now:
        return True
    return False

# 2. CORS ristretto esclusivamente a loopback (nessun wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "null",
        "file://",
    ],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def verify_auth_token_value(token_candidate: Optional[str]) -> bool:
    """Verifica il token di autenticazione locale in tempo costante."""
    if not token_candidate:
        return False
    candidate_clean = token_candidate.strip()
    return hmac.compare_digest(candidate_clean, AUTH_TOKEN)


def verify_auth(
    authorization: Optional[str] = Header(None),
    x_coworkeros_token: Optional[str] = Header(None),
) -> str:
    """
    Dependency FastAPI per proteggere gli endpoint sensibili.
    Accetta credenziali ESCLUSIVAMENTE tramite header autorizzati (Authorization: Bearer o X-CoworkerOS-Token).
    Il passaggio di token via query parameter (?token=) è rigorosamente disabilitato.
    """
    extracted = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            extracted = parts[1]
        else:
            extracted = authorization
    elif x_coworkeros_token:
        extracted = x_coworkeros_token

    if not verify_auth_token_value(extracted):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non autorizzato: credenziali locali non valide o mancanti negli header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(extracted)


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


class CleanupTestChatsRequest(BaseModel):
    chat_ids: List[str]
    confirmed: bool = False


class ApiKeyRequest(BaseModel):
    api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    def get_key(self) -> str:
        return (self.api_key or self.gemini_api_key or "").strip()


class CreateMemoryRequest(BaseModel):
    content: str
    memory_type: str = "fact"
    project_id: str = "default"
    provenance_type: str = "manual"
    provenance_id: Optional[str] = None
    confidence: float = 1.0
    scope: str = "global"
    owner_bot_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UpdateMemoryRequest(BaseModel):
    content: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None
    scope: Optional[str] = None


class MemorySettingsRequest(BaseModel):
    auto_memory_enabled: Optional[bool] = None
    max_context_budget: Optional[int] = None


class CreateScheduledJobRequest(BaseModel):
    name: str
    prompt: str
    schedule_type: str
    schedule_config: Dict[str, Any]
    chat_id: str
    target_bot_id: str = "chief"
    project_id: str = "default"
    timezone: str = "UTC"
    missed_job_policy: str = "skip"
    description: Optional[str] = None


class UpdateScheduledJobRequest(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    status: Optional[str] = None
    missed_job_policy: Optional[str] = None
    description: Optional[str] = None


class SaveUsageLimitRequest(BaseModel):
    key: str
    value: Any


class ModelProviderRequest(BaseModel):
    mode: str  # LOCAL, CLOUD, AUTO


class ModelStartRequest(BaseModel):
    enable_vision: bool = False


@app.on_event("startup")
async def on_startup() -> None:
    db.init_db()
    db.seed_db()
    recovered = db.recover_interrupted_tasks()
    if recovered:
        print(f"[CoworkerOS] Recuperati {len(recovered)} task interrotti al riavvio.")
    orchestrator.reload_client()

    async def broadcast_notification_event(payload: Dict[str, Any]) -> None:
        for cid in list(manager.active_connections.keys()):
            await manager.broadcast(cid, payload)

    notification_manager.register_broadcast_callback(broadcast_notification_event)
    await scheduler_service.start_background_loop()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await scheduler_service.stop_background_loop()
    await local_model_mgr.stop_server_async()


# Endpoint pubblico per probe di salute Electron
@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    return {"status": "ok", "app": "CoworkerOS", "bound": "127.0.0.1"}


# ENDPOINTS PROTETTI DA AUTENTICAZIONE LOCALE

@app.get("/api/bootstrap")
def api_bootstrap(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    return {
        "bots": db.get_all_bots(),
        "chats": db.get_all_chats(),
        "has_api_key": bool(orchestrator.api_key),
        "auth_configured": True,
        "model_status": orchestrator.get_model_status(),
    }


@app.get("/api/model/status")
def api_get_model_status(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    return orchestrator.get_model_status()


@app.post("/api/model/provider")
async def api_set_model_provider(
    req: ModelProviderRequest, _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    return await orchestrator.set_provider_mode(req.mode)


@app.post("/api/model/start")
async def api_start_local_model(
    req: ModelStartRequest = ModelStartRequest(),
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    return await local_model_mgr.start_server_async(enable_vision=req.enable_vision)


@app.post("/api/model/stop")
async def api_stop_local_model(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    return await local_model_mgr.stop_server_async()


@app.get("/api/chats/{chat_id}/messages")
def api_get_messages(chat_id: str, _auth: str = Depends(verify_auth)) -> List[Dict[str, Any]]:
    return db.get_chat_messages(chat_id, limit=100)


@app.post("/api/chats/{chat_id}/messages")
async def api_send_message(
    chat_id: str,
    req: SendMessageRequest,
    _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Messaggio vuoto non valido")

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
def api_create_bot(req: CreateBotRequest, _auth: str = Depends(verify_auth)) -> Dict[str, Any]:
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
def api_create_chat(req: CreateChatRequest, _auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    chat = db.create_chat(req.title.strip(), req.participants)
    return {"chat": chat}


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str, _auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    if hasattr(db, "delete_chat"):
        db.delete_chat(chat_id)
    return {"status": "ok"}


@app.get("/api/chats/test-chats")
def api_get_test_chats(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    """Restituisce l'elenco delle chat generate dai test automatici per permetterne la selezione e rimozione."""
    chats = db.get_test_chats()
    return {
        "count": len(chats),
        "test_chats": chats,
    }


@app.post("/api/chats/cleanup-tests")
def api_cleanup_test_chats(req: CleanupTestChatsRequest, _auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    """Elimina in blocco le sole chat di test selezionate, solo previa conferma esplicita dell'utente."""
    if not req.confirmed:
        raise HTTPException(status_code=400, detail="Conferma esplicita richiesta (confirmed=true).")
    deleted = db.delete_test_chats(req.chat_ids)
    return {
        "status": "ok",
        "deleted_count": deleted,
        "remaining_chats_count": len(db.get_all_chats()),
    }


@app.get("/api/settings")
def api_get_settings(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    masked_key = ""
    if orchestrator.api_key:
        masked_key = orchestrator.api_key[:6] + "..." + orchestrator.api_key[-4:]
    masked_token = AUTH_TOKEN[:6] + "..." + AUTH_TOKEN[-4:]
    return {
        "has_api_key": bool(orchestrator.api_key),
        "masked_key": masked_key,
        "auth_token_configured": True,
        "masked_token": masked_token,
        "workspace_root": str(tools_os.PROJECT_ROOT),
    }


@app.post("/api/settings/apikey")
def api_set_apikey(req: ApiKeyRequest, _auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    clean_key = req.get_key()
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"GEMINI_API_KEY={clean_key}\n", encoding="utf-8")
    else:
        set_key(str(ENV_PATH), "GEMINI_API_KEY", clean_key)
    ok = orchestrator.reload_client(clean_key)
    return {"status": "ok" if ok else "error", "has_api_key": ok}


@app.post("/api/settings/reset")
def api_reset_settings(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    db.reset_db()
    return {"status": "ok", "message": "Database e attività resettati con successo."}


@app.get("/api/os/screenshot")
async def api_os_screenshot(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    return await asyncio.to_thread(tools_os.capture_screen_b64)


@app.get("/api/os/windows")
async def api_os_windows(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    return await asyncio.to_thread(tools_os.list_open_windows)


# ENDPOINTS APPROVAZIONI E AUDIT ATTIVITÀ (HARDENING FASE 1)

@app.get("/api/approvals/pending")
def api_get_pending_approvals(
    chat_id: Optional[str] = None,
    _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    """Elenca le azioni in stato 'waiting_approval' in attesa di conferma utente."""
    return {"status": "ok", "approvals": db.get_pending_approvals(chat_id)}


@app.post("/api/approvals/{approval_id}/approve")
async def api_approve_action(
    approval_id: str,
    _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    """Autorizza ed esegue nel backend l'azione in sospeso."""
    res = await orchestrator.execute_approved_action(
        approval_id=approval_id,
        approved=True,
        broadcast_fn=manager.broadcast,
    )
    if res.get("status") != "ok":
        raise HTTPException(status_code=400, detail=res.get("message", "Errore esecuzione approvazione"))
    return res


@app.post("/api/approvals/{approval_id}/reject")
async def api_reject_action(
    approval_id: str,
    _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    """Rifiuta ed annulla l'azione in sospeso."""
    res = await orchestrator.execute_approved_action(
        approval_id=approval_id,
        approved=False,
        broadcast_fn=manager.broadcast,
    )
    return res


@app.get("/api/activities")
def api_get_activities(
    chat_id: Optional[str] = None,
    limit: int = 50,
    _auth: str = Depends(verify_auth)
) -> Dict[str, Any]:
    """Audit trail delle attività degli agenti e degli strumenti invocati."""
    return {"status": "ok", "activities": db.get_activities(chat_id, limit)}


# ENDPOINTS TASK ENGINE PERSISTENTE (FASE 2A)

@app.get("/api/tasks")
def api_get_tasks(
    chat_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Elenca i task persistenti (con filtro opzionale per chat e stato)."""
    return {"status": "ok", "tasks": db.get_tasks(chat_id=chat_id, status=status, limit=limit)}


@app.get("/api/tasks/{task_id}")
def api_get_task(
    task_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Recupera i dettagli di un singolo task persistente."""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task non trovato")
    return {"status": "ok", "task": task}


@app.post("/api/tasks/{task_id}/resume")
async def api_resume_task(
    task_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Riprende in modo sicuro l'esecuzione di un task interrotto o fallito."""
    res = await orchestrator.resume_task(task_id=task_id, broadcast_fn=manager.broadcast)
    if res.get("status") not in ("ok", "success"):
        raise HTTPException(status_code=400, detail=res.get("message", "Impossibile riprendere il task"))
    return res


@app.post("/api/tasks/{task_id}/cancel")
def api_cancel_task(
    task_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Annulla un task persistente."""
    ok = db.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Impossibile annullare il task o task già terminato")
    task = db.get_task(task_id)
    return {"status": "ok", "task": task}


# ENDPOINTS MEMORIA PERSISTENTE STRUTTURATA (FASE 2B)

@app.get("/api/memories")
def api_get_memories(
    q: Optional[str] = None,
    project_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    scope: Optional[str] = None,
    limit: int = 50,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Recupera o cerca memorie tramite ranking ibrido (FTS5 + semantica locale)."""
    if q and q.strip():
        results = memory_manager.search_memories(
            query=q.strip(),
            project_id=project_id,
            scope=scope,
            limit=limit,
        )
    else:
        results = db.get_memories(
            project_id=project_id,
            memory_type=memory_type,
            status="active",
            scope=scope,
            limit=limit,
        )
    return {"status": "ok", "memories": results}


@app.post("/api/memories")
def api_create_memory(
    req: CreateMemoryRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Crea una nuova memoria persistente con validazione privacy e segreti."""
    try:
        mem = memory_manager.add_memory(
            content=req.content,
            memory_type=req.memory_type,
            project_id=req.project_id,
            provenance_type=req.provenance_type,
            provenance_id=req.provenance_id,
            confidence=req.confidence,
            scope=req.scope,
            owner_bot_id=req.owner_bot_id,
            metadata=req.metadata,
        )
        return {"status": "ok", "memory": mem}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.get("/api/memories/settings")
def api_get_memory_settings(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    """Recupera le impostazioni di memorizzazione."""
    return {"status": "ok", "settings": db.get_memory_settings()}


@app.post("/api/memories/settings")
def api_save_memory_settings(
    req: MemorySettingsRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Salva le impostazioni di memorizzazione (abilitazione automatica, budget contesto)."""
    if req.auto_memory_enabled is not None:
        db.save_memory_setting("auto_memory_enabled", req.auto_memory_enabled)
    if req.max_context_budget is not None:
        db.save_memory_setting("max_context_budget", req.max_context_budget)
    return {"status": "ok", "settings": db.get_memory_settings()}


@app.get("/api/memories/{memory_id}")
def api_get_memory(
    memory_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Recupera una singola memoria per ID."""
    mem = db.get_memory(memory_id)
    if not mem or mem.get("status") == "deleted":
        raise HTTPException(status_code=404, detail="Memoria non trovata")
    return {"status": "ok", "memory": mem}


@app.put("/api/memories/{memory_id}")
def api_update_memory(
    memory_id: str,
    req: UpdateMemoryRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Modifica una memoria esistente."""
    try:
        updated = memory_manager.update_memory(
            memory_id=memory_id,
            content=req.content,
            confidence=req.confidence,
            status=req.status,
            metadata=req.metadata,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Memoria non trovata")
        return {"status": "ok", "memory": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@app.delete("/api/memories/{memory_id}")
def api_delete_memory(
    memory_id: str,
    hard: bool = False,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    """Elimina una memoria e la rimuove dagli indici di ricerca."""
    ok = memory_manager.delete_memory(memory_id=memory_id, hard_delete=hard)
    if not ok:
        raise HTTPException(status_code=404, detail="Impossibile eliminare la memoria")
    return {"status": "ok", "message": "Memoria eliminata con successo"}


# --- FASE 2C: SCHEDULER & ATTIVITÀ PROGRAMMATE ---

@app.get("/api/scheduler/jobs")
def api_get_scheduled_jobs(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    _auth: str = Depends(verify_auth),
) -> List[Dict[str, Any]]:
    return db.get_scheduled_jobs(project_id=project_id, status=status)


@app.post("/api/scheduler/jobs")
def api_create_scheduled_job(
    req: CreateScheduledJobRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    job = scheduler_service.schedule_job(
        name=req.name,
        prompt=req.prompt,
        schedule_type=req.schedule_type,
        schedule_config=req.schedule_config,
        chat_id=req.chat_id,
        target_bot_id=req.target_bot_id,
        project_id=req.project_id,
        timezone_name=req.timezone,
        missed_job_policy=req.missed_job_policy,
        description=req.description,
    )
    return {"status": "ok", "job": job}


@app.get("/api/scheduler/jobs/{job_id}")
def api_get_scheduled_job(
    job_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    job = db.get_scheduled_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Attività programmata non trovata")
    return job


@app.put("/api/scheduler/jobs/{job_id}")
def api_update_scheduled_job(
    job_id: str,
    req: UpdateScheduledJobRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    job = db.get_scheduled_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Attività programmata non trovata")

    if req.status == "active" and job.get("status") == "paused":
        updated = scheduler_service.resume_job(job_id)
    elif req.status == "paused":
        updated = scheduler_service.pause_job(job_id)
    else:
        updated = db.update_scheduled_job(
            job_id=job_id,
            name=req.name,
            prompt=req.prompt,
            schedule_type=req.schedule_type,
            schedule_config=req.schedule_config,
            timezone=req.timezone,
            status=req.status,
            missed_job_policy=req.missed_job_policy,
            description=req.description,
        )
    return {"status": "ok", "job": updated}


@app.delete("/api/scheduler/jobs/{job_id}")
def api_delete_scheduled_job(
    job_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    ok = scheduler_service.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Impossibile eliminare l'attività")
    return {"status": "ok", "message": "Attività programmata eliminata con successo"}


@app.post("/api/scheduler/jobs/{job_id}/run-now")
async def api_run_scheduled_job_now(
    job_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    job = db.get_scheduled_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Attività programmata non trovata")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    exec_rec = db.create_job_execution(job_id=job_id, scheduled_for=now_iso, status="running")
    asyncio.create_task(scheduler_service._execute_job_instance(job, exec_rec["id"], now_iso))
    return {"status": "ok", "message": "Esecuzione avviata", "execution_id": exec_rec["id"]}


@app.get("/api/scheduler/jobs/{job_id}/history")
def api_get_job_history(
    job_id: str,
    limit: int = 50,
    _auth: str = Depends(verify_auth),
) -> List[Dict[str, Any]]:
    return db.get_job_executions(job_id=job_id, limit=limit)


@app.get("/api/scheduler/history")
def api_get_all_scheduler_history(
    limit: int = 50,
    _auth: str = Depends(verify_auth),
) -> List[Dict[str, Any]]:
    return db.get_job_executions(job_id=None, limit=limit)


# --- FASE 2C: CONSUMI E QUOTE ---

@app.get("/api/usage/summary")
def api_get_usage_summary(
    days: int = 1,
    chat_id: Optional[str] = None,
    task_id: Optional[str] = None,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    return db.get_usage_summary(days=days, chat_id=chat_id, task_id=task_id)


@app.get("/api/usage/limits")
def api_get_usage_limits(
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    return db.get_usage_limits()


@app.post("/api/usage/limits")
def api_save_usage_limit(
    req: SaveUsageLimitRequest,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    db.save_usage_limit(req.key, req.value)
    return {"status": "ok", "limits": db.get_usage_limits()}


# --- FASE 2C: NOTIFICHE LOCALI ---

@app.get("/api/notifications")
def api_get_notifications(
    limit: int = 50,
    unread_only: bool = False,
    _auth: str = Depends(verify_auth),
) -> List[Dict[str, Any]]:
    return notification_manager.get_notifications(limit=limit, unread_only=unread_only)


@app.post("/api/notifications/{notification_id}/read")
def api_mark_notification_read(
    notification_id: str,
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    ok = notification_manager.mark_read(notification_id)
    return {"status": "ok", "marked": ok}


@app.post("/api/notifications/read-all")
def api_mark_all_notifications_read(
    _auth: str = Depends(verify_auth),
) -> Dict[str, Any]:
    count = notification_manager.mark_all_read()
    return {"status": "ok", "marked_count": count}


@app.post("/api/auth/ws-ticket")
def api_create_ws_ticket(_auth: str = Depends(verify_auth)) -> Dict[str, Any]:
    """Genera un ticket effimero monouso (validità 15s) per handshake WebSocket."""
    ticket = create_ws_ticket()
    return {"status": "ok", "ticket": ticket, "expires_in": 15}


# WEBSOCKET PROTETTO (Header handshake o ticket effimero monouso)

@app.websocket("/ws/{chat_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    chat_id: str,
    ticket: Optional[str] = Query(None),
) -> None:
    # 1. Verifica header handshake (Authorization: Bearer o X-CoworkerOS-Token iniettati da Electron)
    auth_hdr = websocket.headers.get("authorization") or websocket.headers.get("x-coworkeros-token")
    token_candidate = None
    if auth_hdr and auth_hdr.startswith("Bearer "):
        token_candidate = auth_hdr.split(" ", 1)[1]
    elif auth_hdr:
        token_candidate = auth_hdr

    is_authenticated = verify_auth_token_value(token_candidate)

    # 2. Se privo di header, verifica se è presente un ticket effimero monouso valido
    if not is_authenticated and ticket:
        is_authenticated = consume_ws_ticket(ticket)

    # NOTA: il token persistente 'token=' non è più supportato negli URL
    if not is_authenticated:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

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
