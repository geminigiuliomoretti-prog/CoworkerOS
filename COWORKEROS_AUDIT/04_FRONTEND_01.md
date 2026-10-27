
--- FILE: \frontend\src\App.css ---
.counter {
  font-size: 16px;
  padding: 5px 10px;
  border-radius: 5px;
  color: var(--accent);
  background: var(--accent-bg);
  border: 2px solid transparent;
  transition: border-color 0.3s;
  margin-bottom: 24px;

  &:hover {
    border-color: var(--accent-border);
  }
  &:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
}

.hero {
  position: relative;

  .base,
  .framework,
  .vite {
    inset-inline: 0;
    margin: 0 auto;
  }

  .base {
    width: 170px;
    position: relative;
    z-index: 0;
  }

  .framework,
  .vite {
    position: absolute;
  }

  .framework {
    z-index: 1;
    top: 34px;
    height: 28px;
    transform: perspective(2000px) rotateZ(300deg) rotateX(44deg) rotateY(39deg)
      scale(1.4);
  }

  .vite {
    z-index: 0;
    top: 107px;
    height: 26px;
    width: auto;
    transform: perspective(2000px) rotateZ(300deg) rotateX(40deg) rotateY(39deg)
      scale(0.8);
  }
}

#center {
  display: flex;
  flex-direction: column;
  gap: 25px;
  place-content: center;
  place-items: center;
  flex-grow: 1;

  @media (max-width: 1024px) {
    padding: 32px 20px 24px;
    gap: 18px;
  }
}

#next-steps {
  display: flex;
  border-top: 1px solid var(--border);
  text-align: left;

  & > div {
    flex: 1 1 0;
    padding: 32px;
    @media (max-width: 1024px) {
      padding: 24px 20px;
    }
  }

  .icon {
    margin-bottom: 16px;
    width: 22px;
    height: 22px;
  }

  @media (max-width: 1024px) {
    flex-direction: column;
    text-align: center;
  }
}

#docs {
  border-right: 1px solid var(--border);

  @media (max-width: 1024px) {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}

#next-steps ul {
  list-style: none;
  padding: 0;
  display: flex;
  gap: 8px;
  margin: 32px 0 0;

  .logo {
    height: 18px;
  }

  a {
    color: var(--text-h);
    font-size: 16px;
    border-radius: 6px;
    background: var(--social-bg);
    display: flex;
    padding: 6px 12px;
    align-items: center;
    gap: 8px;
    text-decoration: none;
    transition: box-shadow 0.3s;

    &:hover {
      box-shadow: var(--shadow);
    }
    .button-icon {
      height: 18px;
      width: 18px;
    }
  }

  @media (max-width: 1024px) {
    margin-top: 20px;
    flex-wrap: wrap;
    justify-content: center;

    li {
      flex: 1 1 calc(50% - 8px);
    }

    a {
      width: 100%;
      justify-content: center;
      box-sizing: border-box;
    }
  }
}

#spacer {
  height: 88px;
  border-top: 1px solid var(--border);
  @media (max-width: 1024px) {
    height: 48px;
  }
}

.ticks {
  position: relative;
  width: 100%;

  &::before,
  &::after {
    content: '';
    position: absolute;
    top: -4.5px;
    border: 5px solid transparent;
  }

  &::before {
    left: 0;
    border-left-color: var(--border);
  }
  &::after {
    right: 0;
    border-right-color: var(--border);
  }
}


--- FILE: \frontend\src\App.jsx ---
import React, { useState, useEffect, useRef } from 'react';
import {
  Plus, Search, Settings, Monitor, Send, CheckCircle2,
  Loader2, X, Camera, FolderOpen, Key, RefreshCw, ExternalLink
} from 'lucide-react';
import BlobAvatar from './components/BlobAvatar';

const API_BASE = 'http://127.0.0.1:8000';
const WS_BASE = 'ws://127.0.0.1:8000';

export default function App() {
  const [bots, setBots] = useState([]);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState('chat_chief');
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [botStatuses, setBotStatuses] = useState({});
  const [isSending, setIsSending] = useState(false);

  const [showNewModal, setShowNewModal] = useState(false);
  const [newModalTab, setNewModalTab] = useState('chat');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showInspectorModal, setShowInspectorModal] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);

  const [apiKeyInput, setApiKeyInput] = useState('');
  const [maskedKey, setMaskedKey] = useState('');
  const [newChatTitle, setNewChatTitle] = useState('');
  const [selectedBotIds, setSelectedBotIds] = useState(['chief', 'architect', 'builder']);
  const [newBotName, setNewBotName] = useState('');
  const [newBotRole, setNewBotRole] = useState('');
  const [newBotPrompt, setNewBotPrompt] = useState('');
  const [newBotShape, setNewBotShape] = useState('squircle');
  const [newBotColor, setNewBotColor] = useState('#10B981');

  const [inspectorData, setInspectorData] = useState(null);
  const [inspectorWindows, setInspectorWindows] = useState([]);
  const [loadingInspector, setLoadingInspector] = useState(false);

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const fileInputRef = useRef(null);

  const botsMap = React.useMemo(() => {
    const map = {};
    bots.forEach((b) => { map[b.id] = b; });
    return map;
  }, [bots]);

  const activeChat = React.useMemo(
    () => chats.find((c) => c.id === activeChatId) || chats[0] || null,
    [chats, activeChatId]
  );

  const fetchBootstrap = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/bootstrap`);
      const data = await res.json();
      setBots(data.bots || []);
      setChats(data.chats || []);
      if (data.chats?.length && !data.chats.find((c) => c.id === activeChatId)) {
        setActiveChatId(data.chats[0].id);
      }
    } catch (err) {
      console.error('Bootstrap error:', err);
    }
  };

  const fetchMessages = async (chatId) => {
    if (!chatId) return;
    try {
      const res = await fetch(`${API_BASE}/api/chats/${chatId}/messages`);
      const data = await res.json();
      setMessages(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Messages error:', err);
    }
  };

  useEffect(() => {
    fetchBootstrap();
  }, []);

  useEffect(() => {
    if (!activeChatId) return;
    fetchMessages(activeChatId);

    if (wsRef.current) {
      wsRef.current.close();
    }
    const ws = new WebSocket(`${WS_BASE}/ws/${activeChatId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'new_message' && payload.message) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === payload.message.id)) return prev;
            return [...prev, payload.message];
          });
          fetchBootstrap();
        } else if (payload.type === 'bot_status') {
          setBotStatuses((prev) => ({
            ...prev,
            [payload.bot_id]: payload.status === 'idle' ? null : {
              name: payload.bot_name || payload.bot_id,
              status: payload.status,
            },
          }));
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    return () => ws.close();
  }, [activeChatId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, botStatuses]);

  const handleSendMessage = async (customText = null) => {
    const text = (customText !== null ? customText : inputText).trim();
    if (!text || !activeChatId || isSending) return;
    if (customText === null) setInputText('');
    setIsSending(true);

    try {
      const res = await fetch(`${API_BASE}/api/chats/${activeChatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: text }),
      });
      const data = await res.json();
      if (data.bot_replies) {
        await fetchMessages(activeChatId);
        await fetchBootstrap();
      }
    } catch (err) {
      console.error('Send error:', err);
    } finally {
      setIsSending(false);
      setBotStatuses({});
    }
  };

  const openInspector = async () => {
    setShowInspectorModal(true);
    setLoadingInspector(true);
    try {
      const [capRes, winRes] = await Promise.all([
        fetch(`${API_BASE}/api/os/screenshot`),
        fetch(`${API_BASE}/api/os/windows`),
      ]);
      setInspectorData(await capRes.json());
      const winJson = await winRes.json();
      setInspectorWindows(winJson.windows || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingInspector(false);
    }
  };

  const openSettings = async () => {
    setShowSettingsModal(true);
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      const data = await res.json();
      setMaskedKey(data.masked_key || '');
    } catch (_) {}
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    await fetch(`${API_BASE}/api/settings/apikey`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKeyInput.trim() }),
    });
    setApiKeyInput('');
    setShowSettingsModal(false);
    fetchBootstrap();
  };

  const handleCreateChat = async () => {
    if (!newChatTitle.trim() || selectedBotIds.length === 0) return;
    const res = await fetch(`${API_BASE}/api/chats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newChatTitle.trim(), participants: selectedBotIds }),
    });
    const data = await res.json();
    await fetchBootstrap();
    if (data.chat?.id) setActiveChatId(data.chat.id);
    setNewChatTitle('');
    setShowNewModal(false);
  };

  const handleCreateBot = async () => {
    if (!newBotName.trim() || !newBotRole.trim()) return;
    const res = await fetch(`${API_BASE}/api/bots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newBotName.trim(),
        role: newBotRole.trim(),
        system_prompt: newBotPrompt.trim(),
        shape: newBotShape,
        color: newBotColor,
      }),
    });
    const data = await res.json();
    await fetchBootstrap();
    if (data.chat?.id) setActiveChatId(data.chat.id);
    setNewBotName('');
    setNewBotRole('');
    setNewBotPrompt('');
    setShowNewModal(false);
  };

  const activeWorkingBots = Object.entries(botStatuses)
    .filter(([, val]) => val !== null)
    .map(([id, val]) => ({ id, ...val }));

  const filteredChats = chats.filter((c) =>
    (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#FFFFFF] text-[#111827] select-none font-sans">
      <aside className="w-[290px] bg-[#F8F8F7] border-r border-gray-200 flex flex-col h-full shrink-0">
        <div
          className="h-12 px-4 flex items-center justify-between border-b border-gray-200/70"
          style={{ WebkitAppRegion: 'drag' }}
        >
          <div className="flex items-center gap-2" style={{ WebkitAppRegion: 'no-drag' }}>
            <button
              onClick={() => window.electronAPI?.close?.()}
              className="w-3 h-3 rounded-full bg-[#FF5F56] hover:opacity-80 cursor-pointer"
              title="Chiudi"
            />
            <button
              onClick={() => window.electronAPI?.minimize?.()}
              className="w-3 h-3 rounded-full bg-[#FFBD2E] hover:opacity-80 cursor-pointer"
              title="Riduci a icona"
            />
            <button
              onClick={() => window.electronAPI?.maximize?.()}
              className="w-3 h-3 rounded-full bg-[#27C93F] hover:opacity-80 cursor-pointer"
              title="Ingrandisci"
            />
          </div>

          <button
            onClick={() => setShowNewModal(true)}
            style={{ WebkitAppRegion: 'no-drag' }}
            className="p-1.5 rounded-lg hover:bg-gray-200/80 text-gray-700 transition cursor-pointer z-50"
            title="Nuovo Coworker o Stanza (+)"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>

        <div className="p-3">
          <div className="flex items-center gap-2 bg-gray-200/70 rounded-xl px-3 py-2">
            <Search className="w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cerca conversazione..."
              className="bg-transparent text-sm w-full focus:outline-none text-gray-800"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {filteredChats.map((chat) => {
            const partIds = chat.participants || ['chief'];
            const primaryBot = botsMap[partIds[0]] || { shape: 'squircle', color: '#10B981', name: chat.title };
            const isSelected = chat.id === activeChatId;
            const workingInfo = partIds.map((id) => botStatuses[id]).find(Boolean);

            return (
              <button
                key={chat.id}
                onClick={() => setActiveChatId(chat.id)}
                className={`w-full flex items-center gap-3 p-2.5 rounded-2xl text-left transition cursor-pointer ${
                  isSelected ? 'bg-[#EBEAE6]' : 'hover:bg-gray-200/50'
                }`}
              >
                <div className="relative flex items-center shrink-0">
                  <BlobAvatar
                    shape={primaryBot.shape}
                    color={primaryBot.color}
                    size={40}
                    status={workingInfo ? 'working' : 'idle'}
                  />
                  {partIds.length > 1 && (
                    <span className="absolute -bottom-1 -right-1 bg-gray-900 text-white text-[10px] font-bold px-1.5 py-0.2 rounded-full">
                      {partIds.length}
                    </span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm text-gray-900 truncate">{chat.title}</span>
                  </div>
                  {workingInfo ? (
                    <p className="text-xs text-orange-600 font-medium truncate">
                      â— {workingInfo.status}
                    </p>
                  ) : (
                    <p className="text-xs text-gray-500 truncate">
                      {chat.last_message || primaryBot.role || 'Pronto ad agire'}
                    </p>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        <div className="p-3 border-t border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-gray-800 text-white flex items-center justify-center text-xs font-bold">
              C
            </div>
            <div>
              <div className="text-xs font-semibold text-gray-900">Costa</div>
              <div className="text-[11px] text-emerald-600 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                gemini-3.8-flash (Online)
              </div>
            </div>
          </div>
          <button
            onClick={openSettings}
            style={{ WebkitAppRegion: 'no-drag' }}
            className="p-2 rounded-xl hover:bg-gray-200 text-gray-600 cursor-pointer"
            title="Impostazioni & API Key"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col h-full bg-white">
        <header
          className="h-14 border-b border-gray-100 pl-6 pr-36 flex items-center justify-between shrink-0"
          style={{ WebkitAppRegion: 'drag' }}
        >
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {(activeChat?.participants || ['chief']).map((bid) => {
                const b = botsMap[bid] || { shape: 'circle', color: '#10B981' };
                return (
                  <div key={bid} className="ring-2 ring-white rounded-full">
                    <BlobAvatar shape={b.shape} color={b.color} size={32} />
                  </div>
                );
              })}
            </div>
            <div>
              <h2 className="font-bold text-sm text-gray-900">{activeChat?.title || 'Chief'}</h2>
              <p className="text-xs text-gray-500">
                {(activeChat?.participants || ['chief']).length} coworker attivi
                {activeWorkingBots.length > 0 && ` â€¢ ${activeWorkingBots[0].name}: ${activeWorkingBots[0].status}`}
              </p>
            </div>
          </div>

          <button
            onClick={openInspector}
            style={{ WebkitAppRegion: 'no-drag' }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-xs font-medium text-gray-700 transition cursor-pointer z-50"
          >
            <Monitor className="w-4 h-4 text-orange-500" />
            <span>Screen Inspector</span>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-6 space-y-5 select-text">
          {messages.map((msg) => {
            const isUser = msg.sender_id === 'user';
            const bot = botsMap[msg.sender_id] || {
              name: msg.sender_name || msg.sender_id,
              shape: 'squircle',
              color: '#10B981',
            };
            let card = null;
            if (msg.action_card_json) {
              try {
                card = typeof msg.action_card_json === 'string'
                  ? JSON.parse(msg.action_card_json)
                  : msg.action_card_json;
              } catch (_) {}
            }

            if (isUser) {
              return (
                <div key={msg.id} className="flex flex-col items-end">
                  <span className="text-[11px] text-gray-400 mb-1">You</span>
                  <div className="bg-[#18181B] text-white px-4 py-2.5 rounded-2xl rounded-tr-sm max-w-xl text-sm whitespace-pre-wrap">
                    {msg.content}
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="flex items-start gap-3">
                <div className="shrink-0 mt-1">
                  <BlobAvatar shape={bot.shape} color={bot.color} size={36} />
                </div>
                <div className="flex-1 max-w-2xl space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold" style={{ color: bot.color }}>
                      {bot.name}
                    </span>
                  </div>
                  <div className="bg-[#F6F6F4] text-gray-800 px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed whitespace-pre-wrap">
                    {msg.content}
                  </div>

                  {card && card.screenshot_b64 && (
                    <div className="bg-[#F9F9F8] border border-gray-200 rounded-2xl p-4 shadow-sm max-w-xl">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Monitor className="w-4 h-4 text-gray-700" />
                          <span className="font-bold text-xs text-gray-900">Computer - Live Monitor</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3" />
                            Done
                          </span>
                          <button
                            onClick={openInspector}
                            className="p-1 hover:bg-gray-200 rounded text-gray-500 cursor-pointer"
                            title="Ingrandisci ispezione"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-gray-600 mb-3">{card.title}</p>
                      <div className="relative rounded-xl overflow-hidden border border-gray-300 bg-gray-900">
                        <img
                          src={`data:image/jpeg;base64,${card.screenshot_b64}`}
                          alt="Desktop Capture"
                          className="w-full h-auto object-contain block"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {activeWorkingBots.map((wb) => {
            const b = botsMap[wb.id] || { shape: 'squircle', color: '#10B981' };
            return (
              <div key={wb.id} className="flex items-center gap-3 text-xs text-gray-500 animate-pulse">
                <BlobAvatar shape={b.shape} color={b.color} size={28} status="working" />
                <span>
                  <b>{wb.name}</b>: {wb.status}
                </span>
              </div>
            );
          })}
          <div ref={messagesEndRef} />
        </div>

        <div className="p-4 bg-white border-t border-gray-100 relative">
          {showAttachMenu && (
            <div className="absolute bottom-20 left-6 bg-white border border-gray-200 rounded-2xl shadow-xl p-2 w-64 z-50 space-y-1">
              <button
                onClick={() => {
                  setShowAttachMenu(false);
                  handleSendMessage('Ispeziona il mio schermo attuale e dimmi quali finestre vedi aperte.');
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-xl cursor-pointer"
              >
                <Camera className="w-4 h-4 text-orange-500" />
                <span>Invia Screenshot attuale al Bot</span>
              </button>
              <button
                onClick={() => {
                  setShowAttachMenu(false);
                  fileInputRef.current?.click();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-xl cursor-pointer"
              >
                <FolderOpen className="w-4 h-4 text-blue-500" />
                <span>Allega percorso file dal PC</span>
              </button>
            </div>
          )}

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                setInputText((prev) => `${prev} [File: ${f.name}] `);
              }
            }}
          />

          <div className="flex items-center gap-2 bg-[#F8F8F7] border border-gray-300 rounded-full px-3 py-2 focus-within:border-orange-500 focus-within:ring-2 focus-within:ring-orange-100">
            <button
              onClick={() => setShowAttachMenu((v) => !v)}
              style={{ WebkitAppRegion: 'no-drag' }}
              className="p-1.5 rounded-full hover:bg-gray-200 text-gray-600 cursor-pointer"
              title="Azioni rapide e allegati"
            >
              <Plus className="w-5 h-5" />
            </button>
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder={`Scrivi un messaggio a ${activeChat?.title || 'Chief'}... (es. chiedi una roadmap e falla incollare da @builder su Antigravity)`}
              className="flex-1 bg-transparent text-sm focus:outline-none text-gray-900"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isSending || !inputText.trim()}
              className="p-2 rounded-full bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-40 cursor-pointer"
            >
              {isSending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </main>

      {showNewModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-3xl p-6 w-[460px] shadow-2xl border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-base">Crea in CoworkerOS</h3>
              <button onClick={() => setShowNewModal(false)} className="p-1 hover:bg-gray-100 rounded-full">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex gap-2 mb-4 bg-gray-100 p-1 rounded-xl">
              <button
                onClick={() => setNewModalTab('chat')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg ${
                  newModalTab === 'chat' ? 'bg-white shadow-sm' : 'text-gray-600'
                }`}
              >
                Nuova Stanza Team
              </button>
              <button
                onClick={() => setNewModalTab('bot')}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg ${
                  newModalTab === 'bot' ? 'bg-white shadow-sm' : 'text-gray-600'
                }`}
              >
                Nuovo Coworker Bot
              </button>
            </div>

            {newModalTab === 'chat' ? (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-gray-600">Nome Stanza</label>
                  <input
                    type="text"
                    value={newChatTitle}
                    onChange={(e) => setNewChatTitle(e.target.value)}
                    placeholder="es. Antigravity Automation Crew"
                    className="w-full mt-1 px-3 py-2 border rounded-xl text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-gray-600">Seleziona Coworkers</label>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {bots.map((b) => {
                      const checked = selectedBotIds.includes(b.id);
                      return (
                        <button
                          key={b.id}
                          onClick={() =>
                            setSelectedBotIds((prev) =>
                              checked ? prev.filter((x) => x !== b.id) : [...prev, b.id]
                            )
                          }
                          className={`flex items-center gap-2 p-2 rounded-xl border text-left text-xs ${
                            checked ? 'border-emerald-500 bg-emerald-50/50' : 'border-gray-200'
                          }`}
                        >
                          <BlobAvatar shape={b.shape} color={b.color} size={24} />
                          <span className="font-semibold">{b.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <button
                  onClick={handleCreateChat}
                  className="w-full py-2.5 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800"
                >
                  Crea Stanza
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-center py-2">
                  <BlobAvatar shape={newBotShape} color={newBotColor} size={64} status="working" />
                </div>
                <input
                  type="text"
                  value={newBotName}
                  onChange={(e) => setNewBotName(e.target.value)}
                  placeholder="Nome del Bot (es. QA Tester)"
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                />
                <input
                  type="text"
                  value={newBotRole}
                  onChange={(e) => setNewBotRole(e.target.value)}
                  placeholder="Ruolo (es. Debugger & Automation)"
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                />
                <textarea
                  value={newBotPrompt}
                  onChange={(e) => setNewBotPrompt(e.target.value)}
                  placeholder="System Prompt..."
                  rows={2}
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                />
                <div className="flex gap-2">
                  {['squircle', 'circle', 'triangle', 'cloud', 'cylinder', 'drop'].map((sh) => (
                    <button
                      key={sh}
                      onClick={() => setNewBotShape(sh)}
                      className={`px-2 py-1 text-[11px] rounded-lg border ${
                        newBotShape === sh ? 'bg-gray-900 text-white' : 'bg-gray-50'
                      }`}
                    >
                      {sh}
                    </button>
                  ))}
                </div>
                <button
                  onClick={handleCreateBot}
                  className="w-full py-2.5 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800"
                >
                  Crea Coworker
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-3xl p-6 w-[440px] shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-orange-500" />
                <h3 className="font-bold text-base">Impostazioni Gemini API</h3>
              </div>
              <button onClick={() => setShowSettingsModal(false)} className="p-1 hover:bg-gray-100 rounded-full">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Chiave attuale: <b>{maskedKey || 'Configurata in .env'}</b>. Modello attivo: <b>gemini-3.8-flash</b> (con fallback automatico a <b>gemini-2.5-flash</b>).
            </p>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder="Incolla nuova GEMINI_API_KEY..."
              className="w-full px-3 py-2.5 border rounded-xl text-sm mb-4"
            />
            <button
              onClick={handleSaveApiKey}
              className="w-full py-2.5 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800"
            >
              Salva e Ricarica Motore
            </button>
          </div>
        </div>
      )}

      {showInspectorModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-6">
          <div className="bg-white rounded-3xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-base">Live Monitor & Windows 11 Inspector (2880x1920 HiDPI)</h3>
                <p className="text-xs text-gray-500">
                  Metodo cattura attivo: <b>{inspectorData?.capture_method || 'In corso...'}</b> â€¢ Risoluzione fisica: <b>{inspectorData?.screen_width}x{inspectorData?.screen_height}</b>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={openInspector}
                  className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-xl text-xs font-semibold"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingInspector ? 'animate-spin' : ''}`} />
                  Aggiorna
                </button>
                <button onClick={() => setShowInspectorModal(false)} className="p-1.5 hover:bg-gray-100 rounded-full">
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {inspectorData?.screenshot_b64 && (
              <div className="rounded-2xl overflow-hidden border border-gray-300 bg-gray-950 mb-4">
                <img
                  src={`data:image/jpeg;base64,${inspectorData.screenshot_b64}`}
                  alt="Live Screen"
                  className="w-full max-h-[55vh] object-contain mx-auto"
                />
              </div>
            )}

            <div>
              <h4 className="text-xs font-bold uppercase text-gray-500 mb-2">
                Finestre Rilevate ({inspectorWindows.length})
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {inspectorWindows.map((w, idx) => (
                  <span key={idx} className="px-2.5 py-1 bg-gray-100 rounded-lg text-xs text-gray-800">
                    {w}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


--- FILE: \frontend\src\components\BlobAvatar.jsx ---
import React from 'react';
import { motion } from 'framer-motion';
import { DEFAULT_BOT_PILE } from './blobPresets.js';

/**
 * Returns the base center coordinate (cx, cy) for the eyes in a 100x100 viewBox
 * depending on the blob shape geometry.
 */
function getBaseEyePosition(shape) {
  switch (shape) {
    case 'drop':
      // The drop is fat on bottom-left and tapers to top-right
      return { x: 38, y: 58 };
    case 'triangle':
      // Triangle narrows at the apex; center-belly is slightly lower
      return { x: 50, y: 50 };
    case 'cylinder':
      return { x: 52, y: 46 };
    case 'cloud':
    case 'squircle':
    case 'circle':
    default:
      // Iconic slightly off-center Grok mascot placement
      return { x: 55, y: 45 };
  }
}

/**
 * Directional offsets for where the eyes look.
 */
const LOOK_OFFSETS = {
  right: { x: 5, y: 0 },
  left: { x: -5, y: 0 },
  up: { x: 0, y: -4 },
  down: { x: 0, y: 4 },
  center: { x: 0, y: 0 },
};

/**
 * Renders the SVG shape path based on the shape prop.
 */
function BlobShape({ shape, color }) {
  switch (shape) {
    case 'squircle':
      return (
        <rect
          x="8"
          y="8"
          width="84"
          height="84"
          rx="28"
          fill={color}
        />
      );

    case 'triangle':
      return (
        <path
          d="M50 10 C62 10, 90 68, 86 82 C82 94, 18 94, 14 82 C10 68, 38 10, 50 10 Z"
          fill={color}
        />
      );

    case 'cloud':
      return (
        <path
          d="M 81.2 32.0 A 22 22 0 0 1 81.2 68.0 A 22 22 0 0 1 50.0 86.0 A 22 22 0 0 1 18.8 68.0 A 22 22 0 0 1 18.8 32.0 A 22 22 0 0 1 50.0 14.0 A 22 22 0 0 1 81.2 32.0 Z"
          fill={color}
        />
      );

    case 'cylinder':
      return (
        <rect
          x="14"
          y="10"
          width="72"
          height="80"
          rx="22"
          fill={color}
        />
      );

    case 'drop':
      return (
        <path
          d="M 76 16 C 82 22, 88 44, 84 64 C 80 80, 64 90, 44 90 C 24 90, 12 78, 12 58 C 12 38, 28 22, 52 14 C 64 10, 72 12, 76 16 Z"
          fill={color}
        />
      );

    case 'circle':
    default:
      return (
        <circle
          cx="50"
          cy="50"
          r="44"
          fill={color}
        />
      );
  }
}

/**
 * BlobAvatar Component
 * Playful, animated vector mascot inspired by Grok.
 */
export function BlobAvatar({
  shape = 'circle',
  color = '#FF5C35',
  size = 40,
  status = 'idle',
  tilt = 0,
  lookDirection = 'right',
  className = '',
  onClick,
}) {
  // Base tilt compensation (cylinders lean 15 deg by default)
  const effectiveTilt = (Number(tilt) || 0) + (shape === 'cylinder' ? 15 : 0);

  // Look direction & eye coordinates calculation
  const baseEye = getBaseEyePosition(shape);
  const lookOffset = LOOK_OFFSETS[lookDirection] || LOOK_OFFSETS.right;
  const targetEyeX = baseEye.x + lookOffset.x;
  const targetEyeY = baseEye.y + lookOffset.y;

  // Active status checks
  const isBusy = status === 'working' || status === 'typing';
  const isDone = status === 'done';

  // Dimension formatting (handles numbers, px, rem, or Tailwind classes)
  const numericSize =
    typeof size === 'number'
      ? size
      : !isNaN(Number(size))
      ? Number(size)
      : null;

  const styleDimension =
    numericSize !== null
      ? { width: `${numericSize}px`, height: `${numericSize}px` }
      : typeof size === 'string' && /px|rem|em|%|vw|vh/.test(size)
      ? { width: size, height: size }
      : undefined;

  // Animation variants for the outer body group
  const bodyAnimation = isBusy
    ? {
        rotate: [effectiveTilt - 5, effectiveTilt + 5, effectiveTilt - 5],
        y: [0, -1.5, 0],
      }
    : isDone
    ? {
        rotate: [effectiveTilt, effectiveTilt - 4, effectiveTilt + 4, effectiveTilt],
        scale: [1, 1.08, 0.96, 1],
        y: [0, -5, 1, 0],
      }
    : {
        rotate: effectiveTilt,
        y: [0, -1.5, 0],
      };

  const bodyTransition = isBusy
    ? {
        repeat: Infinity,
        duration: 1.2,
        ease: 'easeInOut',
      }
    : isDone
    ? {
        duration: 0.6,
        ease: 'easeOut',
      }
    : {
        repeat: Infinity,
        duration: 3.5,
        ease: 'easeInOut',
      };

  // Eyes animation (curious scanning left/right when busy)
  const eyeGroupAnimation = isBusy
    ? {
        x: [targetEyeX - 4, targetEyeX + 5, targetEyeX - 2, targetEyeX],
        y: targetEyeY,
      }
    : {
        x: targetEyeX,
        y: targetEyeY,
      };

  const eyeGroupTransition = isBusy
    ? {
        repeat: Infinity,
        duration: 1.6,
        ease: 'easeInOut',
      }
    : {
        type: 'spring',
        stiffness: 280,
        damping: 20,
      };

  return (
    <motion.svg
      viewBox="0 0 100 100"
      width={numericSize || undefined}
      height={numericSize || undefined}
      style={styleDimension}
      className={`inline-block select-none overflow-visible filter drop-shadow-[0_4px_8px_rgba(0,0,0,0.12)] ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
      whileHover={onClick ? { scale: 1.08 } : undefined}
      whileTap={onClick ? { scale: 0.94 } : undefined}
      role="img"
      aria-label={`${shape} mascot in ${status} status`}
    >
      {/* Animated Body Group */}
      <motion.g
        style={{ transformOrigin: '50px 50px' }}
        animate={bodyAnimation}
        transition={bodyTransition}
      >
        {/* Vector Mascot Silhouette */}
        <BlobShape shape={shape} color={color} />

        {/* Eye Cluster Group */}
        <motion.g
          animate={eyeGroupAnimation}
          transition={eyeGroupTransition}
        >
          {/* Natural Grok Pill Angle (-11deg) */}
          <g transform="rotate(-11)">
            {/* Periodic Blink Animation Container */}
            <motion.g
              animate={{ scaleY: [1, 0.08, 1] }}
              transition={{
                duration: 0.18,
                times: [0, 0.5, 1],
                repeat: Infinity,
                repeatDelay: 3.5,
                ease: 'easeInOut',
              }}
              style={{ transformOrigin: '0px 0px' }}
            >
              {/* Left Eye Pill */}
              <rect
                x="-11.5"
                y="-11"
                width="9"
                height="22"
                rx="4.5"
                fill="#FFFFFF"
              />
              {/* Right Eye Pill */}
              <rect
                x="2.5"
                y="-11"
                width="9"
                height="22"
                rx="4.5"
                fill="#FFFFFF"
              />
            </motion.g>
          </g>
        </motion.g>
      </motion.g>
    </motion.svg>
  );
}

/**
 * BotPile Component
 * Stacks a playful pile/cluster of Grok companion bots overlapping like stickers.
 */
export function BotPile({
  bots = DEFAULT_BOT_PILE,
  className = '',
  onBotClick,
}) {
  const botList = bots && bots.length > 0 ? bots : DEFAULT_BOT_PILE;

  return (
    <div
      className={`relative inline-flex items-end justify-center select-none -space-x-4 sm:-space-x-5 py-3 px-2 ${className}`}
    >
      {botList.map((bot, index) => {
        const isInteractive = Boolean(onBotClick);
        return (
          <motion.div
            key={bot.id || `bot-pile-${index}`}
            className={`relative transition-transform ${
              isInteractive ? 'cursor-pointer' : ''
            }`}
            style={{ zIndex: index + 1 }}
            whileHover={{
              y: -8,
              scale: 1.14,
              zIndex: 40,
              transition: { type: 'spring', stiffness: 350, damping: 18 },
            }}
            whileTap={isInteractive ? { scale: 0.94 } : undefined}
            onClick={() => onBotClick?.(bot, index)}
          >
            <BlobAvatar
              shape={bot.shape}
              color={bot.color}
              size={bot.size}
              tilt={bot.tilt}
              lookDirection={bot.lookDirection}
              status={bot.status || 'idle'}
              className="drop-shadow-md"
            />
          </motion.div>
        );
      })}
    </div>
  );
}

export default BlobAvatar;


--- FILE: \frontend\src\components\blobPresets.js ---
/**
 * blobPresets.js
 * Design system palette, presets, and utility helpers for Grok Blob Mascots.
 */

export const BLOB_COLORS = {
  orange: '#FF5C35', // Grok Signature Warm Orange
  coral: '#FF6B4A',  // Punchy Vivid Coral
  sky: '#358BFF',    // Electric Sky Blue
  blue: '#3B82F6',   // Bold Primary Blue
  yellow: '#FFC700', // Grok Vivid Yellow
  lime: '#EAB308',   // Playful Lime Gold
  purple: '#9B51E0', // Deep Creative Purple
  violet: '#A855F7', // Bright Neon Violet
  mint: '#10B981',   // Fresh Mint Green
  green: '#27AE60',  // Emerald Green
  pink: '#FF76A5',   // Sweet Candy Pink
  rose: '#F43F5E',   // Vivid Rose Red
  dark: '#2D3748',   // Sleek Slate / Grok Dark
};

export const BLOB_COLOR_LIST = Object.values(BLOB_COLORS);

export const BLOB_SHAPES = [
  'circle',
  'squircle',
  'triangle',
  'cloud',
  'cylinder',
  'drop',
];

export const LOOK_DIRECTIONS = ['right', 'left', 'center', 'up', 'down'];

/**
 * Default sticker pile representing 6 playful companion bots.
 */
export const DEFAULT_BOT_PILE = [
  {
    id: 'bot-rusty',
    name: 'Rusty',
    shape: 'squircle',
    color: '#FF6B4A',
    size: 70,
    tilt: -18,
    lookDirection: 'right',
    status: 'idle',
  },
  {
    id: 'bot-volt',
    name: 'Volt',
    shape: 'circle',
    color: '#3B82F6',
    size: 85,
    tilt: 14,
    lookDirection: 'left',
    status: 'idle',
  },
  {
    id: 'bot-sunny',
    name: 'Sunny',
    shape: 'triangle',
    color: '#EAB308',
    size: 60,
    tilt: 24,
    lookDirection: 'up',
    status: 'idle',
  },
  {
    id: 'bot-nebula',
    name: 'Nebula',
    shape: 'drop',
    color: '#A855F7',
    size: 75,
    tilt: -8,
    lookDirection: 'right',
    status: 'idle',
  },
  {
    id: 'bot-sprout',
    name: 'Sprout',
    shape: 'cylinder',
    color: '#10B981',
    size: 55,
    tilt: 10,
    lookDirection: 'left',
    status: 'idle',
  },
  {
    id: 'bot-puff',
    name: 'Puff',
    shape: 'cloud',
    color: '#F43F5E',
    size: 65,
    tilt: -12,
    lookDirection: 'right',
    status: 'idle',
  },
];

/**
 * Pre-configured bot roles for agentic workflows
 */
export const ROLE_PRESETS = {
  assistant: {
    name: 'Assistant',
    shape: 'circle',
    color: '#FF5C35',
    tilt: 0,
    lookDirection: 'right',
  },
  coder: {
    name: 'Coder',
    shape: 'squircle',
    color: '#358BFF',
    tilt: -6,
    lookDirection: 'left',
  },
  architect: {
    name: 'Architect',
    shape: 'cylinder',
    color: '#9B51E0',
    tilt: 15,
    lookDirection: 'center',
  },
  reviewer: {
    name: 'Reviewer',
    shape: 'triangle',
    color: '#10B981',
    tilt: 8,
    lookDirection: 'up',
  },
  creative: {
    name: 'Creative',
    shape: 'cloud',
    color: '#FF76A5',
    tilt: -10,
    lookDirection: 'right',
  },
  explorer: {
    name: 'Explorer',
    shape: 'drop',
    color: '#FFC700',
    tilt: 12,
    lookDirection: 'up',
  },
};

/**
 * Returns a randomized cute blob configuration.
 */
export function getRandomBlob(overrides = {}) {
  const randomColor = BLOB_COLOR_LIST[Math.floor(Math.random() * BLOB_COLOR_LIST.length)];
  const randomShape = BLOB_SHAPES[Math.floor(Math.random() * BLOB_SHAPES.length)];
  const randomDirection = LOOK_DIRECTIONS[Math.floor(Math.random() * LOOK_DIRECTIONS.length)];
  const randomTilt = Math.floor(Math.random() * 32) - 16; // -16 to +16 deg

  return {
    shape: randomShape,
    color: randomColor,
    tilt: randomTilt,
    lookDirection: randomDirection,
    status: 'idle',
    size: 48,
    ...overrides,
  };
}

/**
 * Retrieve a preset configuration by role name.
 */
export function getBotByRole(role, overrides = {}) {
  const base = ROLE_PRESETS[role] || ROLE_PRESETS.assistant;
  return { ...base, ...overrides };
}


--- FILE: \frontend\src\components\ChatArea.jsx ---
import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Monitor,
  Share2,
  MoreHorizontal,
  Plus,
  ArrowUp,
  Mic,
  Copy,
  Check,
  Camera,
  FileUp,
  ImageIcon,
} from 'lucide-react';
import BlobAvatar from './BlobAvatar';
import ComputerWorkingCard from './ComputerWorkingCard';
import { getLiveScreenshot } from '../services/api';

/**
 * Lightweight safe markdown renderer
 */
function MarkdownContent({ content = '' }) {
  const [copiedCodeIdx, setCopiedCodeIdx] = useState(null);

  if (!content) return null;

  const copyToClipboard = (text, idx) => {
    navigator.clipboard?.writeText(text);
    setCopiedCodeIdx(idx);
    setTimeout(() => setCopiedCodeIdx(null), 1800);
  };

  // Split by code blocks first
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-2 text-[14.5px] leading-relaxed text-gray-800 break-words font-sans">
      {parts.map((part, index) => {
        if (part.startsWith('```') && part.endsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const firstLine = lines[0].trim();
          const hasLang = !firstLine.includes(' ') && firstLine.length > 0 && firstLine.length < 15;
          const language = hasLang ? firstLine : '';
          const codeBody = hasLang ? lines.slice(1).join('\n') : lines.join('\n');

          return (
            <div
              key={index}
              className="my-2.5 rounded-xl bg-[#1E1E24] text-gray-200 border border-gray-800/80 overflow-hidden font-mono text-xs shadow-xs"
            >
              <div className="flex items-center justify-between px-3.5 py-1.5 bg-[#17171C] border-b border-gray-800 text-[11px] text-gray-400">
                <span>{language || 'code'}</span>
                <button
                  type="button"
                  onClick={() => copyToClipboard(codeBody, index)}
                  className="flex items-center gap-1 hover:text-white transition-colors"
                >
                  {copiedCodeIdx === index ? (
                    <>
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span className="text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
              <pre className="p-3.5 overflow-x-auto leading-5 text-[12px]">{codeBody}</pre>
            </div>
          );
        }

        // Normal text formatting: bullet lists, bold, inline code, paragraphs
        const paragraphs = part.split(/\n\n+/);
        return paragraphs.map((para, pIdx) => {
          const lines = para.split('\n');
          return (
            <p key={`${index}-${pIdx}`} className="leading-relaxed">
              {lines.map((line, lIdx) => {
                const isBullet = line.trim().startsWith('- ') || line.trim().startsWith('* ');
                const isNumbered = /^\d+\.\s/.test(line.trim());

                // Parse bold and inline code
                const formattedSegments = line
                  .replace(/^[*-]\s+/, 'â€¢ ')
                  .split(/(\*\*.*?\*\*|`.*?`)/g)
                  .map((seg, sIdx) => {
                    if (seg.startsWith('**') && seg.endsWith('**')) {
                      return (
                        <strong key={sIdx} className="font-semibold text-gray-900">
                          {seg.slice(2, -2)}
                        </strong>
                      );
                    }
                    if (seg.startsWith('`') && seg.endsWith('`')) {
                      return (
                        <code
                          key={sIdx}
                          className="px-1.5 py-0.5 rounded-md bg-gray-100 text-pink-600 font-mono text-[12.5px] border border-gray-200/60"
                        >
                          {seg.slice(1, -1)}
                        </code>
                      );
                    }
                    return seg;
                  });

                return (
                  <span
                    key={lIdx}
                    className={`block ${isBullet || isNumbered ? 'pl-2 text-gray-800' : ''}`}
                  >
                    {formattedSegments}
                  </span>
                );
              })}
            </p>
          );
        });
      })}
    </div>
  );
}

/**
 * Animated Bot Pile for Empty Chat State
 */
function BotPile({ bots = [] }) {
  const displayBots = bots.slice(0, 4);

  return (
    <div className="flex flex-col items-center justify-center p-6 text-center select-none">
      {/* Playful overlapping Avatar Stack */}
      <div className="relative flex items-center justify-center h-24 mb-4">
        {displayBots.map((b, idx) => {
          const offsets = [
            { x: -35, y: 0, rotate: -8 },
            { x: -10, y: -12, rotate: 4 },
            { x: 18, y: -4, rotate: -4 },
            { x: 38, y: 8, rotate: 10 },
          ];
          const offset = offsets[idx] || { x: 0, y: 0, rotate: 0 };

          return (
            <motion.div
              key={b.id || idx}
              initial={{ scale: 0, y: 20 }}
              animate={{ scale: 1, y: offset.y, x: offset.x, rotate: offset.rotate }}
              transition={{
                delay: idx * 0.1,
                type: 'spring',
                stiffness: 260,
                damping: 20,
              }}
              className="absolute ring-4 ring-white rounded-full shadow-md"
              style={{ zIndex: 10 + idx }}
            >
              <BlobAvatar
                shape={b.shape || 'circle'}
                color={b.color || '#00BA88'}
                size={54}
                status={idx === 0 ? 'working' : 'idle'}
              />
            </motion.div>
          );
        })}
      </div>

      <motion.h3
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-xl font-bold text-gray-900 tracking-tight"
      >
        Welcome to CoworkerOS
      </motion.h3>
      <motion.p
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.38 }}
        className="text-sm text-gray-500 max-w-sm mt-1 mb-6 leading-relaxed"
      >
        Your autonomous desktop coworker team. Chat, orchestrate multi-bot pipelines, and let Builder control your PC directly.
      </motion.p>
    </div>
  );
}

export default function ChatArea({
  activeChat,
  messages = [],
  availableBots = [],
  activeWorkingBot = null, // { botId, name, status, activity }
  onSendMessage,
  onOpenDesktopView,
}) {
  const [inputText, setInputText] = useState('');
  const [isAttachMenuOpen, setIsAttachMenuOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const attachMenuRef = useRef(null);

  // Auto-scroll to bottom on messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeWorkingBot]);

  // Focus input on chat change
  useEffect(() => {
    inputRef.current?.focus();
  }, [activeChat?.id]);

  // Close attach menu on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (attachMenuRef.current && !attachMenuRef.current.contains(event.target)) {
        setIsAttachMenuOpen(false);
      }
    }
    if (isAttachMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isAttachMenuOpen]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed) return;
    onSendMessage?.(trimmed);
    setInputText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsAttachMenuOpen(false);

    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const b64 = event.target.result;
        onSendMessage?.(`Allegata immagine: ${file.name}`, {
          title: file.name,
          status: 'done',
          screenshot_b64: b64,
          subtitle: `File caricato: ${file.name} (${Math.round(file.size / 1024)} KB)`,
        });
      };
      reader.readAsDataURL(file);
    } else {
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target.result;
        setInputText((prev) => (prev ? `${prev}\n\n[File: ${file.name}]\n${text}` : `[File: ${file.name}]\n${text}`));
        inputRef.current?.focus();
      };
      reader.readAsText(file);
    }
    e.target.value = '';
  };

  const handleCaptureAndSendScreenshot = async () => {
    setIsAttachMenuOpen(false);
    try {
      const shot = await getLiveScreenshot();
      if (shot && shot.screenshot_b64) {
        onSendMessage?.('Ecco lo screenshot live del mio PC:', {
          title: 'Screenshot PC Live',
          status: 'done',
          screenshot_b64: shot.screenshot_b64,
          x: 50,
          y: 50,
          subtitle: `Schermo catturato in tempo reale (${shot.screen_width || 1920}x${shot.screen_height || 1080})`,
        });
      }
    } catch (err) {
      alert('Impossibile catturare lo screenshot: ' + err.message);
    }
  };

  // Find participants bot objects
  const participantsList = (activeChat?.participants || []).map((botId) => {
    return (
      availableBots.find((b) => b.id === botId) || {
        id: botId,
        name: botId.charAt(0).toUpperCase() + botId.slice(1),
        shape: 'circle',
        color: '#00BA88',
        role: 'Coworker',
      }
    );
  });

  const chatTitle = activeChat?.title || 'CoworkerOS Room';
  const isGroup = activeChat?.is_group === 1 || (activeChat?.participants?.length || 0) > 1;

  // Quick suggestion pills for empty state
  const quickPrompts = [
    'Chiedi a Chief di creare una roadmap con Architect e incollarla su Antigravity con Builder',
    'Scout, analizza le librerie open source per agenti autonomi e prepara una sintesi',
    'Builder, porta in primo piano Antigravity e verifica che la chat risponda ai comandi',
  ];

  return (
    <div className="flex-1 flex flex-col h-full bg-[#FFFFFF] relative overflow-hidden font-sans">
      {/* 1. TOP BAR */}
      <div className="h-14 border-b border-gray-100 flex items-center justify-between px-6 bg-white/80 backdrop-blur-md z-10 shrink-0 select-none" style={{ WebkitAppRegion: 'drag' }}>
        {/* Left: Chat Title & Bot Avatars */}
        <div className="flex items-center gap-3 min-w-0" style={{ WebkitAppRegion: 'no-drag' }}>
          {/* Overlapping or Single Bot Avatar with Pop-in animation */}
          <div className="flex items-center -space-x-2 shrink-0">
            <AnimatePresence>
              {participantsList.map((bot, idx) => (
                <motion.div
                  key={bot.id}
                  initial={{ scale: 0, opacity: 0 }}
                  animate={{ scale: [0, 1.15, 1], opacity: 1 }}
                  exit={{ scale: 0, opacity: 0 }}
                  transition={{
                    duration: 0.35,
                    delay: idx * 0.05,
                    ease: 'easeOut',
                  }}
                  className="rounded-full ring-2 ring-white shadow-xs relative"
                  style={{ zIndex: 20 - idx }}
                  title={`${bot.name} (${bot.role})`}
                >
                  <BlobAvatar
                    shape={bot.shape || 'circle'}
                    color={bot.color || '#00BA88'}
                    size={30}
                    status={activeWorkingBot?.botId === bot.id ? 'working' : 'idle'}
                    showStatus={false}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </div>

          <div className="min-w-0 flex flex-col justify-center">
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] font-semibold text-gray-900 truncate tracking-tight">
                {chatTitle}
              </h2>
              {isGroup && (
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                  Room
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400 truncate">
              {participantsList.length}{' '}
              {participantsList.length === 1 ? 'bot' : 'bots'} connected
              {activeWorkingBot ? ` â€¢ ${activeWorkingBot.name} is working...` : ' â€¢ Ready'}
            </p>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-1 text-gray-500" style={{ WebkitAppRegion: 'no-drag' }}>
          <button
            type="button"
            onClick={onOpenDesktopView}
            className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-800 transition-colors shadow-2xs mr-1"
            title="Apri Live PC & Screen Inspector"
          >
            <Monitor className="w-3.5 h-3.5 text-orange-600" />
            <span className="hidden sm:inline">Screen Inspector</span>
          </button>
          <button
            type="button"
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors"
            title="Share Room"
          >
            <Share2 className="w-4 h-4" />
          </button>
          <button
            type="button"
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors"
            title="Room Options"
          >
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 2. MESSAGES STREAM */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 ? (
          /* Empty Chat State */
          <div className="h-full flex flex-col items-center justify-center max-w-xl mx-auto py-8">
            <BotPile bots={participantsList.length ? participantsList : availableBots} />

            {/* Quick Prompt Suggestions */}
            <div className="w-full space-y-2 mt-2">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 text-center mb-1">
                Suggested Prompts
              </div>
              {quickPrompts.map((prompt, idx) => (
                <motion.button
                  key={idx}
                  whileHover={{ scale: 1.01, backgroundColor: '#FAF9F6' }}
                  whileTap={{ scale: 0.99 }}
                  onClick={() => {
                    setInputText(prompt);
                    inputRef.current?.focus();
                  }}
                  className="w-full text-left p-3 rounded-xl border border-gray-200/80 bg-white hover:border-gray-300 text-xs text-gray-700 shadow-2xs transition-all flex items-center justify-between group"
                >
                  <span className="leading-snug pr-2">{prompt}</span>
                  <span className="p-1 rounded-md bg-gray-100 text-gray-400 group-hover:bg-orange-100 group-hover:text-orange-600 transition-colors shrink-0">
                    <ArrowUp className="w-3 h-3 rotate-45" />
                  </span>
                </motion.button>
              ))}
            </div>
          </div>
        ) : (
          /* Render Messages */
          messages.map((msg, index) => {
            const isUser = msg.sender_id === 'user';
            const botData = !isUser
              ? availableBots.find((b) => b.id === msg.sender_id) || {
                  name: msg.sender_name || 'Bot',
                  color: '#00BA88',
                  shape: 'circle',
                }
              : null;

            // Parse action card if present
            let actionData = null;
            if (msg.action_card_json) {
              if (typeof msg.action_card_json === 'object') {
                actionData = msg.action_card_json;
              } else {
                try {
                  actionData = JSON.parse(msg.action_card_json);
                } catch {
                  actionData = null;
                }
              }
            }

            const formattedTime = msg.timestamp
              ? new Date(msg.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : '';

            return (
              <motion.div
                key={msg.id || index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22 }}
                className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {/* Bot Avatar on Left */}
                {!isUser && (
                  <div className="shrink-0 pt-0.5">
                    <BlobAvatar
                      shape={botData.shape || 'circle'}
                      color={botData.color || '#00BA88'}
                      size={34}
                      status={activeWorkingBot?.botId === msg.sender_id ? 'working' : 'idle'}
                      showStatus={false}
                    />
                  </div>
                )}

                {/* Message Body */}
                <div
                  className={`flex flex-col ${
                    isUser ? 'items-end max-w-lg sm:max-w-xl' : 'items-start max-w-xl sm:max-w-2xl'
                  }`}
                >
                  {/* Sender Header */}
                  <div className="flex items-center gap-2 mb-1 px-1">
                    <span
                      className={`text-xs font-semibold ${
                        isUser ? 'text-gray-600' : 'text-gray-900'
                      }`}
                      style={{ color: !isUser && botData?.color ? botData.color : undefined }}
                    >
                      {isUser ? 'You' : botData?.name || msg.sender_name}
                    </span>
                    {formattedTime && (
                      <span className="text-[10px] text-gray-400 font-normal">
                        {formattedTime}
                      </span>
                    )}
                  </div>

                  {/* Text Content */}
                  {msg.content && (
                    <div
                      className={`rounded-2xl px-4 py-2.5 text-sm ${
                        isUser
                          ? 'bg-[#1C1917] text-white rounded-tr-xs shadow-xs'
                          : 'bg-[#F7F7F5] text-gray-900 rounded-tl-xs border border-gray-200/70 shadow-2xs'
                      }`}
                    >
                      {isUser ? (
                        <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                      ) : (
                        <MarkdownContent content={msg.content} />
                      )}
                    </div>
                  )}

                  {/* Computer Working Card */}
                  {actionData && (
                    <div className="w-full">
                      <ComputerWorkingCard
                        actionData={actionData}
                        onOpenInspector={onOpenDesktopView}
                      />
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 3. LIVE WORKING INDICATOR ABOVE INPUT */}
      <AnimatePresence>
        {activeWorkingBot && activeWorkingBot.status === 'working' && (
          <motion.div
            initial={{ opacity: 0, y: 10, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: 10, height: 0 }}
            transition={{ duration: 0.2 }}
            className="px-6 pb-2"
          >
            <div className="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-amber-50/90 border border-amber-200/80 text-amber-900 text-xs shadow-xs">
              <BlobAvatar
                shape="circle"
                color="#FF6B00"
                size={22}
                status="working"
                showStatus={false}
              />
              <span className="font-medium animate-pulse">
                {activeWorkingBot.activity || `${activeWorkingBot.name || 'Bot'} is working...`}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 4. APPLE / GROK-STYLE PILL INPUT BAR */}
      <div className="p-4 sm:px-6 sm:pb-6 bg-white shrink-0 relative">
        {/* Hidden File Input for Attachment */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
        />

        {/* Attachment Quick Menu Popup */}
        <AnimatePresence>
          {isAttachMenuOpen && (
            <motion.div
              ref={attachMenuRef}
              initial={{ opacity: 0, scale: 0.95, y: 6 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 6 }}
              transition={{ duration: 0.15 }}
              className="absolute left-6 bottom-20 bg-white/95 backdrop-blur-md rounded-2xl shadow-xl border border-gray-200/90 p-1.5 z-40 text-xs w-64 space-y-0.5"
            >
              <button
                type="button"
                onClick={() => {
                  setIsAttachMenuOpen(false);
                  fileInputRef.current?.click();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-gray-700 hover:text-gray-900 hover:bg-gray-100 transition font-medium text-left"
              >
                <div className="w-6 h-6 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                  <FileUp className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Allega File / Immagine</div>
                  <div className="text-[10px] text-gray-400">Carica codice, log o screenshot</div>
                </div>
              </button>

              <button
                type="button"
                onClick={handleCaptureAndSendScreenshot}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-gray-700 hover:text-gray-900 hover:bg-gray-100 transition font-medium text-left"
              >
                <div className="w-6 h-6 rounded-lg bg-orange-100 text-orange-600 flex items-center justify-center shrink-0">
                  <Camera className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Invia Screenshot Live</div>
                  <div className="text-[10px] text-gray-400">Scatta e invia lo schermo PC reale</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsAttachMenuOpen(false);
                  onOpenDesktopView?.();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-gray-700 hover:text-gray-900 hover:bg-gray-100 transition font-medium text-left"
              >
                <div className="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center shrink-0">
                  <Monitor className="w-3.5 h-3.5" />
                </div>
                <div>
                  <div className="font-semibold text-gray-900">Live PC Inspector</div>
                  <div className="text-[10px] text-gray-400">Ispeziona schermo e finestre attive</div>
                </div>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        <form
          onSubmit={handleSubmit}
          className="relative flex items-center bg-[#F3F3F1] hover:bg-[#EFEFEA] focus-within:bg-white border border-gray-200/90 focus-within:border-gray-400 focus-within:ring-2 focus-within:ring-black/5 rounded-full px-3 py-2 transition-all shadow-xs"
          style={{ WebkitAppRegion: 'no-drag' }}
        >
          {/* Plus Add Button with Quick Menu */}
          <button
            type="button"
            onClick={() => setIsAttachMenuOpen((prev) => !prev)}
            style={{ WebkitAppRegion: 'no-drag' }}
            className={`w-8 h-8 rounded-full flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-gray-200/60 transition-colors shrink-0 mr-1 cursor-pointer ${
              isAttachMenuOpen ? 'bg-gray-200 text-gray-900' : ''
            }`}
            title="Allega file o scatta screenshot"
          >
            <Plus className="w-4 h-4" />
          </button>

          {/* Text Input */}
          <input
            ref={inputRef}
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Scrivi un messaggio a ${chatTitle}...`}
            className="flex-1 bg-transparent border-none outline-hidden text-sm text-gray-900 placeholder-gray-400 px-2 py-1 font-sans"
          />

          {/* Right Action: Send or Mic */}
          {inputText.trim().length > 0 ? (
            <motion.button
              type="submit"
              whileTap={{ scale: 0.92 }}
              className="w-8 h-8 rounded-full bg-black hover:bg-gray-800 text-white flex items-center justify-center transition-colors shadow-xs shrink-0"
              title="Send message"
            >
              <ArrowUp className="w-4 h-4" />
            </motion.button>
          ) : (
            <button
              type="button"
              className="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 transition-colors shrink-0"
              title="Voice Input"
            >
              <Mic className="w-4 h-4" />
            </button>
          )}
        </form>
      </div>
    </div>
  );
}


--- FILE: \frontend\src\components\ComputerWorkingCard.jsx ---
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Monitor,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  MousePointer2,
  Keyboard,
  Scroll,
  Sliders,
  ExternalLink,
} from 'lucide-react';

/**
 * ComputerWorkingCard renders a real physical OS action card
 * featuring real captured screenshots from tools_os.capture_screen_b64()
 * and live crosshair reticle. Clicking the card opens the Live PC Inspector.
 */
export default function ComputerWorkingCard({ actionData = {}, onOpenInspector }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Normalize action fields
  const title = actionData.title || 'Computer';
  const status = actionData.status || 'working'; // 'working' | 'done' | 'failed'
  const isWorking = status === 'working';
  const subtitle =
    actionData.subtitle ||
    (isWorking
      ? 'Interazione fisica con lo schermo del PC...'
      : 'Azione completata con successo sullo schermo');

  const x = typeof actionData.x === 'number' ? Math.max(5, Math.min(95, actionData.x)) : 50;
  const y = typeof actionData.y === 'number' ? Math.max(5, Math.min(95, actionData.y)) : 50;
  const actionType = actionData.action || 'click';
  const target = actionData.target || actionData.window_title || 'Schermo PC';
  const details = actionData.details || `Azione ${actionType} eseguita alle coordinate (x: ${Math.round(x)}%, y: ${Math.round(y)}%)`;
  const screenshotB64 = actionData.screenshot_b64;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="bg-[#F7F7F5] border border-gray-200/90 rounded-2xl p-4 max-w-xl my-2 shadow-sm font-sans cursor-pointer hover:border-gray-300 transition-all"
      onClick={() => onOpenInspector && onOpenInspector()}
    >
      {/* Top Header Row */}
      <div className="flex items-center justify-between">
        <div className="font-semibold text-gray-900 text-base flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-gray-200/70 text-gray-700">
            <Monitor className="w-4 h-4" />
          </span>
          <span>{title}</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Status Pill Badge */}
          {isWorking ? (
            <span className="bg-amber-100/90 text-amber-900 border border-amber-300/70 px-2.5 py-0.5 rounded-full text-xs font-medium flex items-center gap-1.5 shadow-2xs">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-600" />
              <span>Working</span>
            </span>
          ) : (
            <span className="bg-emerald-50 text-emerald-700 border border-emerald-200/80 px-2.5 py-0.5 rounded-full text-xs font-medium flex items-center gap-1.5 shadow-2xs">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Done</span>
            </span>
          )}

          <button
            type="button"
            className="p-1 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 transition"
            title="Apri Live PC & Screen Inspector"
            onClick={(e) => {
              e.stopPropagation();
              if (onOpenInspector) onOpenInspector();
            }}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Subtitle description */}
      <p className="text-sm text-gray-600 mt-1.5 mb-3 leading-relaxed">
        {subtitle}
      </p>

      {/* Screen Frame Container */}
      <div className="bg-gradient-to-tr from-stone-200 via-gray-200 to-stone-300 p-2 rounded-xl shadow-2xs border border-white/60">
        <div className="relative rounded-lg overflow-hidden bg-slate-900 border border-black/20 shadow-md aspect-video flex flex-col justify-between select-none">
          {screenshotB64 ? (
            /* Real Base64 Screenshot captured via mss */
            <div className="relative w-full h-full">
              <img
                src={
                  screenshotB64.startsWith('data:')
                    ? screenshotB64
                    : `data:image/jpeg;base64,${screenshotB64}`
                }
                alt="Live Desktop Capture"
                className="w-full h-full object-cover"
              />
            </div>
          ) : (
            /* Clean real monitor placeholder */
            <div className="w-full h-full flex flex-col items-center justify-center bg-gray-900 text-gray-300 gap-2 p-4 text-center">
              <Monitor className="w-8 h-8 text-orange-400 animate-pulse" />
              <div className="text-xs font-medium text-white">{target}</div>
              <p className="text-[11px] text-gray-400 max-w-xs">
                Clicca per aprire il Live PC &amp; Screen Inspector in tempo reale
              </p>
            </div>
          )}

          {/* Crosshair Reticle when coordinates are provided */}
          {typeof x === 'number' && typeof y === 'number' && (
            <div
              className="absolute z-30 pointer-events-none transform -translate-x-1/2 -translate-y-1/2"
              style={{ left: `${x}%`, top: `${y}%` }}
            >
              {/* Outer Pulsing Ping Ring */}
              <div className="w-10 h-10 rounded-full border-2 border-orange-500 animate-ping opacity-80 absolute -top-5 -left-5" />

              {/* Middle Glassy Concentric Circle */}
              <div className="w-7 h-7 rounded-full border-2 border-orange-500 bg-orange-500/25 shadow-lg flex items-center justify-center absolute -top-3.5 -left-3.5 backdrop-blur-xs">
                <div className="w-2 h-2 rounded-full bg-orange-600 shadow-sm" />
              </div>

              {/* Crosshair Lines */}
              <div className="w-10 h-[1.5px] bg-orange-500/80 absolute -top-[0.75px] -left-5" />
              <div className="h-10 w-[1.5px] bg-orange-500/80 absolute -top-5 -left-[0.75px]" />

              {/* Tooltip */}
              <div className="absolute left-4 -top-3 bg-gray-900/90 text-white font-sans text-[10px] font-medium px-2 py-0.5 rounded-md shadow-md border border-white/10 whitespace-nowrap flex items-center gap-1 backdrop-blur-xs">
                {actionType === 'click' && <MousePointer2 className="w-2.5 h-2.5 text-orange-400" />}
                {actionType === 'type' && <Keyboard className="w-2.5 h-2.5 text-orange-400" />}
                {actionType === 'scroll' && <Scroll className="w-2.5 h-2.5 text-orange-400" />}
                <span className="capitalize">{actionType}</span>
                <span className="text-gray-400 text-[9px]">
                  ({Math.round(x)}%, {Math.round(y)}%)
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Expandable Action Details */}
      <div className="mt-2.5 pt-2 border-t border-gray-200/60" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full flex items-center justify-between text-xs text-gray-500 hover:text-gray-800 transition-colors py-0.5"
        >
          <span className="flex items-center gap-1.5 font-medium">
            <Sliders className="w-3.5 h-3.5 text-gray-400" />
            Dettagli operazione PC
          </span>
          <span className="flex items-center gap-1 text-[11px] text-gray-400">
            {isExpanded ? 'Nascondi' : 'Mostra'}
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
        </button>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="mt-2 p-2.5 bg-white/80 border border-gray-200/70 rounded-xl text-xs space-y-1.5 text-gray-600 font-mono">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-gray-400 font-sans">Tipo azione:</span>
                  <span className="font-semibold text-gray-800 capitalize font-sans">{actionType}</span>
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-gray-400 font-sans">Finestra target:</span>
                  <span className="text-gray-700 truncate max-w-[240px]">{target}</span>
                </div>
                <div className="flex justify-between items-center text-[11px]">
                  <span className="text-gray-400 font-sans">Coordinate normalizzate:</span>
                  <span className="text-orange-600 font-semibold">x: {Math.round(x)}%, y: {Math.round(y)}%</span>
                </div>
                {details && (
                  <div className="pt-1.5 border-t border-gray-100 text-[10px] text-gray-500 font-sans leading-relaxed">
                    {details}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}


--- FILE: \frontend\src\components\CreateModal.jsx ---
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  X,
  MessageSquare,
  Sparkles,
  Check,
  Zap,
  Brain,
  Shield,
} from 'lucide-react';
import BlobAvatar from './BlobAvatar';

const SHAPES = [
  { id: 'circle', label: 'Circle' },
  { id: 'squircle', label: 'Squircle' },
  { id: 'triangle', label: 'Triangle' },
  { id: 'cloud', label: 'Cloud' },
  { id: 'cylinder', label: 'Cylinder' },
  { id: 'drop', label: 'Drop' },
];

const PRESET_COLORS = [
  '#00BA88', // Emerald
  '#FF6B00', // Grok Orange
  '#FF2E93', // Vibrant Pink
  '#FFB800', // Amber Yellow
  '#1D7AFC', // Azure Blue
  '#7C3AED', // Purple
  '#10B981', // Mint
  '#F43F5E', // Rose
];

export default function CreateModal({
  isOpen,
  onClose,
  initialTab = 'chat', // 'chat' | 'bot'
  availableBots = [],
  onCreateRoom,
  onCreateBot,
}) {
  const [activeTab, setActiveTab] = useState(initialTab);

  // --- TAB 1: NEW CHAT / ROOM STATE ---
  const [roomTitle, setRoomTitle] = useState('');
  const [selectedBotIds, setSelectedBotIds] = useState(['chief']);

  // --- TAB 2: NEW BOT STATE ---
  const [botName, setBotName] = useState('');
  const [botRole, setBotRole] = useState('');
  const [botSystemPrompt, setBotSystemPrompt] = useState('');
  const [botShape, setBotShape] = useState('circle');
  const [botColor, setBotColor] = useState('#00BA88');
  const [botEffort, setBotEffort] = useState('medium');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const toggleBotSelection = (botId) => {
    setSelectedBotIds((prev) => {
      if (prev.includes(botId)) {
        if (prev.length === 1) return prev; // Keep at least one
        return prev.filter((id) => id !== botId);
      }
      return [...prev, botId];
    });
  };

  const handleRoomSubmit = async (e) => {
    e.preventDefault();
    if (selectedBotIds.length === 0) return;

    setIsSubmitting(true);
    try {
      const title =
        roomTitle.trim() ||
        (selectedBotIds.length === 1
          ? availableBots.find((b) => b.id === selectedBotIds[0])?.name || 'Chat'
          : `Stanza con ${selectedBotIds.length} Coworker`);

      await onCreateRoom({
        title,
        participants: selectedBotIds,
        is_group: selectedBotIds.length > 1,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBotSubmit = async (e) => {
    e.preventDefault();
    if (!botName.trim()) return;

    setIsSubmitting(true);
    try {
      await onCreateBot({
        name: botName.trim(),
        role: botRole.trim() || 'AI Specialist',
        system_prompt:
          botSystemPrompt.trim() ||
          `Sei ${botName.trim()}. Rispondi in modo collaborativo e preciso.`,
        shape: botShape,
        color: botColor,
        effort: botEffort,
      });
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="bg-white rounded-3xl w-full max-w-lg shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header with Tabs */}
        <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1 bg-[#F4F4F2] p-1 rounded-2xl">
            <button
              type="button"
              onClick={() => setActiveTab('chat')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'chat'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span>Nuova Chat / Stanza</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('bot')}
              className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all ${
                activeTab === 'bot'
                  ? 'bg-white text-gray-900 shadow-xs'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-orange-500" />
              <span>Crea Nuovo Coworker</span>
            </button>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 hover:text-gray-900 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1">
          {activeTab === 'chat' ? (
            /* TAB 1: NUOVA CHAT / STANZA */
            <form onSubmit={handleRoomSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
                  Titolo Stanza (Opzionale)
                </label>
                <input
                  type="text"
                  value={roomTitle}
                  onChange={(e) => setRoomTitle(e.target.value)}
                  placeholder="es. Progetto Alpha o War Room"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-900 placeholder-gray-400 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400 transition"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    Seleziona Partecipanti
                  </label>
                  <span className="text-xs text-gray-400">
                    {selectedBotIds.length} selezionat{selectedBotIds.length === 1 ? 'o' : 'i'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                  {availableBots.map((bot) => {
                    const isSelected = selectedBotIds.includes(bot.id);
                    return (
                      <div
                        key={bot.id}
                        onClick={() => toggleBotSelection(bot.id)}
                        className={`flex items-center gap-3 p-2.5 rounded-2xl border cursor-pointer transition-all ${
                          isSelected
                            ? 'border-gray-900 bg-gray-900/5 shadow-2xs'
                            : 'border-gray-200/80 bg-white hover:border-gray-300'
                        }`}
                      >
                        <BlobAvatar
                          shape={bot.shape || 'circle'}
                          color={bot.color || '#00BA88'}
                          size={32}
                          showStatus={false}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-xs font-bold text-gray-900 truncate">
                            {bot.name}
                          </div>
                          <div className="text-[11px] text-gray-500 truncate">
                            {bot.role}
                          </div>
                        </div>
                        <div
                          className={`w-5 h-5 rounded-md flex items-center justify-center border transition ${
                            isSelected
                              ? 'bg-gray-900 border-gray-900 text-white'
                              : 'border-gray-300 bg-white'
                          }`}
                        >
                          {isSelected && <Check className="w-3.5 h-3.5 stroke-3" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isSubmitting || selectedBotIds.length === 0}
                  className="w-full py-3 rounded-2xl bg-black hover:bg-gray-800 disabled:bg-gray-300 text-white font-semibold text-sm transition shadow-sm"
                >
                  {isSubmitting ? 'Creazione in corso...' : 'Inizia Conversazione'}
                </button>
              </div>
            </form>
          ) : (
            /* TAB 2: CREA NUOVO COWORKER */
            <form onSubmit={handleBotSubmit} className="space-y-4">
              {/* Live Blob Avatar Preview */}
              <div className="flex flex-col items-center justify-center p-4 bg-[#F8F8F7] rounded-2xl border border-gray-200/80 mb-2">
                <BlobAvatar
                  shape={botShape}
                  color={botColor}
                  size={64}
                  status="idle"
                  showStatus={false}
                />
                <div className="text-xs font-bold text-gray-800 mt-2">
                  {botName.trim() || 'Nome Coworker'}
                </div>
                <div className="text-[11px] text-gray-500">
                  {botRole.trim() || 'Ruolo'} â€¢ Effort {botEffort}
                </div>
              </div>

              {/* Bot Name and Role */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                    Nome
                  </label>
                  <input
                    type="text"
                    required
                    value={botName}
                    onChange={(e) => setBotName(e.target.value)}
                    placeholder="es. Scribe, Sentinel..."
                    className="w-full px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-900 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                    Ruolo
                  </label>
                  <input
                    type="text"
                    value={botRole}
                    onChange={(e) => setBotRole(e.target.value)}
                    placeholder="es. Code Reviewer"
                    className="w-full px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-900 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400"
                  />
                </div>
              </div>

              {/* System Prompt */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                  System Prompt
                </label>
                <textarea
                  rows={2}
                  value={botSystemPrompt}
                  onChange={(e) => setBotSystemPrompt(e.target.value)}
                  placeholder="Istruzioni specifiche per il comportamento del bot..."
                  className="w-full px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-900 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400 leading-relaxed resize-none"
                />
              </div>

              {/* Shape Picker */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Forma del Blob
                </label>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                  {SHAPES.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => setBotShape(s.id)}
                      className={`flex flex-col items-center justify-center p-2 rounded-xl border text-center transition ${
                        botShape === s.id
                          ? 'border-orange-500 bg-orange-50 text-orange-700 font-bold'
                          : 'border-gray-200 bg-white hover:border-gray-300 text-gray-600'
                      }`}
                    >
                      <BlobAvatar
                        shape={s.id}
                        color={botColor}
                        size={24}
                        showStatus={false}
                      />
                      <span className="text-[10px] mt-1 capitalize">{s.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Color & Effort */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                    Colore
                  </label>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {PRESET_COLORS.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setBotColor(c)}
                        className={`w-6 h-6 rounded-full border transition-transform ${
                          botColor === c ? 'scale-115 ring-2 ring-black/40' : 'hover:scale-105'
                        }`}
                        style={{ backgroundColor: c }}
                      />
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                    Thinking Effort
                  </label>
                  <div className="grid grid-cols-3 gap-1 bg-gray-100 p-1 rounded-xl text-center text-xs">
                    {['low', 'medium', 'high'].map((eff) => (
                      <button
                        key={eff}
                        type="button"
                        onClick={() => setBotEffort(eff)}
                        className={`py-1 rounded-lg capitalize font-medium transition ${
                          botEffort === eff
                            ? 'bg-white text-gray-900 shadow-2xs font-bold'
                            : 'text-gray-500 hover:text-gray-900'
                        }`}
                      >
                        {eff}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Submit */}
              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isSubmitting || !botName.trim()}
                  className="w-full py-3 rounded-2xl bg-black hover:bg-gray-800 disabled:bg-gray-300 text-white font-semibold text-sm transition shadow-sm"
                >
                  {isSubmitting ? 'Salvataggio...' : 'Crea e Aggiungi Coworker'}
                </button>
              </div>
            </form>
          )}
        </div>
      </motion.div>
    </div>
  );
}


--- FILE: \frontend\src\components\DesktopInspectorModal.jsx ---
import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Monitor,
  X,
  RefreshCw,
  AppWindow,
  Camera,
  Layers,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { getLiveScreenshot, getOpenWindows } from '../services/api';

export default function DesktopInspectorModal({ isOpen, onClose }) {
  const [screenshotData, setScreenshotData] = useState(null);
  const [windowsList, setWindowsList] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchLiveState = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [shot, wins] = await Promise.all([
        getLiveScreenshot().catch((err) => ({
          status: 'error',
          message: err.message,
        })),
        getOpenWindows().catch(() => ({ windows: [] })),
      ]);

      if (shot && shot.status === 'success' && shot.screenshot_b64) {
        setScreenshotData(shot);
      } else if (shot?.message) {
        setError(shot.message);
      }

      setWindowsList(wins.windows || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message || 'Errore durante la cattura dello schermo.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLiveState();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.22 }}
        className="bg-white rounded-3xl w-full max-w-4xl shadow-2xl border border-gray-200 overflow-hidden flex flex-col max-h-[92vh]"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between shrink-0 bg-[#FAFAF9]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-orange-100 text-orange-600 flex items-center justify-center shadow-2xs">
              <Monitor className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-gray-900">Live PC &amp; Screen Inspector</h3>
                <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live Hardware View
                </span>
              </div>
              <p className="text-xs text-gray-500">
                Screenshot reale catturato da mss e finestre aperte dal desktop
                {lastUpdated && ` â€¢ Ultimo scatto: ${lastUpdated}`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchLiveState}
              disabled={isLoading}
              className="px-3.5 py-1.5 rounded-xl bg-gray-900 hover:bg-black text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-2xs disabled:opacity-60"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Cattura Schermo Ora</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="w-8 h-8 rounded-full bg-gray-200/80 hover:bg-gray-300 flex items-center justify-center text-gray-600 hover:text-gray-900 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {error && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Real Live Screenshot Preview */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5 text-orange-600" />
                Screenshot Reale Desktop ({screenshotData?.screen_width || 1920}x{screenshotData?.screen_height || 1080})
              </label>
            </div>

            <div className="relative rounded-2xl overflow-hidden border border-gray-300/80 bg-gray-950 aspect-video shadow-md flex items-center justify-center">
              {screenshotData?.screenshot_b64 ? (
                <img
                  src={
                    screenshotData.screenshot_b64.startsWith('data:')
                      ? screenshotData.screenshot_b64
                      : `data:image/jpeg;base64,${screenshotData.screenshot_b64}`
                  }
                  alt="Live Desktop Screenshot"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center justify-center gap-2 text-gray-400 p-8">
                  <RefreshCw className="w-8 h-8 animate-spin text-orange-500" />
                  <p className="text-xs">Cattura dello schermo in corso...</p>
                </div>
              )}
            </div>
          </div>

          {/* Open Windows List */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-bold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-600" />
                Finestre Rilevate sul PC ({windowsList.length})
              </label>
            </div>

            {windowsList.length === 0 ? (
              <p className="text-xs text-gray-400 italic">Nessuna finestra aperta rilevata.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                {windowsList.map((winTitle, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-2.5 p-2 rounded-xl bg-gray-50 border border-gray-200/80 text-xs text-gray-800"
                  >
                    <AppWindow className="w-4 h-4 text-gray-500 shrink-0" />
                    <span className="truncate font-mono text-[11px]">{winTitle}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}


--- FILE: \frontend\src\components\NewBotModal.jsx ---
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, Check, Wand2 } from 'lucide-react';
import BlobAvatar from './BlobAvatar';

const SHAPES = ['circle', 'squircle', 'triangle', 'cloud', 'cylinder', 'drop'];

const COLOR_PALETTE = [
  { name: 'Grok Orange', hex: '#FF5C35' },
  { name: 'Sky Blue', hex: '#358BFF' },
  { name: 'Sunny Yellow', hex: '#FFC700' },
  { name: 'Electric Purple', hex: '#9B51E0' },
  { name: 'Mint Green', hex: '#10B981' },
  { name: 'Coral Pink', hex: '#F43F5E' },
  { name: 'Indigo', hex: '#6366F1' },
  { name: 'Graphite', hex: '#374151' },
];

const PRESETS = [
  { name: 'Chief', role: 'Tech Lead & Orchestrator', shape: 'squircle', color: '#FF5C35' },
  { name: 'Architect', role: 'System & DB Architecture', shape: 'cylinder', color: '#358BFF' },
  { name: 'Builder', role: 'Code generation & refactor', shape: 'triangle', color: '#10B981' },
  { name: 'Designer', role: 'UI/UX & Micro-interactions', shape: 'cloud', color: '#9B51E0' },
  { name: 'Scout', role: 'Research & Knowledge retrieval', shape: 'drop', color: '#FFC700' },
];

// Helper outside component scope
function generateBotId() {
  return `bot-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}

/**
 * Fallback-safe BlobAvatar renderer
 */
const SafeBlobAvatar = ({ shape, color, size, status, onClick, className, showStatus = true }) => {
  if (!BlobAvatar) {
    return (
      <div
        onClick={onClick}
        className={`rounded-2xl flex items-center justify-center font-bold text-white shadow-xs cursor-pointer ${className}`}
        style={{ width: size, height: size, backgroundColor: color }}
      >
        <Sparkles className="w-8 h-8 text-white" />
      </div>
    );
  }

  return (
    <BlobAvatar
      shape={shape}
      color={color}
      size={size}
      status={status}
      onClick={onClick}
      className={className}
      showStatus={showStatus}
    />
  );
};

export default function NewBotModal({
  isOpen = false,
  onClose,
  onCreateBot,
}) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [selectedShape, setSelectedShape] = useState('squircle');
  const [selectedColor, setSelectedColor] = useState('#FF5C35');
  const [wobbleKey, setWobbleKey] = useState(0);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const applyPreset = (preset) => {
    setName(preset.name);
    setRole(preset.role);
    setSelectedShape(preset.shape);
    setSelectedColor(preset.color);
    setWobbleKey((prev) => prev + 1);
  };

  const resetForm = () => {
    setName('');
    setRole('');
    setSelectedShape('squircle');
    setSelectedColor('#FF5C35');
  };

  const handleClose = () => {
    resetForm();
    onClose?.();
  };

  const handleCreate = (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    const uniqueId = generateBotId();
    const newBot = {
      id: uniqueId,
      name: name.trim(),
      role: role.trim() || 'AI Assistant',
      shape: selectedShape,
      color: selectedColor,
      status: 'idle',
      createdAt: new Date().toISOString(),
    };

    if (onCreateBot) {
      onCreateBot(newBot);
    }
    resetForm();
    if (onClose) {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
          />

          {/* Modal Content Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: 'spring', duration: 0.35, bounce: 0.15 }}
            className="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-gray-100 overflow-hidden z-10 flex flex-col"
          >
            {/* Header */}
            <div className="px-6 pt-5 pb-3 flex items-center justify-between border-b border-gray-100">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-orange-50 text-orange-600 flex items-center justify-center">
                  <Sparkles className="w-4 h-4" />
                </div>
                <h3 className="text-base font-semibold text-gray-900">Create New Bot</h3>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="px-6 py-5 flex flex-col gap-5 overflow-y-auto max-h-[82vh]">
              {/* Live Preview Box with Rocking Animation */}
              <div className="relative rounded-2xl bg-gradient-to-b from-[#FAF9F6] to-[#F3F2EE] border border-stone-200/60 p-5 flex flex-col items-center justify-center text-center">
                <span className="text-[10px] tracking-wider uppercase font-semibold text-gray-400 mb-2">
                  Live Preview â€¢ Click to Wobble
                </span>

                <motion.div
                  key={wobbleKey}
                  onClick={() => setWobbleKey((k) => k + 1)}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{
                    scale: 0.92,
                    rotate: [-12, 12, -8, 8, 0],
                    transition: { duration: 0.35 },
                  }}
                  animate={{
                    rotate: [0, -4, 4, -2, 2, 0],
                  }}
                  transition={{
                    duration: 0.4,
                    ease: 'easeOut',
                  }}
                  className="cursor-pointer select-none py-1"
                >
                  <SafeBlobAvatar
                    shape={selectedShape}
                    color={selectedColor}
                    size={80}
                    status="idle"
                    showStatus={false}
                  />
                </motion.div>

                {/* Live Name & Role Preview */}
                <div className="mt-2.5">
                  <h4 className="text-sm font-bold text-gray-900">
                    {name.trim() || 'Untitled Agent'}
                  </h4>
                  <p className="text-xs text-gray-500 font-medium">
                    {role.trim() || 'Role / Responsibility'}
                  </p>
                </div>
              </div>

              {/* Preset Quick Chips */}
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1.5 flex items-center gap-1.5">
                  <Wand2 className="w-3.5 h-3.5 text-orange-500" />
                  Quick Presets
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {PRESETS.map((p) => (
                    <button
                      key={p.name}
                      type="button"
                      onClick={() => applyPreset(p)}
                      className={`text-xs px-2.5 py-1 rounded-lg border transition font-medium ${
                        name === p.name
                          ? 'bg-black text-white border-black'
                          : 'bg-stone-50 border-stone-200 text-stone-700 hover:bg-stone-100'
                      }`}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* Name & Role Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Bot Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Chief"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full text-sm px-3 py-2 rounded-xl border border-gray-200 focus:border-black focus:ring-1 focus:ring-black outline-none transition bg-white"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Role / Task
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Tech Lead & Orchestrator"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full text-sm px-3 py-2 rounded-xl border border-gray-200 focus:border-black focus:ring-1 focus:ring-black outline-none transition bg-white"
                  />
                </div>
              </div>

              {/* Shape Selector (6 canonical shapes) */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-2">
                  Avatar Shape
                </label>
                <div className="grid grid-cols-6 gap-2">
                  {SHAPES.map((shape) => {
                    const isSelected = selectedShape === shape;
                    return (
                      <button
                        key={shape}
                        type="button"
                        onClick={() => {
                          setSelectedShape(shape);
                          setWobbleKey((k) => k + 1);
                        }}
                        className={`flex flex-col items-center justify-center p-2 rounded-xl border transition-all ${
                          isSelected
                            ? 'border-black bg-stone-100/70 shadow-xs ring-1 ring-black scale-102'
                            : 'border-gray-200 bg-white hover:bg-stone-50 text-gray-600'
                        }`}
                      >
                        <SafeBlobAvatar
                          shape={shape}
                          color={isSelected ? selectedColor : '#9CA3AF'}
                          size={32}
                          status="idle"
                          showStatus={false}
                        />
                        <span className="text-[10px] font-medium mt-1 capitalize text-gray-600">
                          {shape}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Color Swatches */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-2">
                  Theme Color
                </label>
                <div className="grid grid-cols-4 sm:grid-cols-8 gap-2">
                  {COLOR_PALETTE.map((c) => {
                    const isSelected = selectedColor.toLowerCase() === c.hex.toLowerCase();
                    return (
                      <button
                        key={c.hex}
                        type="button"
                        onClick={() => {
                          setSelectedColor(c.hex);
                          setWobbleKey((k) => k + 1);
                        }}
                        title={c.name}
                        className={`group relative h-9 rounded-xl flex items-center justify-center transition-all ${
                          isSelected ? 'ring-2 ring-black ring-offset-2 scale-105' : 'hover:scale-105'
                        }`}
                        style={{ backgroundColor: c.hex }}
                      >
                        {isSelected && (
                          <Check className="w-4 h-4 text-white drop-shadow-md stroke-[2.5]" />
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-xl hover:bg-gray-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!name.trim()}
                  className="bg-black text-white hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl px-5 py-2 text-sm font-medium transition shadow-xs flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Create Bot
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}


--- FILE: \frontend\src\components\NewRoomModal.jsx ---
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Users, Check, Hash, CheckSquare, Square } from 'lucide-react';
import BlobAvatar from './BlobAvatar';

/**
 * Fallback-safe BlobAvatar renderer
 */
const SafeBlobAvatar = ({ shape = 'circle', color = '#358BFF', size = 32, status = 'idle', className = '' }) => {
  if (!BlobAvatar) {
    return (
      <div
        className={`rounded-full flex items-center justify-center font-bold text-white text-xs shadow-xs ${className}`}
        style={{ width: size, height: size, backgroundColor: color }}
      >
        <Users className="w-4 h-4 text-white" />
      </div>
    );
  }

  return (
    <BlobAvatar
      shape={shape}
      color={color}
      size={size}
      status={status}
      className={className}
    />
  );
};

// Helper to create IDs outside component render flow
function generateRoomId() {
  return `room-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
}

function getTimestamp() {
  return new Date().toISOString();
}

// Default sample bots in case none are passed yet
const DEFAULT_SAMPLE_BOTS = [
  { id: 'bot-chief', name: 'Chief', role: 'Tech Lead & Orchestrator', shape: 'squircle', color: '#FF5C35', status: 'idle' },
  { id: 'bot-architect', name: 'Architect', role: 'System & DB Architecture', shape: 'cylinder', color: '#358BFF', status: 'idle' },
  { id: 'bot-builder', name: 'Builder', role: 'Code generation & refactor', shape: 'triangle', color: '#10B981', status: 'working' },
  { id: 'bot-designer', name: 'Designer', role: 'UI/UX & Micro-interactions', shape: 'cloud', color: '#9B51E0', status: 'idle' },
  { id: 'bot-scout', name: 'Scout', role: 'Research & Knowledge retrieval', shape: 'drop', color: '#FFC700', status: 'idle' },
];

export default function NewRoomModal({
  isOpen = false,
  onClose,
  onCreateRoom,
  availableBots = [],
}) {
  const botsList = availableBots && availableBots.length > 0 ? availableBots : DEFAULT_SAMPLE_BOTS;

  const [roomName, setRoomName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedBotIds, setSelectedBotIds] = useState(() => botsList.slice(0, 2).map((b) => b.id));

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose?.();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const toggleBotSelection = (botId) => {
    setSelectedBotIds((prev) =>
      prev.includes(botId) ? prev.filter((id) => id !== botId) : [...prev, botId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedBotIds.length === botsList.length) {
      setSelectedBotIds([]);
    } else {
      setSelectedBotIds(botsList.map((b) => b.id));
    }
  };

  const selectedBots = botsList.filter((b) => selectedBotIds.includes(b.id));

  const resetForm = () => {
    setRoomName('');
    setDescription('');
    setSelectedBotIds(botsList.slice(0, 2).map((b) => b.id));
  };

  const handleClose = () => {
    resetForm();
    onClose?.();
  };

  const handleCreate = (e) => {
    e.preventDefault();
    if (!roomName.trim()) return;

    const roomId = generateRoomId();
    const newRoom = {
      id: roomId,
      name: roomName.trim(),
      description: description.trim(),
      isRoom: true,
      type: 'room',
      bots: selectedBots,
      botIds: selectedBotIds,
      createdAt: getTimestamp(),
      status: selectedBots.some((b) => b.status === 'working' || b.status === 'typing')
        ? 'working'
        : 'idle',
      lastMessage: {
        text: `Room created with ${selectedBots.length} bots: ${selectedBots.map((b) => b.name).join(', ')}`,
        time: 'Just now',
      },
    };

    if (onCreateRoom) {
      onCreateRoom(newRoom);
    }
    resetForm();
    if (onClose) {
      onClose();
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={handleClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity"
          />

          {/* Modal Content Card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: 'spring', duration: 0.35, bounce: 0.15 }}
            className="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-gray-100 overflow-hidden z-10 flex flex-col"
          >
            {/* Header */}
            <div className="px-6 pt-5 pb-3 flex items-center justify-between border-b border-gray-100">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Users className="w-4 h-4" />
                </div>
                <h3 className="text-base font-semibold text-gray-900">Create Collaborative Room</h3>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="px-6 py-5 flex flex-col gap-4 overflow-y-auto max-h-[82vh]">
              {/* Room Name */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1 flex items-center gap-1">
                  <Hash className="w-3.5 h-3.5 text-gray-400" />
                  Room Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Offsite Crew, Sprint 42, Architecture"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  className="w-full text-sm px-3 py-2 rounded-xl border border-gray-200 focus:border-black focus:ring-1 focus:ring-black outline-none transition bg-white"
                />
              </div>

              {/* Room Description */}
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Purpose / Topic (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Cross-functional space for autonomous task execution"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full text-sm px-3 py-2 rounded-xl border border-gray-200 focus:border-black focus:ring-1 focus:ring-black outline-none transition bg-white"
                />
              </div>

              {/* Bot Selection Section */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-700">
                      Add Bots to Room
                    </span>
                    <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200/50">
                      {selectedBotIds.length} of {botsList.length} selected
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={toggleSelectAll}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                  >
                    {selectedBotIds.length === botsList.length ? (
                      <>
                        <CheckSquare className="w-3.5 h-3.5" /> Deselect All
                      </>
                    ) : (
                      <>
                        <Square className="w-3.5 h-3.5" /> Select All
                      </>
                    )}
                  </button>
                </div>

                {/* Selected Avatars Cluster Preview */}
                {selectedBots.length > 0 && (
                  <div className="mb-2 p-2.5 rounded-xl bg-stone-50 border border-stone-200/60 flex items-center justify-between">
                    <div className="flex items-center -space-x-2 overflow-hidden py-0.5 pl-1">
                      {selectedBots.map((b) => (
                        <div
                          key={b.id}
                          className="rounded-full ring-2 ring-white shadow-xs"
                          title={`${b.name} (${b.role})`}
                        >
                          <SafeBlobAvatar
                            shape={b.shape}
                            color={b.color}
                            size={28}
                            status={b.status}
                          />
                        </div>
                      ))}
                    </div>
                    <span className="text-[11px] text-gray-500 font-medium truncate max-w-[200px]">
                      {selectedBots.map((b) => b.name).join(', ')}
                    </span>
                  </div>
                )}

                {/* Bots List */}
                <div className="border border-gray-200 rounded-2xl overflow-hidden divide-y divide-gray-100 max-h-52 overflow-y-auto">
                  {botsList.map((bot) => {
                    const isSelected = selectedBotIds.includes(bot.id);
                    return (
                      <div
                        key={bot.id}
                        onClick={() => toggleBotSelection(bot.id)}
                        className={`flex items-center justify-between px-3.5 py-2.5 cursor-pointer transition-colors ${
                          isSelected ? 'bg-stone-50/80 hover:bg-stone-100/80' : 'hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <SafeBlobAvatar
                            shape={bot.shape}
                            color={bot.color}
                            size={34}
                            status={bot.status}
                          />
                          <div className="flex flex-col min-w-0">
                            <span className="text-sm font-semibold text-gray-900 truncate">
                              {bot.name}
                            </span>
                            <span className="text-xs text-gray-500 truncate">
                              {bot.role}
                            </span>
                          </div>
                        </div>

                        {/* Checkbox box */}
                        <div
                          className={`w-5 h-5 rounded-md flex items-center justify-center transition-all shrink-0 ml-2 ${
                            isSelected
                              ? 'bg-black text-white'
                              : 'border border-gray-300 bg-white'
                          }`}
                        >
                          {isSelected && <Check className="w-3.5 h-3.5 stroke-[2.5]" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5 border-t border-gray-100">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 rounded-xl hover:bg-gray-100 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!roomName.trim() || selectedBotIds.length === 0}
                  className="bg-black text-white hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl px-5 py-2 text-sm font-medium transition shadow-xs flex items-center gap-1.5"
                >
                  <Users className="w-3.5 h-3.5" />
                  Create Room
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}


--- FILE: \frontend\src\components\SettingsModal.jsx ---
import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  X,
  Key,
  User,
  Trash2,
  Check,
  AlertTriangle,
  RefreshCw,
  ExternalLink,
  Lock,
} from 'lucide-react';
import { getSettings, saveApiKey, resetDatabase } from '../services/api';

export default function SettingsModal({
  isOpen,
  onClose,
  currentUserName = 'Costa',
  onUpdateUserName,
  onDatabaseReset,
}) {
  const [apiKey, setApiKey] = useState('');
  const [userName, setUserName] = useState(currentUserName);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null); // { type: 'success' | 'error', text: '' }
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setUserName(currentUserName);
    setStatusMessage(null);
    setIsResetConfirmOpen(false);

    async function loadSettings() {
      try {
        setIsLoading(true);
        const data = await getSettings();
        if (data.gemini_api_key) {
          setApiKey(data.gemini_api_key);
        }
      } catch (err) {
        console.warn('Failed to load settings:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadSettings();
  }, [isOpen, currentUserName]);

  if (!isOpen) return null;

  const handleSaveApiKey = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setStatusMessage({ type: 'error', text: 'La chiave API non puÃ² essere vuota.' });
      return;
    }

    try {
      setIsLoading(true);
      const res = await saveApiKey(apiKey.trim());
      setStatusMessage({
        type: 'success',
        text: res.message || 'Chiave GEMINI_API_KEY salvata e client Gemini 3.8 Flash ricaricato!',
      });
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Errore durante il salvataggio della chiave.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveUserName = (e) => {
    e.preventDefault();
    const cleanName = userName.trim() || 'Costa';
    onUpdateUserName(cleanName);
    setStatusMessage({
      type: 'success',
      text: `Nome utente aggiornato a "${cleanName}".`,
    });
  };

  const handleResetDatabase = async () => {
    try {
      setIsLoading(true);
      await resetDatabase();
      setIsResetConfirmOpen(false);
      setStatusMessage({
        type: 'success',
        text: 'Database azzerato con successo! Le chat sono state pulite.',
      });
      if (onDatabaseReset) {
        onDatabaseReset();
      }
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: err.message || 'Errore durante l\'azzeramento del database.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="bg-white rounded-3xl w-full max-w-md shadow-2xl border border-gray-200 overflow-hidden flex flex-col"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gray-100 flex items-center justify-center text-gray-700">
              <Key className="w-4 h-4 text-orange-600" />
            </div>
            <div>
              <h3 className="text-base font-bold text-gray-900">Impostazioni CoworkerOS</h3>
              <p className="text-xs text-gray-400">Modello: gemini-3.8-flash</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center text-gray-500 hover:text-gray-900 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6 overflow-y-auto max-h-[75vh]">
          {/* Status Alert Banner */}
          {statusMessage && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className={`p-3 rounded-xl text-xs font-medium flex items-center gap-2 ${
                statusMessage.type === 'success'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : 'bg-rose-50 text-rose-800 border border-rose-200'
              }`}
            >
              {statusMessage.type === 'success' ? (
                <Check className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              <span>{statusMessage.text}</span>
            </motion.div>
          )}

          {/* 1. GEMINI_API_KEY Section */}
          <form onSubmit={handleSaveApiKey} className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-gray-400" />
                  GEMINI_API_KEY
                </label>
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-orange-600 hover:underline flex items-center gap-1"
                >
                  Ottieni chiave <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
              <div className="relative">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Incolla la tua chiave Google Gemini..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-sm font-mono text-gray-900 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400"
                />
              </div>
              <p className="text-[11px] text-gray-400 mt-1">
                Salvata in <code className="text-gray-600 font-mono">backend/.env</code> e ricaricata istantaneamente in memoria.
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading || !apiKey.trim()}
              className="w-full py-2.5 rounded-xl bg-gray-900 hover:bg-black disabled:bg-gray-300 text-white font-semibold text-xs transition shadow-2xs flex items-center justify-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Salva &amp; Ricarica Client Gemini</span>
            </button>
          </form>

          {/* 2. User Profile Section */}
          <form onSubmit={handleSaveUserName} className="space-y-3 pt-3 border-t border-gray-100">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-gray-400" />
                Nome Utente
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                  placeholder="Il tuo nome"
                  className="flex-1 px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 text-sm text-gray-900 focus:outline-hidden focus:bg-white focus:ring-2 focus:ring-black/10 focus:border-gray-400"
                />
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-gray-100 hover:bg-gray-200 text-gray-800 font-semibold text-xs transition"
                >
                  Aggiorna
                </button>
              </div>
            </div>
          </form>

          {/* 3. Database Reset Section */}
          <div className="pt-3 border-t border-gray-100 space-y-2">
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
              <Trash2 className="w-3.5 h-3.5 text-rose-500" />
              Reset Database &amp; Pulisci Chat
            </label>
            <p className="text-[11px] text-gray-500 leading-relaxed">
              Elimina tutte le conversazioni e messaggi spazzatura e ripristina i 5 Coworker di base puliti.
            </p>

            {isResetConfirmOpen ? (
              <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-2">
                <p className="text-xs text-rose-800 font-medium">
                  Sei sicuro di voler cancellare tutte le chat? Questa azione Ã¨ irreversibile.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleResetDatabase}
                    disabled={isLoading}
                    className="flex-1 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs transition"
                  >
                    SÃ¬, Cancella Tutto
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsResetConfirmOpen(false)}
                    className="px-3 py-1.5 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium text-xs transition"
                  >
                    Annulla
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setIsResetConfirmOpen(true)}
                className="w-full py-2.5 rounded-xl border border-rose-200 bg-rose-50/60 hover:bg-rose-100 text-rose-700 font-semibold text-xs transition flex items-center justify-center gap-1.5"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Reset Database / Pulisci Tutte le Chat</span>
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}


--- FILE: \frontend\src\components\Sidebar.jsx ---
import React, { useState } from 'react';
import {
  Search,
  Plus,
  Settings,
  Bot,
  X,
  MessageSquare,
  Trash2,
} from 'lucide-react';
import BlobAvatar from './BlobAvatar';

/**
 * Fallback-safe BlobAvatar renderer
 */
const SafeBlobAvatar = ({
  shape = 'circle',
  color = '#FF5C35',
  size = 36,
  status = 'idle',
  className = '',
  showStatus = true,
}) => {
  if (!BlobAvatar) {
    return (
      <div
        className={`rounded-full flex items-center justify-center font-bold text-white text-xs shadow-xs ${className}`}
        style={{ width: size, height: size, backgroundColor: color || '#FF5C35' }}
      >
        <Bot className="w-4 h-4 text-white" />
      </div>
    );
  }

  return (
    <BlobAvatar
      shape={shape}
      color={color}
      size={size}
      status={status}
      className={className}
      showStatus={showStatus}
    />
  );
};

/**
 * Renders avatar(s) for a conversation:
 * - Single bot avatar
 * - Overlapping cluster for multi-bot rooms
 */
const ConversationAvatarGroup = ({ conversation }) => {
  const bots = conversation?.bots || (conversation?.bot ? [conversation.bot] : []);

  if (bots.length > 1) {
    const visibleBots = bots.slice(0, 3);
    const extraCount = bots.length - visibleBots.length;

    return (
      <div className="relative flex items-center -space-x-2.5 shrink-0 pl-0.5">
        {visibleBots.map((b, idx) => (
          <div
            key={b.id || idx}
            className="rounded-full ring-2 ring-[#F8F8F7] group-hover:ring-[#EFEFEA] transition-all overflow-visible"
            style={{ zIndex: 10 - idx }}
          >
            <SafeBlobAvatar
              shape={b.shape || 'circle'}
              color={b.color || '#358BFF'}
              size={26}
              status={idx === 0 ? conversation.status || b.status : undefined}
              showStatus={idx === 0}
            />
          </div>
        ))}
        {extraCount > 0 && (
          <div
            className="w-6 h-6 rounded-full bg-gray-200 text-gray-700 font-semibold text-[10px] flex items-center justify-center ring-2 ring-[#F8F8F7] group-hover:ring-[#EFEFEA]"
            style={{ zIndex: 5 }}
          >
            +{extraCount}
          </div>
        )}
      </div>
    );
  }

  // Single bot conversation
  const singleBot = bots[0] || {
    shape: conversation?.shape || 'circle',
    color: conversation?.color || '#FF5C35',
    status: conversation?.status || 'idle',
  };

  return (
    <SafeBlobAvatar
      shape={singleBot.shape}
      color={singleBot.color}
      size={36}
      status={conversation.status || singleBot.status}
    />
  );
};

export default function Sidebar({
  conversations = [],
  activeId,
  onSelectConversation,
  onOpenCreateModal,
  onDeleteChat,
  onOpenSettings,
  searchQuery = '',
  setSearchQuery,
  currentUser = { name: 'Costa', role: 'Workspace Admin' },
}) {
  const [internalSearch, setInternalSearch] = useState('');
  const query = setSearchQuery ? searchQuery : internalSearch;
  const updateQuery = setSearchQuery || setInternalSearch;

  // Filter conversations by search
  const filteredConversations = conversations.filter((c) => {
    if (!query.trim()) return true;
    const nameMatch = (c.name || c.title || '').toLowerCase().includes(query.toLowerCase());
    const lastMsg = typeof c.lastMessage === 'string'
      ? c.lastMessage
      : c.lastMessage?.text || '';
    const msgMatch = lastMsg.toLowerCase().includes(query.toLowerCase());
    return nameMatch || msgMatch;
  });

  return (
    <aside className="w-[290px] min-w-[290px] bg-[#F8F8F7] border-r border-[#E5E5E2] flex flex-col h-full select-none text-gray-800">
      {/* Top Header: Traffic Lights + Unified '+' Button */}
      <div className="h-12 px-3.5 flex items-center justify-between border-b border-[#ECECE8]/60 shrink-0" style={{ WebkitAppRegion: 'drag' }}>
        <div className="flex items-center gap-2" style={{ WebkitAppRegion: 'no-drag' }}>
          <span
            className="w-3 h-3 rounded-full bg-[#FF5F56] border border-black/10 inline-block cursor-pointer"
            title="Chiudi"
          />
          <span
            className="w-3 h-3 rounded-full bg-[#FFBD2E] border border-black/10 inline-block cursor-pointer"
            title="Minimizza"
          />
          <span
            className="w-3 h-3 rounded-full bg-[#27C93F] border border-black/10 inline-block cursor-pointer"
            title="Ingrandisci"
          />
        </div>

        {/* Plus Button: Opens tabbed Create Modal */}
        <button
          type="button"
          onClick={() => onOpenCreateModal && onOpenCreateModal()}
          style={{ WebkitAppRegion: 'no-drag' }}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-[#EBEAE5] transition shadow-2xs cursor-pointer z-10"
          title="Nuova Chat o Crea Coworker"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {/* Search Bar */}
      <div className="px-3 pt-2.5 pb-2">
        <div className="relative flex items-center bg-[#EBEAE5] rounded-lg px-2.5 py-1.5 transition-all focus-within:bg-white focus-within:ring-1 focus-within:ring-gray-300">
          <Search className="w-3.5 h-3.5 text-gray-400 shrink-0 mr-2" />
          <input
            type="text"
            value={query}
            onChange={(e) => updateQuery(e.target.value)}
            placeholder="Cerca conversazione..."
            className="w-full bg-transparent text-sm text-gray-800 placeholder-gray-400 outline-none border-none p-0"
          />
          {query.length > 0 && (
            <button
              type="button"
              onClick={() => updateQuery('')}
              className="text-gray-400 hover:text-gray-600 transition p-0.5"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1">
        {filteredConversations.length === 0 ? (
          <div className="py-8 px-4 text-center flex flex-col items-center justify-center gap-2 text-gray-400">
            <MessageSquare className="w-6 h-6 stroke-1 text-gray-300" />
            <p className="text-xs">Nessuna conversazione trovata</p>
            {query && (
              <button
                type="button"
                onClick={() => updateQuery('')}
                className="text-xs text-orange-600 hover:underline font-medium"
              >
                Pulisci ricerca
              </button>
            )}
          </div>
        ) : (
          filteredConversations.map((conv) => {
            const isActive = activeId === conv.id;
            const status = conv.status || conv.bot?.status || conv.bots?.[0]?.status;
            const isWorking = status === 'working' || status === 'typing';

            const lastMessageText =
              typeof conv.lastMessage === 'string'
                ? conv.lastMessage
                : conv.lastMessage?.text || '';

            const timeDisplay =
              conv.time ||
              (conv.updatedAt ? new Date(conv.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '');

            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation && onSelectConversation(conv.id)}
                className={`group relative flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl cursor-pointer transition-all duration-150 ${
                  isActive
                    ? 'bg-[#ECEBE5] shadow-xs'
                    : 'hover:bg-[#EFEFEA]'
                }`}
              >
                {/* Avatar */}
                <ConversationAvatarGroup conversation={conv} />

                {/* Details */}
                <div className="flex-1 min-w-0 flex flex-col justify-center">
                  <div className="flex items-center justify-between gap-1 mb-0.5">
                    <span className="font-medium text-gray-900 text-sm truncate">
                      {conv.name || conv.title || 'Chat'}
                    </span>
                    {timeDisplay && (
                      <span className="text-[11px] text-gray-400 shrink-0 font-normal">
                        {timeDisplay}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center min-w-0">
                    {isWorking ? (
                      <div className="flex items-center gap-1.5 text-xs text-amber-600 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse shrink-0" />
                        <span className="truncate">Thinking / Working...</span>
                      </div>
                    ) : (
                      <p className="text-xs text-gray-500 truncate leading-relaxed">
                        {lastMessageText || 'Nessun messaggio'}
                      </p>
                    )}
                  </div>
                </div>

                {/* Trash Icon Button on Hover */}
                {onDeleteChat && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Sei sicuro di voler eliminare la chat "${conv.title || conv.name}"?`)) {
                        onDeleteChat(conv.id);
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-gray-400 hover:text-rose-600 hover:bg-rose-50 transition shrink-0"
                    title="Elimina conversazione"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Footer: User Profile + Settings Gear */}
      <div className="border-t border-[#E5E5E2] p-3 bg-[#F8F8F7] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="relative shrink-0">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-stone-800 to-stone-600 flex items-center justify-center text-white font-medium text-xs shadow-xs">
              {(currentUser?.name || 'C').charAt(0).toUpperCase()}
            </div>
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-500 rounded-full ring-2 ring-[#F8F8F7]" />
          </div>

          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-gray-900 truncate">
              {currentUser?.name || 'Costa'}
            </span>
            <span className="text-[10px] text-gray-500 truncate">
              {currentUser?.role || 'Admin'}
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onOpenSettings && onOpenSettings()}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-900 hover:bg-[#EBEAE5] transition"
          title="Impostazioni (GEMINI_API_KEY, Nome, Reset)"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}


--- FILE: \frontend\src\index.css ---
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  color-scheme: light;
}

html, body, #root {
  height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
  background-color: #F8F8F7;
  color: #1c1c1e;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow: hidden;
  user-select: none;
}

/* Custom scrollbar for desktop app feel */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 9999px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.22);
}


--- FILE: \frontend\src\main.jsx ---
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)


--- FILE: \frontend\src\services\api.js ---
/**
 * CoworkerOS Client API & Realtime Collaboration Engine
 * Connects directly to FastAPI backend (REST & WebSocket).
 * ZERO simulated or fake responses. All AI responses come exclusively from Gemini 3.8 Flash!
 */

const API_BASE = 'http://localhost:8000/api';
const WS_BASE = 'ws://localhost:8000/ws';

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

// Initial 5 clean Coworker chats with zero test chats
export const DEFAULT_CHATS = [
  {
    id: 'chat_chief',
    title: 'Chief',
    is_group: 0,
    participants: ['chief'],
    updated_at: new Date().toISOString(),
  },
  {
    id: 'chat_architect',
    title: 'Architect',
    is_group: 0,
    participants: ['architect'],
    updated_at: new Date().toISOString(),
  },
  {
    id: 'chat_builder',
    title: 'Builder',
    is_group: 0,
    participants: ['builder'],
    updated_at: new Date().toISOString(),
  },
  {
    id: 'chat_scout',
    title: 'Scout',
    is_group: 0,
    participants: ['scout'],
    updated_at: new Date().toISOString(),
  },
  {
    id: 'chat_archivist',
    title: 'Archivist',
    is_group: 0,
    participants: ['archivist'],
    updated_at: new Date().toISOString(),
  },
];

// Zero fake messages: clean slate
export const DEFAULT_MESSAGES = {};

/**
 * Fetch initial bootstrap data (bots, chats) from FastAPI backend
 */
export async function bootstrap() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);

    const res = await fetch(`${API_BASE}/bootstrap`, {
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (res.ok) {
      const data = await res.json();
      const bots = data.bots && data.bots.length > 0 ? data.bots : DEFAULT_BOTS;
      const chats = data.chats && data.chats.length > 0 ? data.chats : DEFAULT_CHATS;
      const activeChatId = chats[0]?.id || 'chat_chief';

      return {
        bots,
        chats,
        activeChatId,
        messages: {},
        isBackendOnline: true,
      };
    }
  } catch (err) {
    console.warn('Bootstrap backend unreachable:', err?.message || err);
  }

  return {
    bots: DEFAULT_BOTS,
    chats: DEFAULT_CHATS,
    activeChatId: 'chat_chief',
    messages: {},
    isBackendOnline: false,
  };
}

/**
 * Fetch messages for a specific chat from backend
 */
export async function fetchMessages(chatId) {
  try {
    const res = await fetch(`${API_BASE}/chats/${chatId}/messages`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn(`Failed to fetch messages for ${chatId}:`, err);
  }
  return [];
}

/**
 * Create a new bot
 */
export async function createBot(botData) {
  const res = await fetch(`${API_BASE}/bots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(botData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create bot');
  }
  return await res.json();
}

/**
 * Create a new room / chat
 */
export async function createChat(chatData) {
  const res = await fetch(`${API_BASE}/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(chatData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create chat');
  }
  return await res.json();
}

/**
 * Delete a chat completely from backend
 */
export async function deleteChat(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to delete chat');
  }
  return await res.json();
}

/**
 * Get Settings & GEMINI_API_KEY from backend
 */
export async function getSettings() {
  const res = await fetch(`${API_BASE}/settings`, {
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) {
    throw new Error('Failed to retrieve settings');
  }
  return await res.json();
}

/**
 * Save GEMINI_API_KEY to backend (.env) and reload client immediately
 */
export async function saveApiKey(apiKey) {
  const res = await fetch(`${API_BASE}/settings/apikey`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gemini_api_key: apiKey }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile salvare la chiave API');
  }
  return await res.json();
}

/**
 * Reset database (wipe chats and messages)
 */
export async function resetDatabase() {
  const res = await fetch(`${API_BASE}/settings/reset`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error('Impossibile resettare il database');
  }
  return await res.json();
}

/**
 * Capture real-time live desktop screenshot from user PC
 */
export async function getLiveScreenshot() {
  const res = await fetch(`${API_BASE}/os/screenshot`, {
    signal: AbortSignal.timeout(6000),
  });
  if (!res.ok) {
    throw new Error('Impossibile catturare lo screenshot');
  }
  return await res.json();
}

/**
 * Retrieve list of open windows on user PC
 */
export async function getOpenWindows() {
  const res = await fetch(`${API_BASE}/os/windows`, {
    signal: AbortSignal.timeout(4000),
  });
  if (!res.ok) {
    throw new Error('Impossibile ottenere la lista delle finestre');
  }
  return await res.json();
}

/**
 * Connect to WebSocket for real-time messages & bot updates
 */
export function connectWebSocket(chatId, onMessage, onError, onClose) {
  let ws = null;
  let isClosedIntentionally = false;
  let reconnectTimeout = null;

  function connect() {
    try {
      ws = new WebSocket(`${WS_BASE}/${chatId}`);

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

      ws.onclose = () => {
        if (!isClosedIntentionally) {
          onClose?.();
          reconnectTimeout = setTimeout(connect, 2500);
        }
      };
    } catch (e) {
      onError?.(e);
    }
  }

  connect();

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

/**
 * Send a user message to backend via REST.
 * The backend triggers Gemini 3.8 Flash orchestrator and broadcasts responses over WebSocket.
 */
export async function sendChatMessage({
  chatId,
  content,
  userName = 'User',
  actionCard = null,
  targetBotId = null,
}) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      sender_id: 'user',
      sender_name: userName,
      action_card: actionCard,
      target_bot_id: targetBotId,
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Impossibile inviare il messaggio al backend.');
  }

  return await res.json();
}

