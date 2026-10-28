"""
CoworkerOS SQLite Database Layer
Handles bots, chats, messages, and initial seeding.
"""

from __future__ import annotations

import re
import json
import os
import hashlib
from pathlib import Path
import sqlite3
import time
from typing import Any, List, Dict, Optional
import uuid

def get_db_path() -> Path:
    custom = os.getenv("COWORKEROS_DB_PATH")

    if custom:
        return Path(custom).expanduser().resolve()

    if os.getenv("COWORKEROS_TEST_MODE") == "1":
        raise RuntimeError(
            "Test senza database isolato: "
            "COWORKEROS_DB_PATH obbligatorio."
        )

    return Path(__file__).parent / "coworkers.db"

def set_db_path(path: str | Path) -> None:
    """Imposta a runtime il percorso del database per i test."""
    os.environ["COWORKEROS_DB_PATH"] = str(Path(path).resolve())

DB_PATH = get_db_path()

DEFAULT_BOTS = [
    {
        "id": "chief",
        "name": "Chief",
        "role": "Coordinator & Chief of Staff",
        "system_prompt": (
            "Sei Chief. Analizzi le richieste dell utente, pianifichi il lavoro, consulti email e calendario in sola lettura, e usi il tool "
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
            "Sei Scout. Esegui ricerche web approfondite, consulti email e calendario in sola lettura, raccogli documentazione e analizzi fonti esterne "
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
    db_file = get_db_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-20000;")
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
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    provenance TEXT NOT NULL DEFAULT 'user'
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS activities (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    chat_id TEXT NOT NULL,
                    bot_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_args_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error_msg TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    activity_id TEXT,
                    task_id TEXT,
                    chat_id TEXT NOT NULL,
                    bot_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    parent_task_id TEXT,
                    bot_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    instruction TEXT NOT NULL,
                    dependencies_json TEXT DEFAULT '[]',
                    status TEXT NOT NULL,
                    result_json TEXT,
                    evidence_json TEXT,
                    error_msg TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 2,
                    idempotency_key TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME,
                    completed_at DATETIME,
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                    FOREIGN KEY(parent_task_id) REFERENCES tasks(id) ON DELETE SET NULL
                );
                """
            )
            # Migrazione sicura colonne esistenti se il DB esiste già
            cursor = conn.execute("PRAGMA table_info(approvals);")
            approval_cols = [row["name"] for row in cursor.fetchall()]
            if "task_id" not in approval_cols:
                conn.execute("ALTER TABLE approvals ADD COLUMN task_id TEXT;")

            cursor = conn.execute("PRAGMA table_info(activities);")
            act_cols = [row["name"] for row in cursor.fetchall()]
            if "task_id" not in act_cols:
                conn.execute("ALTER TABLE activities ADD COLUMN task_id TEXT;")

            # Migrazione sicura provenienza chat (user vs test) con backup preventivo coerente
            cursor = conn.execute("PRAGMA table_info(chats);")
            chat_cols = [row["name"] for row in cursor.fetchall()]
            if "provenance" not in chat_cols:
                db_file = get_db_path()
                if db_file.exists() and db_file.is_file():
                    bak_file = db_file.with_name(f"{db_file.stem}_backup_{int(time.time())}.db")
                    try:
                        with sqlite3.connect(bak_file) as bck:
                            conn.backup(bck)
                    except Exception as e:
                        print(f"[DB] Backup SQLite prima della migrazione chats fallito: {e}")
                conn.execute("ALTER TABLE chats ADD COLUMN provenance TEXT NOT NULL DEFAULT 'user';")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chats_provenance ON chats(provenance);"
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_activities_chat_status ON activities(chat_id, status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_task_id ON approvals(task_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_chat_status ON tasks(chat_id, status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_idempotency ON tasks(idempotency_key);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);"
            )

            # SCHEMA MEMORIA PERSISTENTE STRUTTURATA (FASE 2B)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    project_id TEXT DEFAULT 'default',
                    provenance_type TEXT NOT NULL,
                    provenance_id TEXT,
                    confidence REAL DEFAULT 1.0,
                    status TEXT DEFAULT 'active',
                    scope TEXT DEFAULT 'global',
                    owner_bot_id TEXT,
                    metadata_json TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_project_status ON memories(project_id, status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);"
            )

            # Tabella virtuale FTS5 per ricerca full-text rapida (bm25)
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    id UNINDEXED,
                    content,
                    memory_type,
                    project_id,
                    scope
                );
                """
            )
            # Triggers di sincronizzazione atomica tra memories e memories_fts
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_after_insert AFTER INSERT ON memories
                WHEN new.status != 'deleted'
                BEGIN
                    INSERT INTO memories_fts(id, content, memory_type, project_id, scope)
                    VALUES (new.id, new.content, new.memory_type, new.project_id, new.scope);
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_after_delete AFTER DELETE ON memories
                BEGIN
                    DELETE FROM memories_fts WHERE id = old.id;
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_after_update AFTER UPDATE ON memories
                BEGIN
                    DELETE FROM memories_fts WHERE id = old.id;
                    INSERT INTO memories_fts(id, content, memory_type, project_id, scope)
                    SELECT new.id, new.content, new.memory_type, new.project_id, new.scope
                    WHERE new.status != 'deleted';
                END;
                """
            )

            # SCHEMA AUTONOMIA PROGRAMMATA & CONTROLLO CONSUMI (FASE 2C)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    prompt TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL DEFAULT 'chief',
                    chat_id TEXT NOT NULL,
                    project_id TEXT DEFAULT 'default',
                    schedule_type TEXT NOT NULL,
                    schedule_config_json TEXT NOT NULL,
                    timezone TEXT DEFAULT 'UTC',
                    status TEXT NOT NULL DEFAULT 'active',
                    next_run_at DATETIME,
                    last_run_at DATETIME,
                    missed_job_policy TEXT DEFAULT 'skip',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_executions (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    scheduled_for DATETIME NOT NULL,
                    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    task_id TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    duration_ms INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(job_id) REFERENCES scheduled_jobs(id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_records (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model_name TEXT NOT NULL,
                    task_id TEXT,
                    chat_id TEXT,
                    job_id TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    estimated_cost_usd REAL DEFAULT 0.0,
                    is_estimated INTEGER DEFAULT 1,
                    duration_ms INTEGER DEFAULT 0,
                    time_to_first_chunk_ms INTEGER
                );
                """
            )
            cursor = conn.execute("PRAGMA table_info(usage_records);")
            usage_cols = [row["name"] for row in cursor.fetchall()]
            if "time_to_first_chunk_ms" not in usage_cols:
                conn.execute("ALTER TABLE usage_records ADD COLUMN time_to_first_chunk_ms INTEGER;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_limits (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    related_id TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status_next ON scheduled_jobs(status, next_run_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_executions_job_executed ON job_executions(job_id, executed_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_usage_records_timestamp ON usage_records(timestamp);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_usage_records_task_id ON usage_records(task_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notifications_unread ON notifications(is_read, created_at);"
            )
            # Indici per ottimizzazione query WHERE frequenti (chat_id, task_id, status, bot_id, next_run)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_bot_id ON tasks(bot_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_chat_id ON approvals(chat_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_bot_id ON approvals(bot_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_task_id ON activities(task_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_bot_id ON activities(bot_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_records_chat_id ON usage_records(chat_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_chat_id ON scheduled_jobs(chat_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next_run_at ON scheduled_jobs(next_run_at);")
    finally:
        conn.close()


def seed_db() -> None:
    """Inizializza gli agenti, senza creare conversazioni."""
    conn = get_connection()
    try:
        with conn:
            for bot in DEFAULT_BOTS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO bots
                    (id, name, role, system_prompt, shape, color, effort)
                    VALUES
                    (:id, :name, :role, :system_prompt,
                     :shape, :color, :effort)
                    """,
                    bot,
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
            "SELECT id, title, is_group, participants_json, updated_at, provenance FROM chats ORDER BY updated_at DESC;"
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
            "SELECT id, title, is_group, participants_json, updated_at, provenance FROM chats WHERE id = ?;",
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
    provenance: str | None = None,
) -> dict[str, Any]:
    """Creates a new chat and returns its details."""
    if not chat_id:
        chat_id = f"chat_{uuid.uuid4().hex[:12]}"
    if provenance is None:
        provenance = "test" if os.getenv("COWORKEROS_TEST_MODE") == "1" else "user"
    participants_json = json.dumps(participants)
    is_group_int = 1 if is_group else 0

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO chats (id, title, is_group, participants_json, updated_at, provenance)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (chat_id, title, is_group_int, participants_json, provenance),
            )
            cursor = conn.execute(
                "SELECT id, title, is_group, participants_json, updated_at, provenance FROM chats WHERE id = ?;",
                (chat_id,),
            )
            row = cursor.fetchone()
            item = dict(row)
            item["participants"] = participants
            return item
    finally:
        conn.close()


def delete_chat(chat_id: str) -> bool:
    """Deletes a chat, its messages, tasks, activities and approvals completely."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM messages WHERE chat_id = ?;", (chat_id,))
            conn.execute("DELETE FROM tasks WHERE chat_id = ?;", (chat_id,))
            conn.execute("DELETE FROM activities WHERE chat_id = ?;", (chat_id,))
            conn.execute("DELETE FROM approvals WHERE chat_id = ?;", (chat_id,))
            cursor = conn.execute("DELETE FROM chats WHERE id = ?;", (chat_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_test_chats() -> List[Dict[str, Any]]:
    """
    Identifica le conversazioni esplicitamente marcate con provenance='test'.
    Non include MAI conversazioni personali dell'utente né si affida a regex sul titolo.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT id, title, is_group, participants_json, updated_at, provenance FROM chats WHERE provenance = 'test' ORDER BY updated_at DESC;"
        )
        test_chats = []
        for row in cursor.fetchall():
            cid = row["id"]
            cnt_cur = conn.execute("SELECT COUNT(*) as cnt FROM messages WHERE chat_id = ?;", (cid,))
            cnt_row = cnt_cur.fetchone()
            msg_count = cnt_row["cnt"] if cnt_row else 0
            try:
                participants = json.loads(row["participants_json"])
            except Exception:
                participants = []
            test_chats.append({
                "id": cid,
                "title": row["title"],
                "updated_at": row["updated_at"],
                "message_count": msg_count,
                "participants": participants,
                "provenance": row["provenance"],
            })
        return test_chats
    finally:
        conn.close()


def delete_test_chats(chat_ids: List[str]) -> int:
    """
    Elimina in blocco le conversazioni di test selezionate dall'utente.
    Elimina soltanto record esplicitamente marcati provenance='test'.
    """
    if not chat_ids:
        return 0

    valid_test_chats = get_test_chats()
    valid_test_ids = {c["id"] for c in valid_test_chats}

    target_ids = [cid for cid in chat_ids if cid in valid_test_ids]
    if not target_ids:
        return 0

    conn = get_connection()
    deleted_count = 0
    try:
        with conn:
            for cid in target_ids:
                conn.execute("DELETE FROM messages WHERE chat_id = ?;", (cid,))
                conn.execute("DELETE FROM tasks WHERE chat_id = ?;", (cid,))
                conn.execute("DELETE FROM activities WHERE chat_id = ?;", (cid,))
                conn.execute("DELETE FROM approvals WHERE chat_id = ?;", (cid,))
                cur = conn.execute("DELETE FROM chats WHERE id = ? AND provenance = 'test';", (cid,))
                if cur.rowcount > 0:
                    deleted_count += 1
    finally:
        conn.close()
    return deleted_count


def reset_db() -> None:
    """Wipes all chats, messages, tasks, activities and approvals; re-seeds default bots and clean individual chats."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM messages;")
            conn.execute("DELETE FROM chats;")
            conn.execute("DELETE FROM tasks;")
            conn.execute("DELETE FROM activities;")
            conn.execute("DELETE FROM approvals;")
            conn.execute("DELETE FROM memories;")
            conn.execute("DELETE FROM memories_fts;")
            conn.execute("DELETE FROM memory_settings;")
            conn.execute("DELETE FROM job_executions;")
            conn.execute("DELETE FROM scheduled_jobs;")
            conn.execute("DELETE FROM usage_records;")
            conn.execute("DELETE FROM usage_limits;")
            conn.execute("DELETE FROM notifications;")
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


def create_activity(
    chat_id: str,
    bot_id: str,
    tool_name: str,
    tool_args: dict[str, Any] | str,
    status: str = "pending",
    activity_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Records an explicit activity state: pending, running, waiting_approval, completed, failed."""
    if not activity_id:
        activity_id = f"act_{uuid.uuid4().hex[:12]}"
    args_json = json.dumps(tool_args) if isinstance(tool_args, dict) else str(tool_args)
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO activities (id, task_id, chat_id, bot_id, tool_name, tool_args_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (activity_id, task_id, chat_id, bot_id, tool_name, args_json, status),
            )
        return {
            "id": activity_id,
            "task_id": task_id,
            "chat_id": chat_id,
            "bot_id": bot_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "status": status,
        }
    finally:
        conn.close()


def update_activity(
    activity_id: str,
    status: str | None = None,
    result: Any | None = None,
    error_msg: str | None = None,
) -> dict[str, Any] | None:
    """Updates status, result, or error of an activity."""
    conn = get_connection()
    try:
        fields = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if result is not None:
            fields.append("result_json = ?")
            params.append(json.dumps(result) if not isinstance(result, str) else result)
        if error_msg is not None:
            fields.append("error_msg = ?")
            params.append(error_msg)
        params.append(activity_id)
        with conn:
            conn.execute(f"UPDATE activities SET {', '.join(fields)} WHERE id = ?;", params)
            cursor = conn.execute("SELECT * FROM activities WHERE id = ?;", (activity_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_activities(chat_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieves activities logged for audit and monitoring."""
    conn = get_connection()
    try:
        if chat_id:
            cursor = conn.execute(
                "SELECT * FROM activities WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?;",
                (chat_id, limit),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM activities ORDER BY created_at DESC LIMIT ?;",
                (limit,),
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def create_approval(
    chat_id: str,
    bot_id: str,
    action_type: str,
    description: str,
    payload: dict[str, Any] | str,
    activity_id: str | None = None,
    approval_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Registers an action requiring explicit user confirmation before backend execution."""
    if not approval_id:
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
    payload_json = json.dumps(payload) if isinstance(payload, dict) else str(payload)
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO approvals (id, activity_id, task_id, chat_id, bot_id, action_type, description, payload_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'waiting_approval', CURRENT_TIMESTAMP);
                """,
                (approval_id, activity_id, task_id, chat_id, bot_id, action_type, description, payload_json),
            )
        return {
            "id": approval_id,
            "activity_id": activity_id,
            "task_id": task_id,
            "chat_id": chat_id,
            "bot_id": bot_id,
            "action_type": action_type,
            "description": description,
            "payload": payload,
            "status": "waiting_approval",
        }
    finally:
        conn.close()


def get_approval(approval_id: str) -> dict[str, Any] | None:
    """Retrieves a single approval by ID."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM approvals WHERE id = ?;", (approval_id,))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item["payload_json"])
        except Exception:
            item["payload"] = item["payload_json"]
        return item
    finally:
        conn.close()


def get_pending_approvals(chat_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieves all approvals in waiting_approval status."""
    conn = get_connection()
    try:
        if chat_id:
            cursor = conn.execute(
                "SELECT * FROM approvals WHERE chat_id = ? AND status = 'waiting_approval' ORDER BY created_at ASC;",
                (chat_id,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM approvals WHERE status = 'waiting_approval' ORDER BY created_at ASC;"
            )
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            try:
                item["payload"] = json.loads(item["payload_json"])
            except Exception:
                item["payload"] = item["payload_json"]
            results.append(item)
        return results
    finally:
        conn.close()


def resolve_approval_atomic(
    approval_id: str,
    new_status: str,
    expected_status: str = "waiting_approval",
) -> tuple[bool, dict[str, Any] | None]:
    """
    Transizione atomica SQLite dello stato approvazione.
    Aggiorna lo stato SOLO SE lo stato corrente corrisponde esattamente a expected_status ('waiting_approval').
    Verifica il numero di righe modificate (cursor.rowcount == 1).
    Ritorna (True, record) se la transizione ha avuto successo; (False, record_attuale) se già risolta o fallita.
    """
    if new_status not in ("approved", "rejected", "expired"):
        raise ValueError(f"Invalid approval status: {new_status}")
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                """
                UPDATE approvals
                SET status = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = ?;
                """,
                (new_status, approval_id, expected_status),
            )
            success = (cursor.rowcount == 1)
        current_record = get_approval(approval_id)
        return success, current_record
    finally:
        conn.close()


def resolve_approval(approval_id: str, new_status: str) -> dict[str, Any] | None:
    """Wrapper di retrocompatibilità che chiama la transizione atomica."""
    _, record = resolve_approval_atomic(approval_id, new_status, expected_status="waiting_approval")
    return record


# ============================================================================
# TASK ENGINE PERSISTENTE (FASE 2A)
# ============================================================================

def _format_task_row(item: dict[str, Any]) -> dict[str, Any]:
    """Deserializza i campi JSON del task in strutture Python."""
    for json_col in ("dependencies_json", "result_json", "evidence_json"):
        val = item.get(json_col)
        key_clean = json_col.replace("_json", "")
        if val:
            try:
                item[key_clean] = json.loads(val)
            except Exception:
                item[key_clean] = val
        else:
            item[key_clean] = [] if json_col == "dependencies_json" else None
    item["result_data"] = item.get("result")
    return item


def create_task(
    chat_id: str,
    bot_id: str,
    title: str,
    goal: str = "",
    instruction: str = "",
    parent_task_id: str | None = None,
    dependencies: list[str] | None = None,
    idempotency_key: str | None = None,
    max_retries: int = 2,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Crea un task persistente su SQLite. Supporta idempotenza deterministica."""
    conn = get_connection()
    try:
        if idempotency_key:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE idempotency_key = ?;",
                (idempotency_key,)
            )
            row = cursor.fetchone()
            if row:
                return _format_task_row(dict(row))

        if not task_id:
            task_id = f"task_{uuid.uuid4().hex[:12]}"

        deps_json = json.dumps(dependencies or [])
        status = "pending"

        with conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, chat_id, parent_task_id, bot_id, title, goal, instruction,
                    dependencies_json, status, retry_count, max_retries, idempotency_key,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (task_id, chat_id, parent_task_id, bot_id, title, goal, instruction,
                 deps_json, status, max_retries, idempotency_key),
            )
        return get_task(task_id) or {
            "id": task_id,
            "chat_id": chat_id,
            "bot_id": bot_id,
            "title": title,
            "goal": goal,
            "instruction": instruction,
            "parent_task_id": parent_task_id,
            "dependencies": dependencies or [],
            "status": status,
        }
    finally:
        conn.close()


def get_task(task_id: str) -> dict[str, Any] | None:
    """Recupera un task persistente per ID, includendo le approvazioni collegate."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        task = _format_task_row(dict(row))
        cur_appr = conn.execute(
            "SELECT id, action_type, description, status FROM approvals WHERE task_id = ? ORDER BY created_at ASC;",
            (task_id,)
        )
        task["approvals"] = [dict(r) for r in cur_appr.fetchall()]
        return task
    finally:
        conn.close()


def get_tasks(chat_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Recupera i task persistenti per chat e/o stato."""
    conn = get_connection()
    try:
        query = "SELECT * FROM tasks"
        clauses = []
        params = []
        if chat_id:
            clauses.append("chat_id = ?")
            params.append(chat_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at ASC LIMIT ?;"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [_format_task_row(dict(r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_task_status_atomic(
    task_id: str,
    new_status: str | None = None,
    expected_status: str | None = None,
    result: Any | None = None,
    evidence: Any | None = None,
    error_msg: str | None = None,
    increment_retry: bool = False,
    to_status: str | None = None,
    from_status: str | None = None,
    result_data: Any | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """
    Transizione atomica di stato per un task.
    Se expected_status e' specificato, aggiorna solo se lo stato attuale corrisponde.
    """
    if to_status is not None and new_status is None:
        new_status = to_status
    if from_status is not None and expected_status is None:
        expected_status = from_status
    if result_data is not None and result is None:
        result = result_data

    valid_statuses = ("pending", "running", "delegated", "waiting_approval", "completed", "failed", "cancelled", "interrupted")
    if new_status not in valid_statuses:
        raise ValueError(f"Stato task non valido: {new_status}")

    conn = get_connection()
    try:
        fields = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        params = [new_status]

        if new_status == "running":
            fields.append("started_at = COALESCE(started_at, CURRENT_TIMESTAMP)")
        elif new_status in ("completed", "failed", "cancelled"):
            fields.append("completed_at = CURRENT_TIMESTAMP")

        if result is not None:
            fields.append("result_json = ?")
            params.append(json.dumps(result) if not isinstance(result, str) else result)
        if evidence is not None:
            fields.append("evidence_json = ?")
            params.append(json.dumps(evidence) if not isinstance(evidence, str) else evidence)
        if error_msg is not None:
            fields.append("error_msg = ?")
            params.append(error_msg)
        if increment_retry:
            fields.append("retry_count = retry_count + 1")

        query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?"
        params.append(task_id)
        if expected_status:
            query += " AND status = ?"
            params.append(expected_status)
        query += ";"

        with conn:
            cursor = conn.execute(query, params)
            success = (cursor.rowcount == 1)

        updated_task = get_task(task_id)
        return success, updated_task
    finally:
        conn.close()


def get_ready_tasks(chat_id: str) -> list[dict[str, Any]]:
    """
    Restituisce tutti i task in stato 'pending' le cui dipendenze sono tutte 'completed'.
    """
    all_pending = get_tasks(chat_id=chat_id, status="pending")
    ready = []
    conn = get_connection()
    try:
        for t in all_pending:
            deps = t.get("dependencies", [])
            if not deps:
                ready.append(t)
                continue
            placeholders = ",".join(["?"] * len(deps))
            cursor = conn.execute(
                f"SELECT COUNT(*) as count FROM tasks WHERE id IN ({placeholders}) AND status = 'completed';",
                deps
            )
            completed_count = cursor.fetchone()["count"]
            if completed_count == len(deps):
                ready.append(t)
        return ready
    finally:
        conn.close()


def recover_interrupted_tasks() -> list[dict[str, Any]]:
    """
    All'avvio/riavvio, identifica tutti i task rimasti in 'running' e li imposta su 'interrupted'.
    Non ripete automaticamente operazioni non idempotenti e preserva lo stato per verifica manuale.
    """
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("SELECT id FROM tasks WHERE status = 'running';")
            interrupted_ids = [row["id"] for row in cursor.fetchall()]
            if interrupted_ids:
                placeholders = ",".join(["?"] * len(interrupted_ids))
                conn.execute(
                    f"""
                    UPDATE tasks
                    SET status = 'interrupted',
                        error_msg = 'Interruzione di sistema / riavvio rilevato. Azione non idempotente bloccata.',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders});
                    """,
                    interrupted_ids,
                )
        recovered = []
        for tid in interrupted_ids:
            t = get_task(tid)
            if t:
                recovered.append(t)
        return recovered
    finally:
        conn.close()


def cancel_task(task_id: str) -> dict[str, Any] | None:
    """Annulla un task e tutte le sue approvazioni in sospeso."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'cancelled',
                    error_msg = 'Annullato dall\\'utente o dal sistema',
                    completed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (task_id,),
            )
            conn.execute(
                """
                UPDATE approvals
                SET status = 'expired',
                    resolved_at = CURRENT_TIMESTAMP
                WHERE task_id = ? AND status = 'waiting_approval';
                """,
                (task_id,),
            )
        return get_task(task_id)
    finally:
        conn.close()


# ============================================================================
# MEMORIA PERSISTENTE STRUTTURATA (FASE 2B)
# ============================================================================

def _format_memory_row(item: dict[str, Any]) -> dict[str, Any]:
    """Deserializza i metadati JSON della memoria."""
    raw = item.get("metadata_json")
    if raw:
        try:
            item["metadata"] = json.loads(raw)
        except Exception:
            item["metadata"] = {}
    else:
        item["metadata"] = {}
    return item


def _sanitize_fts_query(q: str) -> str:
    """Sanitizza e prepara la query FTS5 per evitare errori di sintassi su caratteri speciali."""
    tokens = re.findall(r"[\w]+", q, re.UNICODE)
    if not tokens:
        return ""
    return " ".join(f'"{t}"*' for t in tokens)


def save_memory(
    memory_type: str,
    content: str,
    project_id: str = "default",
    provenance_type: str = "manual",
    provenance_id: str | None = None,
    confidence: float = 1.0,
    status: str = "active",
    scope: str = "global",
    owner_bot_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    memory_id: str | None = None,
) -> dict[str, Any]:
    """Salva una memoria persistente strutturata."""
    if not memory_id:
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
    meta_json = json.dumps(metadata or {})
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, memory_type, content, project_id, provenance_type, provenance_id,
                    confidence, status, scope, owner_bot_id, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    memory_id, memory_type, content.strip(), project_id, provenance_type,
                    provenance_id, confidence, status, scope, owner_bot_id, meta_json
                ),
            )
        return get_memory(memory_id) or {
            "id": memory_id,
            "memory_type": memory_type,
            "content": content.strip(),
            "project_id": project_id,
            "confidence": confidence,
            "status": status,
            "scope": scope,
        }
    finally:
        conn.close()


def get_memory(memory_id: str) -> dict[str, Any] | None:
    """Recupera una memoria per ID."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT * FROM memories WHERE id = ?;", (memory_id,))
        row = cursor.fetchone()
        return _format_memory_row(dict(row)) if row else None
    finally:
        conn.close()


def get_memories(
    project_id: str | None = None,
    memory_type: str | None = None,
    status: str = "active",
    scope: str | None = None,
    owner_bot_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Elenca le memorie con filtri opzionali su progetto, tipo, stato e visibilità."""
    conn = get_connection()
    try:
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if project_id:
            query += " AND (project_id = ? OR scope = 'global')"
            params.append(project_id)
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        if owner_bot_id:
            query += " AND (owner_bot_id IS NULL OR owner_bot_id = ?)"
            params.append(owner_bot_id)

        query += " ORDER BY updated_at DESC, confidence DESC LIMIT ?;"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [_format_memory_row(dict(r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def search_memories_fts(
    query_str: str,
    project_id: str | None = None,
    scope: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Ricerca full-text nativa FTS5 con ranking bm25."""
    clean_fts = _sanitize_fts_query(query_str)
    if not clean_fts:
        return []

    conn = get_connection()
    try:
        query = """
            SELECT m.*, bm25(memories_fts) as bm25_score
            FROM memories_fts fts
            JOIN memories m ON m.id = fts.id
            WHERE memories_fts MATCH ?
              AND m.status = 'active'
        """
        params: list[Any] = [clean_fts]
        if project_id:
            query += " AND (m.project_id = ? OR m.scope = 'global')"
            params.append(project_id)
        if scope:
            query += " AND m.scope = ?"
            params.append(scope)

        query += " ORDER BY bm25_score ASC LIMIT ?;"
        params.append(limit)

        cursor = conn.execute(query, params)
        return [_format_memory_row(dict(r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_memory(
    memory_id: str,
    content: str | None = None,
    confidence: float | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    project_id: str | None = None,
    scope: str | None = None,
) -> dict[str, Any] | None:
    """Aggiorna i campi di una memoria esistente."""
    conn = get_connection()
    try:
        fields = ["updated_at = CURRENT_TIMESTAMP"]
        params = []
        if content is not None:
            fields.append("content = ?")
            params.append(content.strip())
        if confidence is not None:
            fields.append("confidence = ?")
            params.append(confidence)
        if status is not None:
            fields.append("status = ?")
            params.append(status)
        if metadata is not None:
            fields.append("metadata_json = ?")
            params.append(json.dumps(metadata))
        if project_id is not None:
            fields.append("project_id = ?")
            params.append(project_id)
        if scope is not None:
            fields.append("scope = ?")
            params.append(scope)

        query = f"UPDATE memories SET {', '.join(fields)} WHERE id = ?;"
        params.append(memory_id)

        with conn:
            conn.execute(query, params)
        return get_memory(memory_id)
    finally:
        conn.close()


def delete_memory(memory_id: str, hard_delete: bool = False) -> bool:
    """Elimina una memoria (soft delete o hard delete). Rimuove automaticamente da FTS5."""
    conn = get_connection()
    try:
        with conn:
            if hard_delete:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?;", (memory_id,))
                conn.execute("DELETE FROM memories_fts WHERE id = ?;", (memory_id,))
                return cursor.rowcount == 1
            else:
                cursor = conn.execute(
                    "UPDATE memories SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                    (memory_id,),
                )
                return cursor.rowcount == 1
    finally:
        conn.close()


def get_memory_settings() -> dict[str, Any]:
    """Recupera le impostazioni di memorizzazione."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT key, value_json FROM memory_settings;")
        res = {"auto_memory_enabled": True, "max_context_budget": 2500}
        for row in cursor.fetchall():
            try:
                res[row["key"]] = json.loads(row["value_json"])
            except Exception:
                res[row["key"]] = row["value_json"]
        return res
    finally:
        conn.close()


def save_memory_setting(key: str, value: Any) -> None:
    """Salva una singola impostazione di memorizzazione."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO memory_settings (key, value_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP;
                """,
                (key, json.dumps(value)),
            )
    finally:
        conn.close()


# ============================================================================
# FASE 2C: AUTONOMIA PROGRAMMATA, SCHEDULER, CONSUMI E NOTIFICHE
# ============================================================================

def _format_job_row(row: dict[str, Any]) -> dict[str, Any]:
    """Helper per formattare una riga scheduled_jobs."""
    item = dict(row)
    if item.get("schedule_config_json"):
        try:
            item["schedule_config"] = json.loads(item["schedule_config_json"])
        except Exception:
            item["schedule_config"] = {}
    else:
        item["schedule_config"] = {}
    return item


def create_scheduled_job(
    name: str,
    prompt: str,
    schedule_type: str,
    schedule_config: dict[str, Any],
    chat_id: str,
    target_bot_id: str = "chief",
    project_id: str = "default",
    timezone: str = "UTC",
    missed_job_policy: str = "skip",
    next_run_at: str | None = None,
    job_id: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Crea una nuova attività programmata nel database."""
    if not job_id:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
    config_json = json.dumps(schedule_config)

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO scheduled_jobs (
                    id, name, description, prompt, target_bot_id, chat_id, project_id,
                    schedule_type, schedule_config_json, timezone, status, next_run_at,
                    missed_job_policy, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    job_id,
                    name.strip(),
                    description.strip() if description else "",
                    prompt.strip(),
                    target_bot_id.strip(),
                    chat_id.strip(),
                    project_id.strip(),
                    schedule_type.strip(),
                    config_json,
                    timezone.strip(),
                    next_run_at,
                    missed_job_policy.strip(),
                ),
            )
        job = get_scheduled_job(job_id)
        if not job:
            raise RuntimeError(f"Impossibile creare il job {job_id}")
        return job
    finally:
        conn.close()


def get_scheduled_job(job_id: str) -> dict[str, Any] | None:
    """Recupera una singola attività programmata."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT id, name, description, prompt, target_bot_id, chat_id, project_id,
                   schedule_type, schedule_config_json, timezone, status, next_run_at,
                   last_run_at, missed_job_policy, created_at, updated_at
            FROM scheduled_jobs
            WHERE id = ?;
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        return _format_job_row(dict(row)) if row else None
    finally:
        conn.close()


def get_scheduled_jobs(
    project_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Elenca le attività programmate con filtri opzionali."""
    conn = get_connection()
    try:
        query = (
            "SELECT id, name, description, prompt, target_bot_id, chat_id, project_id, "
            "schedule_type, schedule_config_json, timezone, status, next_run_at, "
            "last_run_at, missed_job_policy, created_at, updated_at "
            "FROM scheduled_jobs WHERE 1=1"
        )
        params: list[Any] = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC;"

        cursor = conn.execute(query, params)
        return [_format_job_row(dict(r)) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_scheduled_job(
    job_id: str,
    name: str | None = None,
    description: str | None = None,
    prompt: str | None = None,
    target_bot_id: str | None = None,
    schedule_type: str | None = None,
    schedule_config: dict[str, Any] | None = None,
    timezone: str | None = None,
    status: str | None = None,
    next_run_at: str | None = None,
    last_run_at: str | None = None,
    missed_job_policy: str | None = None,
) -> dict[str, Any] | None:
    """Aggiorna campi specifici di un'attività programmata."""
    conn = get_connection()
    try:
        fields = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[Any] = []
        if name is not None:
            fields.append("name = ?")
            params.append(name.strip())
        if description is not None:
            fields.append("description = ?")
            params.append(description.strip())
        if prompt is not None:
            fields.append("prompt = ?")
            params.append(prompt.strip())
        if target_bot_id is not None:
            fields.append("target_bot_id = ?")
            params.append(target_bot_id.strip())
        if schedule_type is not None:
            fields.append("schedule_type = ?")
            params.append(schedule_type.strip())
        if schedule_config is not None:
            fields.append("schedule_config_json = ?")
            params.append(json.dumps(schedule_config))
        if timezone is not None:
            fields.append("timezone = ?")
            params.append(timezone.strip())
        if status is not None:
            fields.append("status = ?")
            params.append(status.strip())
        if next_run_at is not None:
            fields.append("next_run_at = ?")
            params.append(next_run_at)
        if last_run_at is not None:
            fields.append("last_run_at = ?")
            params.append(last_run_at)
        if missed_job_policy is not None:
            fields.append("missed_job_policy = ?")
            params.append(missed_job_policy.strip())

        query = f"UPDATE scheduled_jobs SET {', '.join(fields)} WHERE id = ?;"
        params.append(job_id)

        with conn:
            conn.execute(query, params)
        return get_scheduled_job(job_id)
    finally:
        conn.close()


def delete_scheduled_job(job_id: str) -> bool:
    """Elimina definitivamente un'attività programmata e le sue esecuzioni."""
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM scheduled_jobs WHERE id = ?;", (job_id,))
            return cursor.rowcount == 1
    finally:
        conn.close()


def reserve_job_for_execution_atomic(
    job_id: str,
    expected_next_run: str | None,
    new_next_run: str | None,
    new_status: str = "active",
) -> bool:
    """
    Prenota atomicamente un job per l'esecuzione, aggiornando next_run_at e last_run_at.
    Restituisce True solo se la riga è stata aggiornata esattamente da questa chiamata,
    prevenendo doppie esecuzioni concorrenti su SQLite.
    """
    conn = get_connection()
    try:
        with conn:
            if expected_next_run is None:
                cursor = conn.execute(
                    """
                    UPDATE scheduled_jobs
                    SET next_run_at = ?, last_run_at = CURRENT_TIMESTAMP, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'active' AND next_run_at IS NULL;
                    """,
                    (new_next_run, new_status, job_id),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE scheduled_jobs
                    SET next_run_at = ?, last_run_at = CURRENT_TIMESTAMP, status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'active' AND next_run_at = ?;
                    """,
                    (new_next_run, new_status, job_id, expected_next_run),
                )
            return cursor.rowcount == 1
    finally:
        conn.close()


def create_job_execution(
    job_id: str,
    scheduled_for: str,
    task_id: str | None = None,
    status: str = "running",
    error_message: str | None = None,
) -> dict[str, Any]:
    """Crea una riga nella cronologia delle esecuzioni."""
    exec_id = f"exec_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO job_executions (
                    id, job_id, scheduled_for, executed_at, task_id, status, error_message, duration_ms, created_at
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, 0, CURRENT_TIMESTAMP);
                """,
                (exec_id, job_id, scheduled_for, task_id, status, error_message),
            )
        return {
            "id": exec_id,
            "job_id": job_id,
            "scheduled_for": scheduled_for,
            "task_id": task_id,
            "status": status,
            "error_message": error_message,
            "duration_ms": 0,
        }
    finally:
        conn.close()


def update_job_execution(
    execution_id: str,
    status: str,
    error_message: str | None = None,
    duration_ms: int = 0,
    task_id: str | None = None,
) -> dict[str, Any] | None:
    """Aggiorna lo stato e i risultati di un'esecuzione registrata."""
    conn = get_connection()
    try:
        fields = ["status = ?", "duration_ms = ?"]
        params: list[Any] = [status, duration_ms]
        if error_message is not None:
            fields.append("error_message = ?")
            params.append(error_message)
        if task_id is not None:
            fields.append("task_id = ?")
            params.append(task_id)

        query = f"UPDATE job_executions SET {', '.join(fields)} WHERE id = ?;"
        params.append(execution_id)

        with conn:
            conn.execute(query, params)

        cursor = conn.execute("SELECT * FROM job_executions WHERE id = ?;", (execution_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job_executions(
    job_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Elenca le esecuzioni storiche."""
    conn = get_connection()
    try:
        if job_id:
            cursor = conn.execute(
                """
                SELECT id, job_id, scheduled_for, executed_at, task_id, status, error_message, duration_ms, created_at
                FROM job_executions
                WHERE job_id = ?
                ORDER BY executed_at DESC
                LIMIT ?;
                """,
                (job_id, limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, job_id, scheduled_for, executed_at, task_id, status, error_message, duration_ms, created_at
                FROM job_executions
                ORDER BY executed_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


# --- CONSUMI & QUOTE ---

def _calc_percentile(values: list[float | int], p: float) -> float | int | None:
    """Calcola il percentile (es. 50 o 95) su una lista di valori con interpolazione lineare."""
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    d = k - f
    return round(sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f]), 2)


def record_usage(
    model_name: str,
    task_id: str | None = None,
    chat_id: str | None = None,
    job_id: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float = 0.0,
    duration_ms: int = 0,
    time_to_first_chunk_ms: int | None = None,
    is_estimated: int = 1,
) -> dict[str, Any]:
    """Registra una transazione di utilizzo del modello (senza inventare token se non forniti)."""
    usage_id = f"usg_{uuid.uuid4().hex[:12]}"
    total_tokens = None
    if input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO usage_records (
                    id, timestamp, model_name, task_id, chat_id, job_id,
                    input_tokens, output_tokens, total_tokens, estimated_cost_usd,
                    is_estimated, duration_ms, time_to_first_chunk_ms
                ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    usage_id,
                    model_name,
                    task_id,
                    chat_id,
                    job_id,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd,
                    is_estimated,
                    duration_ms,
                    time_to_first_chunk_ms,
                ),
            )
        return {
            "id": usage_id,
            "model_name": model_name,
            "task_id": task_id,
            "chat_id": chat_id,
            "job_id": job_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "is_estimated": is_estimated,
            "duration_ms": duration_ms,
            "time_to_first_chunk_ms": time_to_first_chunk_ms,
        }
    finally:
        conn.close()


def get_usage_summary(
    days: int = 1,
    chat_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Calcola il riassunto consumi per giornata, task o chat."""
    conn = get_connection()
    try:
        # Conteggio richieste oggi
        cursor = conn.execute(
            """
            SELECT COUNT(*) AS req_count,
                   SUM(COALESCE(input_tokens, 0)) AS in_tokens,
                   SUM(COALESCE(output_tokens, 0)) AS out_tokens,
                   SUM(COALESCE(total_tokens, 0)) AS tot_tokens,
                   SUM(COALESCE(estimated_cost_usd, 0.0)) AS tot_cost
            FROM usage_records
            WHERE timestamp >= datetime('now', '-' || ? || ' day');
            """,
            (days,),
        )
        row = cursor.fetchone()
        tot_requests = (row["req_count"] or 0) if row else 0
        in_tokens = (row["in_tokens"] or 0) if row else 0
        out_tokens = (row["out_tokens"] or 0) if row else 0
        tot_tokens = (row["tot_tokens"] or 0) if row else 0
        tot_cost = float(row["tot_cost"] or 0.0) if row else 0.0

        # Raggruppamento per modello
        cursor_mod = conn.execute(
            """
            SELECT model_name, COUNT(*) AS count,
                   SUM(COALESCE(total_tokens, 0)) AS tokens,
                   SUM(COALESCE(estimated_cost_usd, 0.0)) AS cost
            FROM usage_records
            WHERE timestamp >= datetime('now', '-' || ? || ' day')
            GROUP BY model_name;
            """,
            (days,),
        )
        by_model = [dict(r) for r in cursor_mod.fetchall()]

        # Se richiesto per uno specifico task
        task_usage = None
        if task_id:
            cursor_task = conn.execute(
                """
                SELECT COUNT(*) AS count,
                       SUM(COALESCE(total_tokens, 0)) AS tokens,
                       SUM(COALESCE(estimated_cost_usd, 0.0)) AS cost
                FROM usage_records WHERE task_id = ?;
                """,
                (task_id,),
            )
            r_t = cursor_task.fetchone()
            task_usage = {
                "requests": r_t["count"] if r_t else 0,
                "tokens": r_t["tokens"] if r_t else 0,
                "cost": r_t["cost"] if r_t else 0.0,
            }

        # Calcolo latenze p50 e p95 di duration_ms e time_to_first_chunk_ms
        where_clauses = ["timestamp >= datetime('now', '-' || ? || ' day')"]
        query_params: list[Any] = [days]
        if chat_id:
            where_clauses.append("chat_id = ?")
            query_params.append(chat_id)
        if task_id:
            where_clauses.append("task_id = ?")
            query_params.append(task_id)

        where_sql = " AND ".join(where_clauses)
        cursor_lat = conn.execute(
            f"SELECT duration_ms, time_to_first_chunk_ms FROM usage_records WHERE {where_sql};",
            query_params,
        )
        lat_rows = cursor_lat.fetchall()
        durations = [r["duration_ms"] for r in lat_rows if r["duration_ms"] is not None]
        ttfc_list = [r["time_to_first_chunk_ms"] for r in lat_rows if r["time_to_first_chunk_ms"] is not None]

        p50_duration = _calc_percentile(durations, 50)
        p95_duration = _calc_percentile(durations, 95)
        p50_ttfc = _calc_percentile(ttfc_list, 50)
        p95_ttfc = _calc_percentile(ttfc_list, 95)

        return {
            "period_days": days,
            "requests_count": tot_requests,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": tot_tokens,
            "estimated_cost_usd": round(tot_cost, 6),
            "is_estimate_notice": "Stima puramente indicativa dei consumi, non costituisce fatturazione reale.",
            "by_model": by_model,
            "task_usage": task_usage,
            "duration_ms_p50": p50_duration,
            "duration_ms_p95": p95_duration,
            "time_to_first_chunk_ms_p50": p50_ttfc,
            "time_to_first_chunk_ms_p95": p95_ttfc,
            "latency": {
                "duration_ms": {"p50": p50_duration, "p95": p95_duration},
                "time_to_first_chunk_ms": {"p50": p50_ttfc, "p95": p95_ttfc},
            },
        }
    finally:
        conn.close()


def get_usage_limits() -> dict[str, Any]:
    """Recupera le quote e limiti configurati."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT key, value_json FROM usage_limits;")
        res = {
            "max_requests_per_task": 15,
            "max_requests_daily": 200,
            "max_concurrent_tasks": 3,
            "max_execution_seconds_per_task": 120,
            "max_daily_tokens": 500000,
        }
        for row in cursor.fetchall():
            try:
                res[row["key"]] = json.loads(row["value_json"])
            except Exception:
                res[row["key"]] = row["value_json"]
        return res
    finally:
        conn.close()


def save_usage_limit(key: str, value: Any) -> None:
    """Salva una singola quota o limite di utilizzo."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO usage_limits (key, value_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP;
                """,
                (key, json.dumps(value)),
            )
    finally:
        conn.close()


# --- NOTIFICHE LOCALI ---

def create_notification(
    category: str,
    title: str,
    message: str,
    related_id: str | None = None,
) -> dict[str, Any]:
    """Crea una notifica locale persistente."""
    notif_id = f"notif_{uuid.uuid4().hex[:12]}"
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO notifications (id, category, title, message, related_id, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP);
                """,
                (notif_id, category.strip(), title.strip(), message.strip(), related_id),
            )
        return {
            "id": notif_id,
            "category": category,
            "title": title,
            "message": message,
            "related_id": related_id,
            "is_read": 0,
        }
    finally:
        conn.close()


def get_notifications(
    limit: int = 50,
    unread_only: bool = False,
) -> list[dict[str, Any]]:
    """Elenca le notifiche locali."""
    conn = get_connection()
    try:
        if unread_only:
            cursor = conn.execute(
                """
                SELECT id, category, title, message, related_id, is_read, created_at
                FROM notifications
                WHERE is_read = 0
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, category, title, message, related_id, is_read, created_at
                FROM notifications
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def mark_notification_read(notification_id: str) -> bool:
    """Segna una notifica come letta."""
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?;",
                (notification_id,),
            )
            return cursor.rowcount == 1
    finally:
        conn.close()


def mark_all_notifications_read() -> int:
    """Segna tutte le notifiche come lette."""
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0;")
            return cursor.rowcount
    finally:
        conn.close()


def get_app_setting(key: str, default: Any = None) -> Any:
    """Recupera un'impostazione generale dell'applicazione."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT value_json FROM app_settings WHERE key = ?;", (key,))
        row = cur.fetchone()
        if row:
            return json.loads(row["value_json"])
        return default
    except Exception:
        return default
    finally:
        conn.close()


def save_app_setting(key: str, value: Any) -> None:
    """Salva o aggiorna un'impostazione generale dell'applicazione."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP;
                """,
                (key, json.dumps(value)),
            )
    except Exception as e:
        print(f"[DB Error] save_app_setting: {e}")
    finally:
        conn.close()


# Automatically initialize and seed database on import
init_db()
seed_db()
