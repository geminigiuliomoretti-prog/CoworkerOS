/**
 * CoworkerOS Client API & Centralized Backend Connector
 * Connects securely to FastAPI backend (REST & WebSocket).
 * L'autenticazione e' mediata dal processo principale Electron (onBeforeSendHeaders)
 * e da ticket effimeri monouso per WebSocket, senza persistere segreti nel browser
 * e senza esporre credenziali persistenti negli URL.
 */

export const BACKEND_URL = 'http://127.0.0.1:8000';
export const API_BASE = `${BACKEND_URL}/api`;
export const WS_BASE = 'ws://127.0.0.1:8000/ws';

// Token in sola memoria volatile (opzionale per test, mai persistito su disco o storage)
let inMemorySessionToken = '';

export function setSessionToken(token) {
  inMemorySessionToken = token ? token.trim() : '';
}

/**
 * Returns request headers. In Electron, authorization headers are automatically
 * injected by the main process (session.defaultSession.webRequest.onBeforeSendHeaders).
 */
export async function getAuthHeaders(extraHeaders = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...extraHeaders,
  };
  if (inMemorySessionToken) {
    headers['Authorization'] = `Bearer ${inMemorySessionToken}`;
    headers['X-CoworkerOS-Token'] = inMemorySessionToken;
  }
  return headers;
}

/**
 * Wrapper for fetch with local authentication and timeout.
 */
export async function authFetch(url, options = {}, timeoutMs = 25000) {
  const headers = await getAuthHeaders(options.headers || {});
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return res;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err.name === 'AbortError') {
      throw new Error(`Timeout richiesta (${Math.round(timeoutMs / 1000)}s superati). L'elaborazione locale richiede più tempo.`);
    }
    if (err.message === 'Failed to fetch' || (err instanceof TypeError)) {
      throw new Error('Impossibile connettersi al backend di CoworkerOS (127.0.0.1:8000). Il server locale è in avvio o non raggiungibile.');
    }
    throw err;
  }
}

// Default iconic coworker bots
export const DEFAULT_BOTS = [
  {
    id: 'chief',
    name: 'Chief',
    role: 'Coordinator & Chief of Staff',
    system_prompt:
      'Sei Chief. Analizzi le richieste dell utente, pianifichi il lavoro e usi il tool delegate_to_coworker per passare i compiti agli altri bot senza che l utente debba fare nulla.',
    shape: 'squircle',
    color: '#00BA88',
    effort: 'high',
  },
  {
    id: 'architect',
    name: 'Architect',
    role: 'Product & Roadmap Strategist',
    system_prompt:
      'Sei Architect. Crei roadmap tecniche, prompt dettagliati per Antigravity e architetture software. Passi il risultato a Builder.',
    shape: 'circle',
    color: '#FF6B00',
    effort: 'high',
  },
  {
    id: 'builder',
    name: 'Builder',
    role: 'PC & Antigravity Operator',
    system_prompt:
      'Sei Builder. Controlli fisicamente il PC: fai screenshot, porti finestre in primo piano, clicchi con il mouse, incolli codice o prompt.',
    shape: 'triangle',
    color: '#FF2E93',
    effort: 'low',
  },
  {
    id: 'scout',
    name: 'Scout',
    role: 'Web & Deep Researcher',
    system_prompt:
      'Sei Scout. Esegui ricerche web approfondite, raccogli documentazione e analizzi fonti esterne.',
    shape: 'cloud',
    color: '#FFB800',
    effort: 'medium',
  },
  {
    id: 'archivist',
    name: 'Archivist',
    role: 'File System & Archive Manager',
    system_prompt:
      'Sei Archivist. Gestisci il file system locale, archivi e recuperi file di progetto e log.',
    shape: 'cylinder',
    color: '#1D7AFC',
    effort: 'low',
  },
];

export const DEFAULT_CHATS = [
  { id: 'chat_chief', title: 'Chief', is_group: 0, participants: ['chief'] },
  { id: 'chat_architect', title: 'Architect', is_group: 0, participants: ['architect'] },
  { id: 'chat_builder', title: 'Builder', is_group: 0, participants: ['builder'] },
  { id: 'chat_scout', title: 'Scout', is_group: 0, participants: ['scout'] },
  { id: 'chat_archivist', title: 'Archivist', is_group: 0, participants: ['archivist'] },
];

export async function bootstrap() {
  const res = await authFetch(`${API_BASE}/bootstrap`, {}, 10000);

  if (!res.ok) {
    throw new Error(
      `Bootstrap fallito: HTTP ${res.status}`
    );
  }

  const data = await res.json();

  if (!Array.isArray(data.bots) || !Array.isArray(data.chats)) {
    throw new Error('Risposta bootstrap non valida');
  }

  return data;
}

export async function fetchMessages(chatId) {
  const res = await authFetch(
    `${API_BASE}/chats/${encodeURIComponent(chatId)}/messages`,
    {},
    10000
  );

  if (!res.ok) {
    throw new Error(
      `Caricamento messaggi fallito: HTTP ${res.status}`
    );
  }

  const messages = await res.json();

  if (!Array.isArray(messages)) {
    throw new Error('Formato messaggi non valido');
  }

  return messages;
}

export async function sendChatMessage({
  chatId,
  content,
  targetBotId = null,
}) {
  const res = await authFetch(`${API_BASE}/chats/${chatId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      content,
      target_bot_id: targetBotId,
    }),
  }, 180000); // 180s per concedere tempo a Qwen locale su CPU / batteria

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile inviare il messaggio al backend.');
  }

  return await res.json();
}

export async function checkBackendHealth() {
  try {
    const res = await authFetch(
      `${API_BASE}/bootstrap`,
      {},
      5000
    );

    return res.ok;
  } catch {
    return false;
  }
}

export async function getTestChats() {
  try {
    const res = await authFetch(`${API_BASE}/chats/test-chats`, {}, 5000);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn('Failed to fetch test chats:', err);
  }
  return { count: 0, test_chats: [] };
}

export async function cleanupTestChats(chatIds) {
  const res = await authFetch(`${API_BASE}/chats/cleanup-tests`, {
    method: 'POST',
    body: JSON.stringify({ chat_ids: chatIds, confirmed: true }),
  }, 20000);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile eliminare le chat di test.');
  }
  return await res.json();
}

export async function createBot(botData) {
  const res = await authFetch(`${API_BASE}/bots`, {
    method: 'POST',
    body: JSON.stringify(botData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create bot');
  }
  return await res.json();
}

export async function createChat(chatData) {
  const res = await authFetch(`${API_BASE}/chats`, {
    method: 'POST',
    body: JSON.stringify(chatData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create room');
  }
  return await res.json();
}

export async function deleteChat(chatId) {
  const res = await authFetch(`${API_BASE}/chats/${chatId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    throw new Error('Impossibile eliminare la conversazione');
  }
  return await res.json();
}

export async function getSettings() {
  const res = await authFetch(`${API_BASE}/settings`);
  if (!res.ok) {
    throw new Error('Impossibile recuperare le impostazioni');
  }
  return await res.json();
}

export async function saveApiKey(apiKey) {
  const res = await authFetch(`${API_BASE}/settings/apikey`, {
    method: 'POST',
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile salvare la chiave API');
  }
  return await res.json();
}

export async function resetDatabase() {
  const res = await authFetch(`${API_BASE}/settings/reset`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Impossibile resettare il database');
  }
  return await res.json();
}

export async function getModelStatus() {
  try {
    const res = await authFetch(`${API_BASE}/model/status`, {}, 4000);
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn('Failed to fetch model status:', err);
  }
  return {
    provider_mode: 'AUTO',
    active_provider: 'AUTO',
    local_model: { status: 'stopped', is_alive: false },
    gemini: { configured: false },
    ram_info: { available_gb: 0, total_gb: 0 },
  };
}

export async function setModelProvider(mode) {
  const res = await authFetch(`${API_BASE}/model/provider`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  }, 40000);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile cambiare modalità provider');
  }
  return await res.json();
}

export async function startLocalModel(enableVision = false) {
  const res = await authFetch(`${API_BASE}/model/start`, {
    method: 'POST',
    body: JSON.stringify({ enable_vision: enableVision }),
  }, 45000);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile avviare il modello locale');
  }
  return await res.json();
}

export async function stopLocalModel() {
  const res = await authFetch(`${API_BASE}/model/stop`, {
    method: 'POST',
  }, 10000);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile arrestare il modello locale');
  }
  return await res.json();
}

export async function getLiveScreenshot() {
  const res = await authFetch(`${API_BASE}/os/screenshot`, {}, 8000);
  if (!res.ok) {
    throw new Error('Impossibile catturare lo screenshot');
  }
  return await res.json();
}

export async function getOpenWindows() {
  const res = await authFetch(`${API_BASE}/os/windows`, {}, 5000);
  if (!res.ok) {
    throw new Error('Impossibile ottenere la lista delle finestre');
  }
  return await res.json();
}

// TASKS API (FASE 2A: MOTORE MULTI-AGENTE PERSISTENTE)

export async function getTasks(chatId = null, status = null) {
  const params = new URLSearchParams();
  if (chatId) params.append('chat_id', chatId);
  if (status) params.append('status', status);
  const query = params.toString() ? `?${params.toString()}` : '';
  const res = await authFetch(`${API_BASE}/tasks${query}`, {}, 10000);
  if (!res.ok) return [];
  const data = await res.json();
  return data.tasks || [];
}

export async function getTask(taskId) {
  const res = await authFetch(`${API_BASE}/tasks/${taskId}`, {}, 10000);
  if (!res.ok) return null;
  const data = await res.json();
  return data.task || null;
}

export async function resumeTask(taskId) {
  const res = await authFetch(`${API_BASE}/tasks/${taskId}/resume`, {
    method: 'POST',
  }, 45000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante la ripresa del task');
  }
  return await res.json();
}

export async function cancelTask(taskId) {
  const res = await authFetch(`${API_BASE}/tasks/${taskId}/cancel`, {
    method: 'POST',
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante l\'annullamento del task');
  }
  return await res.json();
}

// MEMORIES API (FASE 2B: MEMORIA PERSISTENTE INTELLIGENTE)

export async function getMemories(q = '', projectId = null, memoryType = null, limit = 50) {
  const params = new URLSearchParams();
  if (q) params.append('q', q);
  if (projectId) params.append('project_id', projectId);
  if (memoryType) params.append('memory_type', memoryType);
  params.append('limit', limit);
  const res = await authFetch(`${API_BASE}/memories?${params.toString()}`, {}, 10000);
  if (!res.ok) return [];
  const data = await res.json();
  return data.memories || [];
}

export async function createMemory(payload) {
  const res = await authFetch(`${API_BASE}/memories`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante la creazione della memoria');
  }
  return await res.json();
}

export async function updateMemory(memoryId, payload) {
  const res = await authFetch(`${API_BASE}/memories/${memoryId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante la modifica della memoria');
  }
  return await res.json();
}

export async function deleteMemory(memoryId) {
  const res = await authFetch(`${API_BASE}/memories/${memoryId}`, {
    method: 'DELETE',
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante l\'eliminazione della memoria');
  }
  return await res.json();
}

export async function getMemorySettings() {
  const res = await authFetch(`${API_BASE}/memories/settings`, {}, 5000);
  if (!res.ok) return { auto_memory_enabled: true, max_context_budget: 2500 };
  const data = await res.json();
  return data.settings || { auto_memory_enabled: true, max_context_budget: 2500 };
}

export async function saveMemorySettings(settings) {
  const res = await authFetch(`${API_BASE}/memories/settings`, {
    method: 'POST',
    body: JSON.stringify(settings),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore salvataggio impostazioni memoria');
  }
  return await res.json();
}

// SCHEDULER & AUTOMAZIONI API (FASE 2C)

export async function getScheduledJobs(projectId = null, status = null) {
  const params = new URLSearchParams();
  if (projectId) params.append('project_id', projectId);
  if (status) params.append('status', status);
  const res = await authFetch(`${API_BASE}/scheduler/jobs?${params.toString()}`, {}, 10000);
  if (!res.ok) return [];
  return await res.json();
}

export async function createScheduledJob(payload) {
  const res = await authFetch(`${API_BASE}/scheduler/jobs`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore creazione attività programmata');
  }
  return await res.json();
}

export async function updateScheduledJob(jobId, payload) {
  const res = await authFetch(`${API_BASE}/scheduler/jobs/${jobId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore aggiornamento attività programmata');
  }
  return await res.json();
}

export async function deleteScheduledJob(jobId) {
  const res = await authFetch(`${API_BASE}/scheduler/jobs/${jobId}`, {
    method: 'DELETE',
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore eliminazione attività programmata');
  }
  return await res.json();
}

export async function runScheduledJobNow(jobId) {
  const res = await authFetch(`${API_BASE}/scheduler/jobs/${jobId}/run-now`, {
    method: 'POST',
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore avvio immediato attività');
  }
  return await res.json();
}

export async function getJobHistory(jobId) {
  const res = await authFetch(`${API_BASE}/scheduler/jobs/${jobId}/history`, {}, 10000);
  if (!res.ok) return [];
  return await res.json();
}

export async function getAllSchedulerHistory() {
  const res = await authFetch(`${API_BASE}/scheduler/history`, {}, 10000);
  if (!res.ok) return [];
  return await res.json();
}

// CONSUMI & QUOTE API (FASE 2C)

export async function getUsageSummary(days = 1) {
  const res = await authFetch(`${API_BASE}/usage/summary?days=${days}`, {}, 10000);
  if (!res.ok) return { requests_count: 0, total_tokens: 0, estimated_cost_usd: 0.0 };
  return await res.json();
}

export async function getUsageLimits() {
  const res = await authFetch(`${API_BASE}/usage/limits`, {}, 5000);
  if (!res.ok) return {};
  return await res.json();
}

export async function saveUsageLimit(key, value) {
  const res = await authFetch(`${API_BASE}/usage/limits`, {
    method: 'POST',
    body: JSON.stringify({ key, value }),
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore salvataggio quota');
  }
  return await res.json();
}

// NOTIFICHE LOCALI API (FASE 2C)

export async function getNotifications(unreadOnly = false) {
  const res = await authFetch(`${API_BASE}/notifications?unread_only=${unreadOnly}`, {}, 10000);
  if (!res.ok) return [];
  return await res.json();
}

export async function markNotificationRead(notifId) {
  const res = await authFetch(`${API_BASE}/notifications/${notifId}/read`, {
    method: 'POST',
  }, 5000);
  if (!res.ok) return false;
  const data = await res.json();
  return data.marked || false;
}

export async function markAllNotificationsRead() {
  const res = await authFetch(`${API_BASE}/notifications/read-all`, {
    method: 'POST',
  }, 5000);
  if (!res.ok) return 0;
  const data = await res.json();
  return data.marked_count || 0;
}

// APPROVALS API (FASE 1: HARDENING)

export async function getPendingApprovals(chatId = null) {
  const url = chatId
    ? `${API_BASE}/approvals/pending?chat_id=${encodeURIComponent(chatId)}`
    : `${API_BASE}/approvals/pending`;
  const res = await authFetch(url, {}, 5000);
  if (!res.ok) return [];
  const data = await res.json();
  return data.approvals || [];
}

export async function approveAction(approvalId) {
  const res = await authFetch(`${API_BASE}/approvals/${approvalId}/approve`, {
    method: 'POST',
  }, 35000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante l\'approvazione dell\'azione');
  }
  return await res.json();
}

export async function rejectAction(approvalId) {
  const res = await authFetch(`${API_BASE}/approvals/${approvalId}/reject`, {
    method: 'POST',
  }, 10000);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Errore durante il rifiuto dell\'azione');
  }
  return await res.json();
}

/**
 * Connect to WebSocket with local authentication.
 * In Electron, headers are automatically attached by main process (onBeforeSendHeaders).
 * Alternativamente richiede un ticket effimero monouso a brevissima scadenza.
 * Nessuna credenziale persistente viene mai inserita nell'URL.
 */
export async function connectWebSocket(chatId, onMessage, onError, onClose) {
  let ws = null;
  let isClosedIntentionally = false;
  let reconnectTimeout = null;

  async function connect() {
    try {
      let ticket = null;
      if (typeof window !== 'undefined' && window.electronAPI?.getWsTicket) {
        try {
          const res = await window.electronAPI.getWsTicket();
          ticket = res?.ticket || null;
        } catch (_) {}
      }

      // Se disponibile ticket effimero monouso, usa ?ticket= (mai il token persistente master)
      const wsUrl = ticket
        ? `${WS_BASE}/${chatId}?ticket=${encodeURIComponent(ticket)}`
        : `${WS_BASE}/${chatId}`;

      ws = new WebSocket(wsUrl);

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          onMessage?.(parsed);
        } catch {
          onMessage?.(event.data);
        }
      };

      ws.onerror = (err) => {
        onError?.(err);
      };

      ws.onclose = (event) => {
        if (!isClosedIntentionally) {
          onClose?.(event);
          reconnectTimeout = setTimeout(connect, 3000);
        }
      };
    } catch (e) {
      onError?.(e);
    }
  }

  await connect();

  return {
    send: (payload) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(typeof payload === 'string' ? payload : JSON.stringify(payload));
        return true;
      }
      return false;
    },
    close: () => {
      isClosedIntentionally = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    },
  };
}
