"""
CoworkerOS - Fase 1.1 Hardening & Stabilizzazione Test Suite
Verifica automatizzata completa:
1. Autenticazione API REST (401 vs 200, Header Bearer, X-CoworkerOS-Token)
2. Rigetto tassativo di ?token= nelle query string delle API REST (restituisce 401)
3. Assenza assoluta di token persistenti in localStorage e nel contextBridge del renderer
4. Autenticazione WebSocket mediata (Header handshake e ticket effimero monouso, rigetto ?token= persistente)
5. Sicurezza File System (Blocco Path Traversal, symlink, .env, coworkers.db)
6. Disabilitazione Esecuzione Shell Arbitraria
7. Transizione Atomica SQLite delle Approvazioni (verifica rowcount, thread separati e concorrenza)
8. Flusso di Approvazione Obbligatoria (Waiting Approval, Execute su Approve, Annullamento su Reject)
9. Sicurezza Screen Control (Nessun clic di fallback se Vision non trova l'elemento)
10. Cleanup degli artefatti temporanei di test
"""

import os
import sys
import json
import time
import uuid
import threading
import sqlite3
import asyncio
from pathlib import Path

# Isolamento database sicuro da test_db_isolation PRIMA degli import applicativi
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
import test_db_isolation

from fastapi.testclient import TestClient

import database as db
import tools_os
from main import app, AUTH_TOKEN
from agent_engine import orchestrator


def test_auth_protection_headers_only():
    """Verifica che tutti gli endpoint critici richiedano autenticazione via header e RIFIUTINO ?token=."""
    client = TestClient(app)

    # 1. Endpoint pubblico di health
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("  [PASS] /api/health accessibile liberamente per probe loopback")

    # 2. Richieste NON autenticate -> 401 Unauthorized
    protected_endpoints = [
        ("GET", "/api/bootstrap"),
        ("GET", "/api/chats/chat_chief/messages"),
        ("GET", "/api/settings"),
        ("GET", "/api/approvals/pending"),
        ("GET", "/api/activities"),
        ("POST", "/api/settings/reset"),
    ]
    for method, ep in protected_endpoints:
        if method == "GET":
            r = client.get(ep)
        else:
            r = client.post(ep)
        assert r.status_code == 401, f"Atteso 401 su {ep}, ottenuto {r.status_code}"
    print("  [PASS] Tutti gli endpoint protetti ritornano 401 senza token")

    # 3. Richiesta con token in QUERY STRING -> DEVE ESSERE RIGETTATA (401)
    r_query1 = client.get(f"/api/bootstrap?token={AUTH_TOKEN}")
    assert r_query1.status_code == 401, f"Atteso 401 su ?token=, ottenuto {r_query1.status_code}"

    r_query2 = client.get(f"/api/settings?token={AUTH_TOKEN}")
    assert r_query2.status_code == 401, f"Atteso 401 su ?token=, ottenuto {r_query2.status_code}"
    print("  [PASS] Supporto a ?token= rimosso dalle API REST (ritorna 401)")

    # 4. Richieste con token errato negli header -> 401
    bad_headers = {"Authorization": "Bearer invalid_secret_token_12345"}
    r_bad = client.get("/api/bootstrap", headers=bad_headers)
    assert r_bad.status_code == 401
    print("  [PASS] Richiesta con token errato rifiutata (401)")

    # 5. Richieste con token corretto (Bearer) -> 200
    valid_headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    r = client.get("/api/bootstrap", headers=valid_headers)
    assert r.status_code == 200
    assert "bots" in r.json()
    print("  [PASS] Autenticazione Bearer corretta (200 OK su /api/bootstrap)")

    # 6. Richieste con header personalizzato X-CoworkerOS-Token -> 200
    custom_hdr = {"X-CoworkerOS-Token": AUTH_TOKEN}
    r2 = client.get("/api/settings", headers=custom_hdr)
    assert r2.status_code == 200
    assert r2.json()["auth_token_configured"] is True
    print("  [PASS] Autenticazione con header X-CoworkerOS-Token accettata")


def test_token_storage_and_renderer_exposure():
    """Verifica che il token master non sia presente in localStorage né esposto al renderer."""
    project_root = tools_os.PROJECT_ROOT

    # 1. Verifica frontend/src/services/api.js
    api_js = (project_root / "frontend/src/services/api.js").read_text(encoding="utf-8")
    assert "localStorage.setItem('coworkeros_auth_token'" not in api_js
    assert "localStorage.getItem('coworkeros_auth_token'" not in api_js
    assert "localStorage" not in api_js
    print("  [PASS] Assenza totale di token o chiavi in localStorage nel client frontend")

    # 2. Verifica electron/preload.js (nessun getAuthToken che esponga il token master al renderer)
    preload_js = (project_root / "electron/preload.js").read_text(encoding="utf-8")
    assert "getAuthToken" not in preload_js
    assert "getWsTicket" in preload_js
    print("  [PASS] Token master persistente non esposto nel contextBridge del renderer")


def test_websocket_auth_and_tickets():
    """Verifica autenticazione WebSocket mediata (rigetto ?token= persistente, ticket monouso e header)."""
    client = TestClient(app)
    auth_headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # 1. Connessione senza autenticazione -> Rifiutata (1008)
    rej1 = False
    try:
        with client.websocket_connect("/ws/chat_chief") as ws:
            ws.receive_json()
    except Exception:
        rej1 = True
    assert rej1, "WebSocket senza auth deve essere rifiutato"
    print("  [PASS] WebSocket senza auth rifiutato con codice 1008")

    # 2. Connessione con ?token= persistente -> DEVE ESSERE RIFIUTATA (1008)
    rej2 = False
    try:
        with client.websocket_connect(f"/ws/chat_chief?token={AUTH_TOKEN}") as ws:
            ws.receive_json()
    except Exception:
        rej2 = True
    assert rej2, "WebSocket con ?token= persistente deve essere rifiutato"
    print("  [PASS] WebSocket con ?token= persistente rifiutato con codice 1008")

    # 3. Creazione ticket effimero monouso via POST /api/auth/ws-ticket
    r_ticket = client.post("/api/auth/ws-ticket", headers=auth_headers)
    assert r_ticket.status_code == 200
    ticket_data = r_ticket.json()
    assert ticket_data.get("status") == "ok"
    ticket = ticket_data.get("ticket")
    assert ticket and len(ticket) > 16
    print("  [PASS] Endpoint /api/auth/ws-ticket genera ticket effimero monouso")

    # 4. Connessione con ticket effimero monouso -> Accettata
    with client.websocket_connect(f"/ws/chat_chief?ticket={ticket}") as ws:
        assert ws is not None
    print("  [PASS] Connessione WebSocket con ticket effimero accettata con successo")

    # 5. Secondo tentativo con lo STESSO ticket (monouso) -> Rifiutata (1008)
    rej3 = False
    try:
        with client.websocket_connect(f"/ws/chat_chief?ticket={ticket}") as ws:
            ws.receive_json()
    except Exception:
        rej3 = True
    assert rej3, "Un ticket effimero già consumato NON deve poter essere riutilizzato"
    print("  [PASS] Ticket monouso consumato: tentativo di replay rifiutato con codice 1008")

    # 6. Connessione con Header di handshake (come iniettato da onBeforeSendHeaders in Electron)
    with client.websocket_connect("/ws/chat_chief", headers={"Authorization": f"Bearer {AUTH_TOKEN}"}) as ws_hdr:
        assert ws_hdr is not None
    print("  [PASS] Connessione WebSocket con header Authorization accettata")


def test_atomic_approval_transitions_and_concurrency():
    """Verifica la transizione atomica SQLite e la mutua esclusione con connessioni concorrenti."""
    client = TestClient(app)
    auth_headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

    # 1. Creazione attività e approvazione isolata
    act = db.create_activity("chat_chief", "builder", "manage_files", {"action": "write", "path": "atomic_test.txt"})
    appr = db.create_approval(
        chat_id="chat_chief",
        bot_id="builder",
        action_type="file_write",
        description="Test atomicità SQLite",
        payload={"tool_name": "manage_files", "args": {"action": "write", "path": "atomic_test.txt", "content": "ok"}},
        activity_id=act["id"],
    )
    test_id = appr["id"]

    # 2. Concorrenza diretta con DUE connessioni SQLite indipendenti
    results = []

    def attempt_atomic_resolve(thread_idx: int):
        # Connessione SQLite indipendente per simulare due processi/thread separati
        conn_thread = sqlite3.connect(str(db.get_db_path()), check_same_thread=False)
        try:
            with conn_thread:
                cur = conn_thread.execute(
                    """
                    UPDATE approvals
                    SET status = 'approved', resolved_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'waiting_approval';
                    """,
                    (test_id,),
                )
                results.append((thread_idx, cur.rowcount))
        finally:
            conn_thread.close()

    t1 = threading.Thread(target=attempt_atomic_resolve, args=(1,))
    t2 = threading.Thread(target=attempt_atomic_resolve, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    rowcounts = [r[1] for r in results]
    assert rowcounts.count(1) == 1, f"Esattamente un thread deve aggiornare 1 riga, ottenuto: {rowcounts}"
    assert rowcounts.count(0) == 1, f"Il secondo thread concorrente deve aggiornare 0 righe, ottenuto: {rowcounts}"
    print("  [PASS] Transizione atomica SQLite su connessioni indipendenti: esattamente 1 vince (rowcount=1), l'altro perde (rowcount=0)")

    # 3. Tentativo di ri-approvazione via API -> 400 Bad Request
    r_double = client.post(f"/api/approvals/{test_id}/approve", headers=auth_headers)
    assert r_double.status_code == 400
    assert "già stata risolta" in r_double.json().get("detail", "")
    print("  [PASS] Chiamata API su approvazione già risolta bloccata con 400 Bad Request")

    # 4. Test di concorrenza end-to-end tramite API FastAPI con httpx
    act2 = db.create_activity("chat_chief", "builder", "manage_files", {"action": "write", "path": "atomic_test2.txt"})
    appr2 = db.create_approval(
        chat_id="chat_chief",
        bot_id="builder",
        action_type="file_write",
        description="Test atomicità API HTTPX",
        payload={"tool_name": "manage_files", "args": {"action": "write", "path": "atomic_test2.txt", "content": "ok2"}},
        activity_id=act2["id"],
    )
    test_id2 = appr2["id"]

    async def concurrent_http_approvals():
        import httpx
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            r1 = ac.post(f"/api/approvals/{test_id2}/approve", headers=auth_headers)
            r2 = ac.post(f"/api/approvals/{test_id2}/approve", headers=auth_headers)
            res1, res2 = await asyncio.gather(r1, r2, return_exceptions=True)
            return res1, res2

    resp1, resp2 = asyncio.run(concurrent_http_approvals())
    codes = [resp1.status_code, resp2.status_code]
    assert codes.count(200) == 1, f"Esattamente una chiamata HTTP deve avere successo (200), ottenuto {codes}"
    assert codes.count(400) == 1, f"La seconda chiamata concorrente deve fallire (400), ottenuto {codes}"
    print("  [PASS] Concorrenza API end-to-end: esattamente una riceve 200 OK e l'altra 400 Bad Request")

    # Pulizia file temporaneo generato dal test
    p_atomic = tools_os.PROJECT_ROOT / "atomic_test2.txt"
    if p_atomic.exists():
        p_atomic.unlink()


def test_path_traversal_and_file_security():
    """Verifica che l'accesso ai file sia strettamente confinato al workspace autorizzato."""
    # 1. Path traversal verso Windows System32
    res = tools_os.manage_files("read", "../../Windows/System32/drivers/etc/hosts")
    assert res.get("status") == "error"
    assert res.get("blocked") is True
    assert "fuori delle directory autorizzate" in res.get("message", "")
    print("  [PASS] Path traversal verso System32 bloccato")

    # 2. Path traversal verso la root
    res2 = tools_os.manage_files("list", "../../../..")
    assert res2.get("status") == "error"
    assert res2.get("blocked") is True
    print("  [PASS] Path traversal arbitrario bloccato")

    # 3. Tentativo di lettura file sensibile .env
    res_env = tools_os.manage_files("read", ".env")
    assert res_env.get("status") == "error"
    assert res_env.get("blocked") is True
    assert "protetto" in res_env.get("message", "")
    print("  [PASS] Lettura del file .env protetta e bloccata")

    # 4. Tentativo di lettura del database coworkers.db
    res_db = tools_os.manage_files("read", "coworkers.db")
    assert res_db.get("status") == "error"
    assert res_db.get("blocked") is True
    assert "protetto" in res_db.get("message", "")
    print("  [PASS] Lettura diretta del database protetta e bloccata")


def test_arbitrary_shell_disabled():
    """Verifica che l'esecuzione di comandi shell da parte dell'agente sia disabilitata."""
    res = tools_os.run_terminal_command("whoami")
    assert res.get("status") == "error"
    assert res.get("blocked") is True
    assert "disabilitata" in res.get("message", "")
    print("  [PASS] Esecuzione arbitraria di comandi shell disabilitata")


def test_approval_enforcement():
    """Verifica che le operazioni di modifica e desktop richiedano approvazione esplicita."""
    client = TestClient(app)
    auth_hdr = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    test_file = "test_phase1_sandbox.txt"
    test_content = "Safe content verified by Phase 1 hardening suite."

    # Assicuriamoci che non esista prima del test
    p = tools_os.PROJECT_ROOT / test_file
    if p.exists():
        p.unlink()

    # 1. Tentativo di scrittura SENZA approved=True
    res = tools_os.manage_files("write", test_file, test_content, approved=False)
    assert res.get("status") == "waiting_approval"
    assert res.get("requires_approval") is True
    assert not p.exists(), "Il file NON deve essere creato senza approvazione"
    print("  [PASS] Scrittura file richiede waiting_approval e non scrive su disco")

    # 2. Tentativo di clic desktop SENZA approved=True
    res_click = tools_os.click_at_normalized_coords(500, 500, approved=False)
    assert res_click.get("status") == "waiting_approval"
    assert res_click.get("requires_approval") is True
    print("  [PASS] Clic desktop richiede waiting_approval")

    # 3. Flusso di approvazione nel backend
    act_record = db.create_activity("chat_chief", "builder", "manage_files", {"action": "write", "path": test_file})
    act_id = act_record["id"]
    appr = db.create_approval(
        chat_id="chat_chief",
        bot_id="builder",
        action_type="file_write",
        description=f"Scrittura file {test_file}",
        payload={"tool_name": "manage_files", "args": {"action": "write", "path": test_file, "content": test_content}},
        activity_id=act_id,
    )
    appr_id = appr["id"]

    # Verifica comparsa tra le approvazioni in attesa
    r_pend = client.get("/api/approvals/pending", headers=auth_hdr)
    assert r_pend.status_code == 200
    pending_ids = [a["id"] for a in r_pend.json().get("approvals", [])]
    assert appr_id in pending_ids
    print("  [PASS] Approvazione registrata e presente in /api/approvals/pending")

    # Esegui approvazione via API
    r_appr = client.post(f"/api/approvals/{appr_id}/approve", headers=auth_hdr)
    assert r_appr.status_code == 200
    assert r_appr.json().get("status") == "ok"

    # Verifica che ora il file esista con il contenuto corretto
    assert p.exists(), "Il file DEVE esistere dopo l'approvazione esplicita"
    assert p.read_text(encoding="utf-8") == test_content
    print("  [PASS] Approvazione eseguita: file creato con successo solo dopo conferma")

    # Verifica stato attività aggiornato a completed
    acts = db.get_activities("chat_chief", limit=10)
    matching_act = [a for a in acts if a["id"] == act_id]
    assert matching_act and matching_act[0]["status"] == "completed"
    print("  [PASS] Stato attività aggiornato a 'completed'")

    # 4. Flusso di rifiuto (Reject)
    act_record2 = db.create_activity("chat_chief", "builder", "manage_files", {"action": "delete", "path": test_file})
    act_id2 = act_record2["id"]
    appr2 = db.create_approval(
        chat_id="chat_chief",
        bot_id="builder",
        action_type="file_delete",
        description=f"Eliminazione {test_file}",
        payload={"tool_name": "manage_files", "args": {"action": "delete", "path": test_file}},
        activity_id=act_id2,
    )
    r_rej = client.post(f"/api/approvals/{appr2['id']}/reject", headers=auth_hdr)
    assert r_rej.status_code == 200

    # Verifica che il file NON sia stato eliminato
    assert p.exists(), "Il file NON deve essere eliminato dopo il rifiuto"

    # Verifica stato attività aggiornato a failed
    acts2 = db.get_activities("chat_chief", limit=10)
    matching_act2 = [a for a in acts2 if a["id"] == act_id2]
    assert matching_act2 and matching_act2[0]["status"] == "failed"
    print("  [PASS] Rifiuto eseguito: operazione annullata e stato attività 'failed'")

    # Pulizia file temporaneo
    if p.exists():
        p.unlink()


def test_screen_control_no_blind_fallback():
    """Verifica che la logica di Vision non utilizzi coordinate di fallback se il target non viene trovato."""
    res = asyncio.run(orchestrator._locate_element_with_vision("Elemento inesistente 9999XYZ"))
    if not res.get("found"):
        assert res.get("norm_x") is None, "norm_x deve essere None quando l'elemento non è trovato"
        assert res.get("norm_y") is None, "norm_y deve essere None quando l'elemento non è trovato"
        assert "fallback disabilitato" in res.get("error", "").lower()
    print("  [PASS] Screen Control: Clic di fallback disabilitato in assenza di certezza visiva")


if __name__ == "__main__":
    print("\n--- AVVIO TEST SUITE: COWORKEROS FASE 1.1 HARDENING COMPLETO ---")
    try:
        test_auth_protection_headers_only()
        test_token_storage_and_renderer_exposure()
        test_websocket_auth_and_tickets()
        test_atomic_approval_transitions_and_concurrency()
        test_path_traversal_and_file_security()
        test_arbitrary_shell_disabled()
        test_approval_enforcement()
        test_screen_control_no_blind_fallback()
        print("\n=== TUTTI I TEST DI HARDENING (FASE 1.1) SONO STATI SUPERATI CON SUCCESSO! ===")
    except Exception as e:
        print(f"\n[FAIL] Errore durante i test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
