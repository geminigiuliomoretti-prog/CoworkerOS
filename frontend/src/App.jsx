import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Plus, Search, Settings, Monitor, Send, CheckCircle2,
  Loader2, X, Camera, FolderOpen, Key, RefreshCw, ExternalLink, ShieldCheck, Trash2,
  Play, Brain, Edit3, Database, Clock, Calendar, Bell, PlayCircle, PauseCircle, Sliders, AlertTriangle
} from 'lucide-react';
import BlobAvatar from './components/BlobAvatar';
import {
  bootstrap,
  fetchMessages,
  sendChatMessage,
  createBot as apiCreateBot,
  createChat as apiCreateChat,
  deleteChat as apiDeleteChat,
  getSettings,
  saveApiKey,
  resetDatabase,
  getLiveScreenshot,
  getOpenWindows,
  approveAction,
  rejectAction,
  connectWebSocket,
  getTasks,
  resumeTask,
  cancelTask,
  getMemories,
  createMemory,
  updateMemory,
  deleteMemory,
  getMemorySettings,
  saveMemorySettings,
  getScheduledJobs,
  createScheduledJob,
  updateScheduledJob,
  deleteScheduledJob,
  runScheduledJobNow,
  getAllSchedulerHistory,
  getUsageSummary,
  getUsageLimits,
  saveUsageLimit,
  getNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  getModelStatus,
  setModelProvider,
  startLocalModel,
  stopLocalModel,
  checkBackendHealth,
  getTestChats,
  cleanupTestChats,
  DEFAULT_BOTS,
  DEFAULT_CHATS,
} from './services/api';

export default function App() {
  const [bots, setBots] = useState(DEFAULT_BOTS);
  const [chats, setChats] = useState(DEFAULT_CHATS);
  const [activeChatId, setActiveChatId] = useState('chat_chief');
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [botStatuses, setBotStatuses] = useState({});
  const [isSending, setIsSending] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [taskLoading, setTaskLoading] = useState(null);

  // Streaming and Tool Progress State (Fase 4)
  const [streamingMessage, setStreamingMessage] = useState(null);
  const [toolProgress, setToolProgress] = useState(null);

  // Backend Connection and Error Handlers (Fix Failed to Fetch)
  const [backendReady, setBackendReady] = useState(null);
  const [sendError, setSendError] = useState(null);

  // Test Chats Management State (Isolamento e Pulizia)
  const [testChats, setTestChats] = useState([]);
  const [showCleanupModal, setShowCleanupModal] = useState(false);
  const [selectedTestChats, setSelectedTestChats] = useState([]);
  const [cleanupLoading, setCleanupLoading] = useState(false);

  // Provider and Local Model State
  const [providerMode, setProviderMode] = useState('AUTO'); // LOCAL, CLOUD, AUTO
  const [modelStatus, setModelStatus] = useState(null);
  const [modelLoading, setModelLoading] = useState(false);
  const [modelError, setModelError] = useState(null);

  // Modals state
  const [showNewModal, setShowNewModal] = useState(false);
  const [newModalTab, setNewModalTab] = useState('chat');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showInspectorModal, setShowInspectorModal] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [showMemoryModal, setShowMemoryModal] = useState(false);

  // Memories state (Fase 2B)
  const [memories, setMemories] = useState([]);
  const [memorySearch, setMemorySearch] = useState('');
  const [memoryTypeFilter, setMemoryTypeFilter] = useState('all');
  const [memorySettings, setMemorySettings] = useState({ auto_memory_enabled: true });
  const [editingMemoryId, setEditingMemoryId] = useState(null);
  const [editingMemoryContent, setEditingMemoryContent] = useState('');
  const [newMemoryContent, setNewMemoryContent] = useState('');
  const [newMemoryType, setNewMemoryType] = useState('fact');
  const [showNewMemoryForm, setShowNewMemoryForm] = useState(false);
  const [loadingMemories, setLoadingMemories] = useState(false);

  // Scheduler & Automazioni state (Fase 2C)
  const [showSchedulerModal, setShowSchedulerModal] = useState(false);
  const [schedulerTab, setSchedulerTab] = useState('jobs');
  const [scheduledJobs, setScheduledJobs] = useState([]);
  const [schedulerHistory, setSchedulerHistory] = useState([]);
  const [usageSummary, setUsageSummary] = useState({ requests_count: 0, total_tokens: 0, estimated_cost_usd: 0.0, by_model: [] });
  const [usageLimits, setUsageLimits] = useState({ max_requests_daily: 200, max_requests_per_task: 15, max_concurrent_tasks: 3 });
  const [notificationsList, setNotificationsList] = useState([]);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const [loadingScheduler, setLoadingScheduler] = useState(false);
  const [newJobForm, setNewJobForm] = useState({
    name: '',
    prompt: '',
    schedule_type: 'interval',
    interval_seconds: 3600,
    time: '09:00',
    target_bot_id: 'chief',
    missed_job_policy: 'skip',
    timezone: 'Europe/Rome',
    target_time: '',
  });
  const [showNewJobForm, setShowNewJobForm] = useState(false);

  // Settings & forms
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [maskedKey, setMaskedKey] = useState('');
  const [maskedToken, setMaskedToken] = useState('');
  const [newChatTitle, setNewChatTitle] = useState('');
  const [selectedBotIds, setSelectedBotIds] = useState(['chief', 'architect', 'builder']);
  const [newBotName, setNewBotName] = useState('');
  const [newBotRole, setNewBotRole] = useState('');
  const [newBotPrompt, setNewBotPrompt] = useState('');
  const [newBotShape, setNewBotShape] = useState('squircle');
  const [newBotColor, setNewBotColor] = useState('#10B981');

  // Inspector
  const [inspectorData, setInspectorData] = useState(null);
  const [inspectorWindows, setInspectorWindows] = useState([]);
  const [loadingInspector, setLoadingInspector] = useState(false);

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const fileInputRef = useRef(null);

  const botsMap = useMemo(() => {
    const map = {};
    bots.forEach((b) => { map[b.id] = b; });
    return map;
  }, [bots]);

  const activeChat = useMemo(
    () => chats.find((c) => c.id === activeChatId) || chats[0] || null,
    [chats, activeChatId]
  );

  const loadTestChatsList = useCallback(async () => {
    try {
      const data = await getTestChats();
      if (data && Array.isArray(data.test_chats)) {
        setTestChats(data.test_chats);
      }
    } catch (err) {
      console.warn('Failed to load test chats:', err);
    }
  }, []);

  const loadBootstrap = useCallback(async () => {
    try {
      const isHealthy = await checkBackendHealth();
      setBackendReady(isHealthy);
      if (!isHealthy) return;

      const data = await bootstrap();
      if (data) {
        if (data.bots?.length) setBots(data.bots);
        if (data.chats?.length) {
          setChats(data.chats);
          if (!data.chats.some((c) => c.id === activeChatId)) {
            setActiveChatId(data.chats[0].id);
          }
        }
        if (data.model_status) {
          setModelStatus(data.model_status);
          if (data.model_status.provider_mode) {
            setProviderMode(data.model_status.provider_mode);
          }
        }
      }
      await loadTestChatsList();
    } catch (err) {
      console.error('Bootstrap error:', err);
      setBackendReady(false);
    }
  }, [activeChatId, loadTestChatsList]);

  const loadChatMessages = useCallback(async (chatId) => {
    if (!chatId) return;
    try {
      const msgs = await fetchMessages(chatId);
      setMessages(Array.isArray(msgs) ? msgs : []);
    } catch (err) {
      console.error('Messages error:', err);
    }
  }, []);

  const loadTasks = useCallback(async (chatId) => {
    if (!chatId) return;
    try {
      const list = await getTasks(chatId);
      setTasks(Array.isArray(list) ? list : []);
    } catch (err) {
      console.error('Tasks error:', err);
    }
  }, []);

  useEffect(() => {
    loadBootstrap();
    const interval = setInterval(async () => {
      const ok = await checkBackendHealth();
      setBackendReady(ok);
      if (ok && testChats.length === 0) {
        loadTestChatsList();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [loadBootstrap, loadTestChatsList, testChats.length]);

  useEffect(() => {
    if (!activeChatId) return;
    loadChatMessages(activeChatId);
    loadTasks(activeChatId);

    let activeWs = null;
    let isSubscribed = true;

    async function initWs() {
      if (wsRef.current) {
        wsRef.current.close();
      }
      activeWs = await connectWebSocket(
        activeChatId,
        (payload) => {
          if (!isSubscribed) return;
          if (typeof payload === 'object') {
            if (payload.type === 'new_message' && payload.message) {
              setStreamingMessage(null);
              setToolProgress(null);
              setMessages((prev) => {
                if (prev.some((m) => m.id === payload.message.id)) return prev;
                return [...prev, payload.message];
              });
              loadBootstrap();
            } else if (payload.type === 'streaming_chunk') {
              setStreamingMessage({
                id: 'streaming-active',
                sender_id: payload.bot_id || 'chief',
                sender_name: payload.bot_name || 'Chief',
                content: payload.content || '',
              });
            } else if (payload.type === 'tool_progress') {
              setToolProgress({
                stage: payload.stage,
                tool: payload.tool,
                bot_name: payload.bot_name || 'Chief',
              });
            } else if (payload.type === 'bot_status') {
              setBotStatuses((prev) => ({
                ...prev,
                [payload.bot_id]: payload.status === 'idle' ? null : {
                  name: payload.bot_name || payload.bot_id,
                  status: payload.status,
                },
              }));
            } else if (payload.type === 'approval_resolved') {
              loadChatMessages(activeChatId);
              loadTasks(activeChatId);
            } else if (payload.type === 'task_updated') {
              loadTasks(activeChatId);
            } else if (payload.type === 'notification' && payload.notification) {
              setNotificationsList((prev) => [payload.notification, ...prev]);
              setUnreadNotifCount((prev) => prev + 1);
            }
          }
        },
        (err) => console.warn('WS error:', err),
        () => {}
      );
      wsRef.current = activeWs;
    }

    initWs();

    return () => {
      isSubscribed = false;
      if (activeWs) activeWs.close();
    };
  }, [activeChatId, loadBootstrap, loadChatMessages, loadTasks]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, botStatuses, streamingMessage, toolProgress]);

  const handleSendMessage = async (customText = null) => {
    const text = (customText !== null ? customText : inputText).trim();
    if (!text || !activeChatId || isSending) return;

    if (backendReady === false) {
      setSendError('Il backend di CoworkerOS (127.0.0.1:8000) non è ancora pronto o raggiungibile. Attendere qualche secondo e riprovare.');
      return;
    }

    setSendError(null);
    if (customText === null) setInputText('');
    setIsSending(true);

    try {
      const data = await sendChatMessage({
        chatId: activeChatId,
        content: text,
      });
      if (data.bot_replies) {
        await loadChatMessages(activeChatId);
        await loadTasks(activeChatId);
        await loadBootstrap();
      }
    } catch (err) {
      console.error('Send error:', err);
      // Ripristina il testo digitato per non perdere il messaggio dell'utente
      if (customText === null) {
        setInputText(text);
      }
      setSendError(err.message || 'Errore durante la comunicazione con il server.');
    } finally {
      setIsSending(false);
      setBotStatuses({});
    }
  };

  const handlePerformCleanup = async () => {
    if (selectedTestChats.length === 0 || cleanupLoading) return;
    setCleanupLoading(true);
    try {
      const res = await cleanupTestChats(selectedTestChats);
      if (res && res.success) {
        setShowCleanupModal(false);
        setSelectedTestChats([]);
        await loadBootstrap();
      } else {
        alert(res?.error || 'Errore durante la pulizia delle chat di test');
      }
    } catch (err) {
      alert(err.message || 'Errore durante la pulizia');
    } finally {
      setCleanupLoading(false);
    }
  };

  const handleApprove = async (approvalId) => {
    if (!approvalId || actionLoading) return;
    setActionLoading(approvalId);
    try {
      await approveAction(approvalId);
      await loadChatMessages(activeChatId);
      await loadTasks(activeChatId);
    } catch (err) {
      alert(err.message || 'Errore durante l\'approvazione');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (approvalId) => {
    if (!approvalId || actionLoading) return;
    setActionLoading(approvalId);
    try {
      await rejectAction(approvalId);
      await loadChatMessages(activeChatId);
      await loadTasks(activeChatId);
    } catch (err) {
      alert(err.message || 'Errore durante il rifiuto');
    } finally {
      setActionLoading(null);
    }
  };

  const handleResumeTask = async (taskId) => {
    if (!taskId || taskLoading) return;
    setTaskLoading(taskId);
    try {
      await resumeTask(taskId);
      await loadTasks(activeChatId);
      await loadChatMessages(activeChatId);
    } catch (err) {
      alert(err.message || 'Errore durante la ripresa del task');
    } finally {
      setTaskLoading(null);
    }
  };

  const handleCancelTask = async (taskId) => {
    if (!taskId || taskLoading) return;
    setTaskLoading(taskId);
    try {
      await cancelTask(taskId);
      await loadTasks(activeChatId);
    } catch (err) {
      alert(err.message || 'Errore durante l\'annullamento del task');
    } finally {
      setTaskLoading(null);
    }
  };

  const openInspector = async () => {
    setShowInspectorModal(true);
    setLoadingInspector(true);
    try {
      const [capData, winJson] = await Promise.all([
        getLiveScreenshot(),
        getOpenWindows(),
      ]);
      setInspectorData(capData);
      setInspectorWindows(winJson.windows || []);
    } catch (e) {
      console.error('Inspector error:', e);
    } finally {
      setLoadingInspector(false);
    }
  };

  const openSettings = async () => {
    setShowSettingsModal(true);
    try {
      const settings = await getSettings();
      setMaskedKey(settings.masked_key || '');
      setMaskedToken(settings.masked_token || '');
    } catch (_) {}
  };

  const refreshModelStatus = useCallback(async () => {
    try {
      const data = await getModelStatus();
      if (data) {
        setModelStatus(data);
        if (data.provider_mode) {
          setProviderMode(data.provider_mode);
        }
      }
    } catch (_) {}
  }, []);

  const handleSelectProvider = async (mode) => {
    try {
      setModelLoading(true);
      setModelError(null);
      const res = await setModelProvider(mode);
      setProviderMode(mode);
      if (res?.status) {
        setModelStatus(res.status);
      } else {
        await refreshModelStatus();
      }
    } catch (err) {
      setModelError(err.message || 'Errore cambio provider');
    } finally {
      setModelLoading(false);
    }
  };

  const handleToggleLocalModel = async () => {
    try {
      setModelLoading(true);
      setModelError(null);
      if (modelStatus?.local_model?.is_alive) {
        await stopLocalModel();
      } else {
        const res = await startLocalModel(false);
        if (!res.success) {
          setModelError(res.error || 'Impossibile avviare il modello locale');
        }
      }
      await refreshModelStatus();
    } catch (err) {
      setModelError(err.message || 'Errore controllo modello');
    } finally {
      setModelLoading(false);
    }
  };

  const loadMemoriesList = useCallback(async (search = '', type = 'all') => {
    setLoadingMemories(true);
    try {
      const typeFilter = type === 'all' ? null : type;
      const data = await getMemories(search, null, typeFilter);
      setMemories(Array.isArray(data) ? data : []);
      const settings = await getMemorySettings();
      if (settings) setMemorySettings(settings);
    } catch (err) {
      console.error('Memories error:', err);
    } finally {
      setLoadingMemories(false);
    }
  }, []);

  const openMemoryModal = () => {
    setShowMemoryModal(true);
    loadMemoriesList(memorySearch, memoryTypeFilter);
  };

  const handleToggleAutoMemory = async () => {
    try {
      const updated = await saveMemorySettings({
        auto_memory_enabled: !memorySettings.auto_memory_enabled,
      });
      setMemorySettings(updated.settings);
    } catch (err) {
      alert(err.message || 'Errore salvataggio impostazioni memoria');
    }
  };

  const handleCreateMemory = async () => {
    if (!newMemoryContent.trim()) return;
    try {
      await createMemory({
        content: newMemoryContent.trim(),
        memory_type: newMemoryType,
        project_id: activeChatId || 'default',
      });
      setNewMemoryContent('');
      setShowNewMemoryForm(false);
      loadMemoriesList(memorySearch, memoryTypeFilter);
    } catch (err) {
      alert(err.message || 'Errore salvataggio memoria');
    }
  };

  const handleSaveEditMemory = async (memoryId) => {
    if (!editingMemoryContent.trim()) return;
    try {
      await updateMemory(memoryId, { content: editingMemoryContent.trim() });
      setEditingMemoryId(null);
      loadMemoriesList(memorySearch, memoryTypeFilter);
    } catch (err) {
      alert(err.message || 'Errore modifica memoria');
    }
  };

  const handleDeleteMemoryItem = async (memoryId) => {
    if (!confirm('Sei sicuro di voler eliminare questa memoria?')) return;
    try {
      await deleteMemory(memoryId);
      loadMemoriesList(memorySearch, memoryTypeFilter);
    } catch (err) {
      alert(err.message || 'Errore eliminazione memoria');
    }
  };

  // SCHEDULER & AUTOMAZIONI HANDLERS (FASE 2C)
  const openSchedulerModal = async () => {
    setShowSchedulerModal(true);
    setLoadingScheduler(true);
    try {
      const [jobs, hist, usage, limits, notifs] = await Promise.all([
        getScheduledJobs(),
        getAllSchedulerHistory(),
        getUsageSummary(1),
        getUsageLimits(),
        getNotifications(false),
      ]);
      setScheduledJobs(jobs || []);
      setSchedulerHistory(hist || []);
      setUsageSummary(usage || { requests_count: 0, total_tokens: 0, estimated_cost_usd: 0.0 });
      setUsageLimits(limits || {});
      setNotificationsList(notifs || []);
      setUnreadNotifCount((notifs || []).filter((n) => !n.is_read).length);
    } catch (e) {
      console.warn('Errore caricamento scheduler:', e);
    } finally {
      setLoadingScheduler(false);
    }
  };

  const handleCreateJob = async () => {
    if (!newJobForm.name.trim() || !newJobForm.prompt.trim()) return;
    try {
      let config = {};
      if (newJobForm.schedule_type === 'interval') {
        config = { interval_seconds: parseInt(newJobForm.interval_seconds, 10) || 3600 };
      } else if (newJobForm.schedule_type === 'daily') {
        config = { time: newJobForm.time || '09:00' };
      } else if (newJobForm.schedule_type === 'weekly') {
        config = { time: newJobForm.time || '09:00', days: [0, 2, 4] };
      } else if (newJobForm.schedule_type === 'once') {
        config = { target_time: newJobForm.target_time || new Date(Date.now() + 3600000).toISOString() };
      }

      await createScheduledJob({
        name: newJobForm.name.trim(),
        prompt: newJobForm.prompt.trim(),
        schedule_type: newJobForm.schedule_type,
        schedule_config: config,
        chat_id: activeChatId || 'chat_chief',
        target_bot_id: newJobForm.target_bot_id || 'chief',
        timezone: newJobForm.timezone || 'Europe/Rome',
        missed_job_policy: newJobForm.missed_job_policy || 'skip',
      });
      setShowNewJobForm(false);
      setNewJobForm({
        name: '',
        prompt: '',
        schedule_type: 'interval',
        interval_seconds: 3600,
        time: '09:00',
        target_bot_id: 'chief',
        missed_job_policy: 'skip',
        timezone: 'Europe/Rome',
        target_time: '',
      });
      const updated = await getScheduledJobs();
      setScheduledJobs(updated || []);
    } catch (e) {
      alert(e.message || 'Errore creazione attività');
    }
  };

  const handleTogglePauseJob = async (job) => {
    try {
      const newStatus = job.status === 'paused' ? 'active' : 'paused';
      await updateScheduledJob(job.id, { status: newStatus });
      const updated = await getScheduledJobs();
      setScheduledJobs(updated || []);
    } catch (e) {
      alert(e.message || 'Errore aggiornamento');
    }
  };

  const handleDeleteJob = async (jobId) => {
    if (!confirm('Eliminare definitivamente questa attività programmata?')) return;
    try {
      await deleteScheduledJob(jobId);
      setScheduledJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (e) {
      alert(e.message || 'Errore eliminazione');
    }
  };

  const handleRunJobNow = async (jobId) => {
    try {
      await runScheduledJobNow(jobId);
      alert('Esecuzione avviata in background!');
      const hist = await getAllSchedulerHistory();
      setSchedulerHistory(hist || []);
    } catch (e) {
      alert(e.message || 'Errore avvio');
    }
  };

  const handleSaveLimit = async (key, val) => {
    try {
      const updated = await saveUsageLimit(key, parseInt(val, 10));
      setUsageLimits(updated.limits || {});
    } catch (e) {
      alert(e.message || 'Errore salvataggio quota');
    }
  };

  const handleMarkNotifRead = async (notifId) => {
    try {
      await markNotificationRead(notifId);
      setNotificationsList((prev) => prev.map((n) => (n.id === notifId ? { ...n, is_read: 1 } : n)));
      setUnreadNotifCount((prev) => Math.max(0, prev - 1));
    } catch (e) {
      console.warn(e);
    }
  };

  const handleMarkAllNotifsRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotificationsList((prev) => prev.map((n) => ({ ...n, is_read: 1 })));
      setUnreadNotifCount(0);
    } catch (e) {
      console.warn(e);
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      await saveApiKey(apiKeyInput.trim());
      setApiKeyInput('');
      setShowSettingsModal(false);
      await loadBootstrap();
    } catch (err) {
      alert(err.message || 'Impossibile salvare la chiave');
    }
  };

  const handleResetDatabase = async () => {
    if (window.confirm('Sei sicuro di voler pulire e resettare il database e la cronologia chat?')) {
      try {
        await resetDatabase();
        await loadBootstrap();
        await loadChatMessages(activeChatId);
        setShowSettingsModal(false);
      } catch (err) {
        alert(err.message || 'Errore reset database');
      }
    }
  };

  const handleCreateChat = async () => {
    if (!newChatTitle.trim() || selectedBotIds.length === 0) return;
    try {
      const data = await apiCreateChat({
        title: newChatTitle.trim(),
        participants: selectedBotIds,
      });
      await loadBootstrap();
      if (data.chat?.id) setActiveChatId(data.chat.id);
      setNewChatTitle('');
      setShowNewModal(false);
    } catch (err) {
      alert(err.message || 'Errore creazione stanza');
    }
  };

  const handleCreateBot = async () => {
    if (!newBotName.trim() || !newBotRole.trim()) return;
    try {
      const data = await apiCreateBot({
        name: newBotName.trim(),
        role: newBotRole.trim(),
        system_prompt: newBotPrompt.trim(),
        shape: newBotShape,
        color: newBotColor,
      });
      await loadBootstrap();
      if (data.chat?.id) setActiveChatId(data.chat.id);
      setNewBotName('');
      setNewBotRole('');
      setNewBotPrompt('');
      setShowNewModal(false);
    } catch (err) {
      alert(err.message || 'Errore creazione bot');
    }
  };

  const handleDeleteChat = async (chatId, title) => {
    if (window.confirm(`Eliminare la conversazione "${title}"?`)) {
      try {
        await apiDeleteChat(chatId);
        await loadBootstrap();
      } catch (err) {
        alert(err.message || 'Errore eliminazione chat');
      }
    }
  };

  const activeWorkingBots = Object.entries(botStatuses)
    .filter(([, val]) => val !== null)
    .map(([id, val]) => ({ id, ...val }));

  const filteredChats = chats.filter((c) =>
    (c.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#FFFFFF] text-[#111827] select-none font-sans">
      {/* 1. SIDEBAR SINISTRA */}
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

        <div className="p-3 pb-1">
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

        {/* BANNER RILEVAZIONE E PULIZIA CHAT DI TEST */}
        {testChats.length > 0 && (
          <div className="mx-3 mb-2 p-2.5 bg-amber-50/90 border border-amber-200 rounded-2xl flex items-center justify-between shadow-xs">
            <div className="flex items-center gap-2 min-w-0 pr-1">
              <Trash2 className="w-4 h-4 text-amber-600 shrink-0" />
              <div className="text-[11px] leading-tight text-amber-900 truncate">
                <span className="font-bold">{testChats.length}</span> chat di test
              </div>
            </div>
            <button
              onClick={() => {
                setSelectedTestChats(testChats.map((c) => c.id));
                setShowCleanupModal(true);
              }}
              className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white text-[11px] font-bold rounded-xl transition cursor-pointer shadow-xs shrink-0"
            >
              Pulisci
            </button>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {filteredChats.map((chat) => {
            const partIds = chat.participants || ['chief'];
            const primaryBot = botsMap[partIds[0]] || { shape: 'squircle', color: '#10B981', name: chat.title };
            const isSelected = chat.id === activeChatId;
            const workingInfo = partIds.map((id) => botStatuses[id]).find(Boolean);

            return (
              <div
                key={chat.id}
                onClick={() => setActiveChatId(chat.id)}
                className={`group w-full flex items-center justify-between gap-2 p-2.5 rounded-2xl text-left transition cursor-pointer ${
                  isSelected ? 'bg-[#EBEAE6]' : 'hover:bg-gray-200/50'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
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
                        ● {workingInfo.status}
                      </p>
                    ) : (
                      <p className="text-xs text-gray-500 truncate">
                        {chat.last_message || primaryBot.role || 'Pronto ad agire'}
                      </p>
                    )}
                  </div>
                </div>

                {chats.length > 1 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteChat(chat.id, chat.title);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-300 rounded text-gray-400 hover:text-rose-600 transition"
                    title="Elimina chat"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
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
                <span className={`w-1.5 h-1.5 rounded-full ${modelStatus?.local_model?.is_alive ? 'bg-emerald-500' : 'bg-blue-500'}`} />
                <span className="truncate max-w-[150px]">
                  {modelStatus?.active_provider || (providerMode === 'LOCAL' ? 'Qwen3.5-4B (Local)' : 'gemini-3.8-flash')}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={openSettings}
            style={{ WebkitAppRegion: 'no-drag' }}
            className="p-2 rounded-xl hover:bg-gray-200 text-gray-600 cursor-pointer"
            title="Impostazioni, Sicurezza & API Key"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </aside>

      {/* 2. CHAT AREA CENTRALE */}
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
                {activeWorkingBots.length > 0 && ` • ${activeWorkingBots[0].name}: ${activeWorkingBots[0].status}`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2" style={{ WebkitAppRegion: 'no-drag' }}>
            {/* SELETTORE MODALITÀ PROVIDER */}
            <div className="flex items-center bg-gray-100 rounded-xl p-0.5 border border-gray-200 text-xs shadow-inner">
              <button
                onClick={() => handleSelectProvider('LOCAL')}
                disabled={modelLoading}
                className={`px-2 py-1 rounded-lg font-medium transition cursor-pointer ${
                  providerMode === 'LOCAL'
                    ? 'bg-white shadow-sm text-emerald-700 font-bold'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
                title="LOCAL: utilizza esclusivamente Qwen3.5-4B su CPU locale"
              >
                LOCAL
              </button>
              <button
                onClick={() => handleSelectProvider('AUTO')}
                disabled={modelLoading}
                className={`px-2 py-1 rounded-lg font-medium transition cursor-pointer ${
                  providerMode === 'AUTO'
                    ? 'bg-white shadow-sm text-indigo-700 font-bold'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
                title="AUTO: Qwen3.5-4B locale prioritario, con fallback trasparente su Gemini Cloud"
              >
                AUTO
              </button>
              <button
                onClick={() => handleSelectProvider('CLOUD')}
                disabled={modelLoading}
                className={`px-2 py-1 rounded-lg font-medium transition cursor-pointer ${
                  providerMode === 'CLOUD'
                    ? 'bg-white shadow-sm text-blue-700 font-bold'
                    : 'text-gray-500 hover:text-gray-800'
                }`}
                title="CLOUD: utilizza Gemini Cloud per richieste estese o senza consumo RAM locale"
              >
                CLOUD
              </button>
            </div>

            {/* STATO RUNTIME QWEN LOCALE */}
            {modelLoading ? (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-amber-50 text-[11px] font-semibold text-amber-700 border border-amber-200">
                <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
                <span>Caricamento...</span>
              </span>
            ) : modelStatus?.local_model?.is_alive ? (
              <button
                onClick={handleToggleLocalModel}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-[11px] font-semibold text-emerald-700 border border-emerald-200 cursor-pointer transition"
                title={`Qwen3.5-4B Attivo (PID: ${modelStatus.local_model.pid}, RAM modello: ${modelStatus.local_model.server_rss_mb || 0} MB). Clicca per arrestare.`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Qwen Attivo</span>
              </button>
            ) : (
              <button
                onClick={handleToggleLocalModel}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-gray-100 hover:bg-gray-200 text-[11px] font-medium text-gray-600 border border-gray-200 cursor-pointer transition"
                title="Qwen3.5-4B non attivo. Clicca per avviare il modello locale."
              >
                <span className="w-2 h-2 rounded-full bg-gray-400" />
                <span>Avvia Qwen</span>
              </button>
            )}

            {/* RAM DISPONIBILE */}
            {modelStatus?.ram_info?.available_gb !== undefined && (
              <span
                className={`hidden md:flex items-center gap-1 px-2 py-1 rounded-xl text-[10px] border ${
                  modelStatus.ram_info.available_gb < 3.2
                    ? 'bg-amber-50 text-amber-800 border-amber-200 font-bold'
                    : 'bg-gray-50 text-gray-500 border-gray-200'
                }`}
                title={`RAM Libera: ${modelStatus.ram_info.available_gb} GB su ${modelStatus.ram_info.total_gb} GB.`}
              >
                {modelStatus.ram_info.available_gb < 3.2 && <AlertTriangle className="w-3 h-3 text-amber-600" />}
                <span>RAM {modelStatus.ram_info.available_gb} GB</span>
              </span>
            )}

            <button
              onClick={openSchedulerModal}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-xs font-semibold text-blue-700 border border-blue-200 transition cursor-pointer z-50 relative"
              title="Automazioni & Controllo Consumi (Fase 2C)"
            >
              <Clock className="w-4 h-4 text-blue-600" />
              <span>Automazioni</span>
              {unreadNotifCount > 0 && (
                <span className="w-2 h-2 rounded-full bg-red-500 absolute -top-0.5 -right-0.5 animate-pulse" />
              )}
            </button>

            <button
              onClick={openMemoryModal}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-xs font-semibold text-purple-700 border border-purple-200 transition cursor-pointer z-50"
              title="Memoria Locale Intelligente (Fase 2B)"
            >
              <Brain className="w-4 h-4 text-purple-600" />
              <span>Memoria</span>
            </button>

            <button
              onClick={openInspector}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gray-100 hover:bg-gray-200 text-xs font-medium text-gray-700 transition cursor-pointer z-50"
            >
              <Monitor className="w-4 h-4 text-orange-500" />
              <span>Screen Inspector</span>
            </button>
          </div>
        </header>

        {/* BANNER AVVISI RAM / MODELLO */}
        {modelError && (
          <div className="bg-amber-50 border-b border-amber-200 px-6 py-2 flex items-center justify-between text-xs text-amber-800">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{modelError}</span>
            </div>
            <button
              onClick={() => setModelError(null)}
              className="p-1 hover:bg-amber-100 rounded text-amber-700 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* TASK ENGINE PERSISTENTE (FASE 2A) */}
        {tasks.length > 0 && (
          <div className="bg-[#FAF9F5] border-b border-gray-200 px-6 py-2 flex items-center justify-between gap-3 text-xs shrink-0 select-none">
            <div className="flex items-center gap-2 overflow-x-auto py-0.5">
              <span className="font-bold text-gray-500 uppercase tracking-wider text-[10px] shrink-0">
                Task ({tasks.filter((t) => !['completed', 'cancelled'].includes(t.status)).length} attivi):
              </span>
              {tasks.slice(0, 4).map((task) => {
                const bot = botsMap[task.bot_id] || { name: task.bot_id, color: '#666' };
                const isInterrupted = task.status === 'interrupted';
                const isFailed = task.status === 'failed';
                const isRunning = task.status === 'running';
                const isWaiting = task.status === 'waiting_approval';
                const isCompleted = task.status === 'completed';

                let badgeColor = 'bg-gray-100 text-gray-600 border-gray-200';
                if (isRunning) badgeColor = 'bg-blue-50 text-blue-700 border-blue-200 animate-pulse';
                else if (isWaiting) badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';
                else if (isCompleted) badgeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
                else if (isInterrupted) badgeColor = 'bg-orange-50 text-orange-700 border-orange-200 font-semibold';
                else if (isFailed) badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';

                return (
                  <div
                    key={task.id}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-xl border text-[11px] ${badgeColor} shrink-0 max-w-xs`}
                    title={task.error_msg || task.goal || task.title}
                  >
                    <span className="font-bold" style={{ color: bot.color }}>{bot.name}:</span>
                    <span className="truncate max-w-[120px]">{task.title}</span>
                    <span className="text-[9px] uppercase tracking-wider px-1 rounded bg-white/70">
                      {task.status}
                    </span>

                    {(isInterrupted || isFailed) && (
                      <button
                        onClick={() => handleResumeTask(task.id)}
                        disabled={taskLoading === task.id}
                        className="p-0.5 hover:bg-white rounded text-emerald-700 transition cursor-pointer"
                        title="Riprendi task interrotto"
                      >
                        {taskLoading === task.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3 fill-current" />
                        )}
                      </button>
                    )}

                    {!['completed', 'cancelled'].includes(task.status) && (
                      <button
                        onClick={() => handleCancelTask(task.id)}
                        disabled={taskLoading === task.id}
                        className="p-0.5 hover:bg-white rounded text-gray-400 hover:text-rose-600 transition cursor-pointer"
                        title="Annulla task"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            <button
              onClick={() => loadTasks(activeChatId)}
              className="text-gray-400 hover:text-gray-600 p-1 rounded-md cursor-pointer shrink-0"
              title="Aggiorna task"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

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

                  {/* ACTION CARD: RICHIESTA DI APPROVAZIONE SICURA */}
                  {card && card.status === 'waiting_approval' && card.approval_id && (
                    <div className="bg-amber-50/90 border border-amber-300 rounded-2xl p-4 shadow-sm max-w-xl text-amber-950 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <ShieldCheck className="w-4 h-4 text-amber-700" />
                          <span className="font-bold text-xs text-amber-900">
                            Autorizzazione Richiesta (Hardening Fase 1)
                          </span>
                        </div>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-200 text-amber-900 border border-amber-300">
                          In attesa
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-amber-950">{card.title}</p>
                      {card.details && <p className="text-xs text-amber-800">{card.details}</p>}
                      <div className="flex items-center gap-2 pt-1">
                        <button
                          onClick={() => handleApprove(card.approval_id)}
                          disabled={actionLoading === card.approval_id}
                          className="flex-1 py-1.5 px-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition disabled:opacity-50 cursor-pointer flex items-center justify-center gap-1.5"
                        >
                          {actionLoading === card.approval_id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          )}
                          Approva ed Esegui
                        </button>
                        <button
                          onClick={() => handleReject(card.approval_id)}
                          disabled={actionLoading === card.approval_id}
                          className="py-1.5 px-3 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded-xl text-xs font-semibold transition disabled:opacity-50 cursor-pointer flex items-center justify-center gap-1"
                        >
                          <X className="w-3.5 h-3.5" />
                          Rifiuta
                        </button>
                      </div>
                    </div>
                  )}

                  {/* ACTION CARD: SCREENSHOT MONITOR (DONE) */}
                  {card && card.status === 'done' && card.screenshot_b64 && (
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

          {/* TOOL PROGRESS INTERMEDIATE STATUS (FASE 4) */}
          {toolProgress && (
            <div className="flex items-center gap-2 text-xs py-1.5 px-3 bg-blue-50 border border-blue-200 text-blue-800 rounded-full w-fit animate-pulse shadow-xs">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
              <span className="font-semibold">{toolProgress.bot_name}:</span>
              <span>{toolProgress.stage}</span>
            </div>
          )}

          {/* STREAMING MESSAGE PROGRESSIVE RENDER (FASE 4) */}
          {streamingMessage && (
            <div className="flex items-start gap-3">
              <div className="shrink-0 mt-1">
                <BlobAvatar shape="squircle" color="#10B981" size={36} status="working" />
              </div>
              <div className="flex-1 max-w-2xl space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-emerald-600">
                    {streamingMessage.sender_name}
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-medium animate-pulse">
                    in generazione (live)
                  </span>
                </div>
                <div className="bg-[#F6F6F4] text-gray-800 px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed whitespace-pre-wrap">
                  {streamingMessage.content}
                  <span className="inline-block w-1.5 h-4 ml-1 bg-emerald-500 animate-pulse align-middle" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 3. INPUT BAR */}
        <div className="p-4 bg-white border-t border-gray-100 relative">
          {showAttachMenu && (
            <div className="absolute bottom-20 left-6 bg-white border border-gray-200 rounded-2xl shadow-xl p-2 w-64 z-50 space-y-1">
              <button
                onClick={() => {
                  setShowAttachMenu(false);
                  handleSendMessage('Ispeziona il mio schermo attuale con inspect_screen e dimmi cosa vedi.');
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-xl cursor-pointer"
              >
                <Camera className="w-4 h-4 text-orange-500" />
                <span>Ispeziona Schermo Live (Sola Lettura)</span>
              </button>
              <button
                onClick={() => {
                  setShowAttachMenu(false);
                  fileInputRef.current?.click();
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-100 rounded-xl cursor-pointer"
              >
                <FolderOpen className="w-4 h-4 text-blue-500" />
                <span>Allega percorso file dal workspace</span>
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

          {/* BANNER STATO CONNESSIONE BACKEND */}
          {backendReady === false && (
            <div className="mb-2 p-2.5 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-xs text-rose-800 shadow-xs animate-in fade-in">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Backend di CoworkerOS (127.0.0.1:8000) non pronto o disconnesso. Avvio in corso...</span>
              </div>
              <button
                onClick={loadBootstrap}
                className="px-2.5 py-1 bg-rose-100 hover:bg-rose-200 text-rose-900 rounded-xl font-bold cursor-pointer transition text-[11px]"
              >
                Riconnetti
              </button>
            </div>
          )}

          {/* BANNER ERRORE INVIO MESSAGGIO (CON TESTO PRESERVATO) */}
          {sendError && (
            <div className="mb-2 p-2.5 bg-amber-50 border border-amber-200 rounded-2xl flex items-center justify-between text-xs text-amber-900 shadow-xs animate-in fade-in">
              <div className="flex items-center gap-2 min-w-0 pr-2">
                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                <span className="truncate">{sendError}</span>
              </div>
              <button
                onClick={() => setSendError(null)}
                className="p-1 hover:bg-amber-100 rounded-xl text-amber-700 cursor-pointer"
                title="Chiudi avviso"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

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
              placeholder={`Scrivi un messaggio a ${activeChat?.title || 'Chief'}... (es. chiedi un'analisi sicura o ispezione)`}
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

      {/* 4. MODALE CREA COWOKER / STANZA */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-3xl p-6 w-[460px] shadow-2xl border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-base">Crea in CoworkerOS</h3>
              <button onClick={() => setShowNewModal(false)} className="p-1 hover:bg-gray-100 rounded-full cursor-pointer">
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
                    placeholder="es. Secure Automation Crew"
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
                          className={`flex items-center gap-2 p-2 rounded-xl border text-left text-xs cursor-pointer ${
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
                  className="w-full py-2.5 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 cursor-pointer"
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
                  placeholder="Ruolo (es. Security Inspector)"
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
                      className={`px-2 py-1 text-[11px] rounded-lg border cursor-pointer ${
                        newBotShape === sh ? 'bg-gray-900 text-white' : 'bg-gray-50'
                      }`}
                    >
                      {sh}
                    </button>
                  ))}
                </div>
                <button
                  onClick={handleCreateBot}
                  className="w-full py-2.5 bg-gray-900 text-white rounded-xl text-sm font-semibold hover:bg-gray-800 cursor-pointer"
                >
                  Crea Coworker
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 5. MODALE IMPOSTAZIONI & SICUREZZA */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]">
          <div className="bg-white rounded-3xl p-6 w-[480px] shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
                <h3 className="font-bold text-base">Sicurezza & Impostazioni</h3>
              </div>
              <button onClick={() => setShowSettingsModal(false)} className="p-1 hover:bg-gray-100 rounded-full cursor-pointer">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-2xl border border-gray-200 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Token Locale Loopback:</span>
                <span className="font-mono font-bold text-gray-800">{maskedToken || 'Protetto'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Stato Autenticazione:</span>
                <span className="text-emerald-600 font-semibold">● Attivo su 127.0.0.1</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-gray-600 block mb-1">
                Aggiorna Gemini API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder={maskedKey ? `Attuale: ${maskedKey}` : 'Incolla GEMINI_API_KEY...'}
                  className="flex-1 px-3 py-2 border rounded-xl text-sm"
                />
                <button
                  onClick={handleSaveApiKey}
                  className="px-4 py-2 bg-gray-900 text-white rounded-xl text-xs font-semibold hover:bg-gray-800 cursor-pointer"
                >
                  Salva
                </button>
              </div>
            </div>

            <div className="pt-2 border-t border-gray-200">
              <button
                onClick={handleResetDatabase}
                className="w-full py-2 bg-rose-50 text-rose-700 hover:bg-rose-100 rounded-xl text-xs font-semibold border border-rose-200 transition cursor-pointer"
              >
                Reset Database & Svuota Cronologia
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 6. MODALE LIVE MONITOR INSPECTOR */}
      {showInspectorModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-6">
          <div className="bg-white rounded-3xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-base">Live Monitor & Windows 11 Inspector (2880x1920 HiDPI)</h3>
                <p className="text-xs text-gray-500">
                  Metodo cattura: <b>{inspectorData?.capture_method || 'In corso...'}</b> • Risoluzione fisica: <b>{inspectorData?.screen_width}x{inspectorData?.screen_height}</b>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={openInspector}
                  className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 hover:bg-gray-200 rounded-xl text-xs font-semibold cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingInspector ? 'animate-spin' : ''}`} />
                  Aggiorna
                </button>
                <button onClick={() => setShowInspectorModal(false)} className="p-1.5 hover:bg-gray-100 rounded-full cursor-pointer">
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

      {/* 7. MODALE MEMORIA PERSISTENTE INTELLIGENTE (FASE 2B) */}
      {showMemoryModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-6">
          <div className="bg-white rounded-3xl p-6 max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-gray-200">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center">
                  <Brain className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-gray-900">Memoria Persistente Intelligente</h3>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200">
                      SQLite FTS5
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">Ricerca semantica ibrida, deduplicazione e isolamento progetti</p>
                </div>
              </div>
              <button
                onClick={() => setShowMemoryModal(false)}
                className="p-1.5 hover:bg-gray-100 rounded-full cursor-pointer text-gray-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Controls Bar: Search + Auto Memory Toggle */}
            <div className="py-3 flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 shrink-0">
              <div className="flex-1 relative min-w-[200px]">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={memorySearch}
                  onChange={(e) => {
                    setMemorySearch(e.target.value);
                    loadMemoriesList(e.target.value, memoryTypeFilter);
                  }}
                  placeholder="Cerca nella memoria locale (FTS5 + semantica)..."
                  className="w-full pl-9 pr-3 py-1.5 rounded-xl border border-gray-200 text-xs focus:outline-none focus:border-purple-400"
                />
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowNewMemoryForm(!showNewMemoryForm)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-semibold cursor-pointer transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Nuova Memoria</span>
                </button>

                <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-xl border text-xs">
                  <span className="text-[11px] text-gray-600 font-medium">Auto-memorizza:</span>
                  <button
                    onClick={handleToggleAutoMemory}
                    className={`px-2 py-0.5 rounded-md text-[10px] font-bold cursor-pointer transition ${
                      memorySettings.auto_memory_enabled
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-gray-200 text-gray-600'
                    }`}
                  >
                    {memorySettings.auto_memory_enabled ? 'ON' : 'OFF'}
                  </button>
                </div>
              </div>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-1.5 py-2 overflow-x-auto shrink-0 text-xs border-b border-gray-100">
              {['all', 'fact', 'preference', 'decision', 'task_outcome', 'project'].map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setMemoryTypeFilter(t);
                    loadMemoriesList(memorySearch, t);
                  }}
                  className={`px-2.5 py-1 rounded-lg font-medium text-xs cursor-pointer capitalize ${
                    memoryTypeFilter === t
                      ? 'bg-purple-100 text-purple-800 font-bold'
                      : 'text-gray-500 hover:bg-gray-100'
                  }`}
                >
                  {t === 'all' ? 'Tutte' : t}
                </button>
              ))}
            </div>

            {/* Inline New Memory Form */}
            {showNewMemoryForm && (
              <div className="bg-purple-50/70 border border-purple-200 rounded-2xl p-3 my-2 text-xs space-y-2 shrink-0">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-purple-900">Aggiungi Nuova Memoria</span>
                  <select
                    value={newMemoryType}
                    onChange={(e) => setNewMemoryType(e.target.value)}
                    className="px-2 py-1 rounded-lg border bg-white text-xs font-semibold"
                  >
                    <option value="fact">fact</option>
                    <option value="preference">preference</option>
                    <option value="decision">decision</option>
                    <option value="project">project</option>
                  </select>
                </div>
                <textarea
                  value={newMemoryContent}
                  onChange={(e) => setNewMemoryContent(e.target.value)}
                  placeholder="Es. L'utente preferisce risposte concise e codice TypeScript..."
                  className="w-full p-2 rounded-xl border border-purple-200 text-xs bg-white focus:outline-none"
                  rows={2}
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setShowNewMemoryForm(false)}
                    className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-gray-600 cursor-pointer"
                  >
                    Annulla
                  </button>
                  <button
                    onClick={handleCreateMemory}
                    className="px-3 py-1 bg-purple-600 text-white font-semibold rounded-lg hover:bg-purple-700 cursor-pointer"
                  >
                    Salva Memoria
                  </button>
                </div>
              </div>
            )}

            {/* Memory List */}
            <div className="flex-1 overflow-y-auto py-2 space-y-2 select-text">
              {loadingMemories ? (
                <div className="flex items-center justify-center py-8 text-xs text-gray-500 gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-purple-600" />
                  <span>Caricamento memorie locali...</span>
                </div>
              ) : memories.length === 0 ? (
                <div className="text-center py-12 text-xs text-gray-400">
                  Nessuna memoria trovata per questa ricerca.
                </div>
              ) : (
                memories.map((m) => {
                  const isEditing = editingMemoryId === m.id;
                  const hasConflict = m.metadata?.has_conflict;
                  let typeColor = 'bg-gray-100 text-gray-700 border-gray-200';
                  if (m.memory_type === 'preference') typeColor = 'bg-pink-50 text-pink-700 border-pink-200';
                  else if (m.memory_type === 'decision') typeColor = 'bg-blue-50 text-blue-700 border-blue-200';
                  else if (m.memory_type === 'task_outcome') typeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
                  else if (m.memory_type === 'project') typeColor = 'bg-amber-50 text-amber-700 border-amber-200';

                  return (
                    <div
                      key={m.id}
                      className="bg-[#FAFAFA] border border-gray-200 rounded-2xl p-3 text-xs space-y-1.5 hover:border-gray-300 transition"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded-md font-bold uppercase tracking-wider text-[9px] border ${typeColor}`}>
                            {m.memory_type}
                          </span>
                          <span className="text-[10px] text-gray-400">
                            Origine: <b>{m.provenance_type}</b> ({m.provenance_id || 'manuale'})
                          </span>
                          <span className="text-[10px] text-gray-500 font-semibold">
                            • Affidabilità: {Math.round((m.confidence || 1) * 100)}%
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => {
                              if (isEditing) {
                                setEditingMemoryId(null);
                              } else {
                                setEditingMemoryId(m.id);
                                setEditingMemoryContent(m.content);
                              }
                            }}
                            className="p-1 hover:bg-gray-200 rounded text-gray-500 cursor-pointer"
                            title="Modifica memoria"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeleteMemoryItem(m.id)}
                            className="p-1 hover:bg-rose-100 rounded text-gray-400 hover:text-rose-600 cursor-pointer"
                            title="Elimina memoria"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>

                      {hasConflict && (
                        <div className="bg-amber-50 border border-amber-200 px-2 py-1 rounded-lg text-[10px] text-amber-800 font-semibold">
                          ⚠️ Attenzione: Questa informazione è in conflitto con un'altra memoria attiva registrata.
                        </div>
                      )}

                      {isEditing ? (
                        <div className="space-y-1 pt-1">
                          <textarea
                            value={editingMemoryContent}
                            onChange={(e) => setEditingMemoryContent(e.target.value)}
                            className="w-full p-2 border rounded-xl bg-white text-xs"
                            rows={2}
                          />
                          <div className="flex justify-end gap-1.5">
                            <button
                              onClick={() => setEditingMemoryId(null)}
                              className="px-2.5 py-1 bg-gray-100 rounded-lg text-gray-600 text-[11px] cursor-pointer"
                            >
                              Annulla
                            </button>
                            <button
                              onClick={() => handleSaveEditMemory(m.id)}
                              className="px-2.5 py-1 bg-purple-600 text-white rounded-lg font-semibold text-[11px] cursor-pointer"
                            >
                              Salva
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-gray-800 text-xs leading-relaxed whitespace-pre-wrap">{m.content}</p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
      {/* 8. MODALE AUTOMAZIONI, CONSUMI & NOTIFICHE (FASE 2C) */}
      {showSchedulerModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[9999] p-6">
          <div className="bg-white rounded-3xl p-6 max-w-4xl w-full max-h-[88vh] flex flex-col shadow-2xl border border-gray-200">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center">
                  <Clock className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-base text-gray-900">Automazioni & Controllo Consumi</h3>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                      Fase 2C
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">Pianificazione persistente, quote token e notifiche locali</p>
                </div>
              </div>
              <button
                onClick={() => setShowSchedulerModal(false)}
                className="p-1.5 hover:bg-gray-100 rounded-full cursor-pointer text-gray-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tabs Bar */}
            <div className="py-2.5 flex items-center justify-between border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => setSchedulerTab('jobs')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition ${
                    schedulerTab === 'jobs'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Attività ({scheduledJobs.length})
                </button>
                <button
                  onClick={() => setSchedulerTab('history')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition ${
                    schedulerTab === 'history'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Cronologia ({schedulerHistory.length})
                </button>
                <button
                  onClick={() => setSchedulerTab('usage')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition ${
                    schedulerTab === 'usage'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Consumi & Quote
                </button>
                <button
                  onClick={() => setSchedulerTab('notifications')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition relative ${
                    schedulerTab === 'notifications'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  Notifiche
                  {unreadNotifCount > 0 && (
                    <span className="ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] bg-red-500 text-white font-bold">
                      {unreadNotifCount}
                    </span>
                  )}
                </button>
              </div>

              {schedulerTab === 'jobs' && (
                <button
                  onClick={() => setShowNewJobForm(!showNewJobForm)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold cursor-pointer transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Nuova Attività</span>
                </button>
              )}

              {schedulerTab === 'notifications' && notificationsList.some((n) => !n.is_read) && (
                <button
                  onClick={handleMarkAllNotifsRead}
                  className="text-xs text-blue-600 hover:underline font-semibold cursor-pointer"
                >
                  Segna tutte come lette
                </button>
              )}
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto py-3 space-y-3">
              {/* TAB 1: ATTIVITÀ PROGRAMMATE */}
              {schedulerTab === 'jobs' && (
                <>
                  {showNewJobForm && (
                    <div className="p-4 bg-blue-50/60 rounded-2xl border border-blue-200 space-y-3">
                      <h4 className="font-bold text-xs text-blue-900">Pianifica Nuova Attività</h4>
                      <div className="grid grid-cols-2 gap-3 text-xs">
                        <div>
                          <label className="block text-gray-600 text-[11px] mb-1 font-medium">Nome Attività</label>
                          <input
                            type="text"
                            placeholder="Es. Controllo report mattutino"
                            value={newJobForm.name}
                            onChange={(e) => setNewJobForm({ ...newJobForm, name: e.target.value })}
                            className="w-full p-2 border rounded-xl bg-white"
                          />
                        </div>
                        <div>
                          <label className="block text-gray-600 text-[11px] mb-1 font-medium">Coworker Responsabile</label>
                          <select
                            value={newJobForm.target_bot_id}
                            onChange={(e) => setNewJobForm({ ...newJobForm, target_bot_id: e.target.value })}
                            className="w-full p-2 border rounded-xl bg-white"
                          >
                            <option value="chief">Chief (Coordinatore)</option>
                            <option value="architect">Architect (Analisi)</option>
                            <option value="builder">Builder (Esecutore)</option>
                            <option value="scout">Scout (Ricerca)</option>
                            <option value="archivist">Archivist (Memoria)</option>
                          </select>
                        </div>
                      </div>

                      <div>
                        <label className="block text-gray-600 text-[11px] mb-1 font-medium">Istruzione / Richiesta per l'agente</label>
                        <textarea
                          placeholder="Descrivi l'obiettivo dettagliato dell'attività da eseguire automaticamente..."
                          value={newJobForm.prompt}
                          onChange={(e) => setNewJobForm({ ...newJobForm, prompt: e.target.value })}
                          className="w-full p-2 border rounded-xl bg-white text-xs"
                          rows={2}
                        />
                      </div>

                      <div className="grid grid-cols-3 gap-3 text-xs">
                        <div>
                          <label className="block text-gray-600 text-[11px] mb-1 font-medium">Tipo Pianificazione</label>
                          <select
                            value={newJobForm.schedule_type}
                            onChange={(e) => setNewJobForm({ ...newJobForm, schedule_type: e.target.value })}
                            className="w-full p-2 border rounded-xl bg-white"
                          >
                            <option value="interval">A intervallo (ricorrente)</option>
                            <option value="daily">Giornaliero (ora fissa)</option>
                            <option value="weekly">Settimanale (giorni scelti)</option>
                            <option value="once">Esecuzione singola</option>
                          </select>
                        </div>

                        {newJobForm.schedule_type === 'interval' && (
                          <div>
                            <label className="block text-gray-600 text-[11px] mb-1 font-medium">Intervallo (secondi)</label>
                            <input
                              type="number"
                              value={newJobForm.interval_seconds}
                              onChange={(e) => setNewJobForm({ ...newJobForm, interval_seconds: e.target.value })}
                              className="w-full p-2 border rounded-xl bg-white"
                            />
                          </div>
                        )}

                        {(newJobForm.schedule_type === 'daily' || newJobForm.schedule_type === 'weekly') && (
                          <div>
                            <label className="block text-gray-600 text-[11px] mb-1 font-medium">Orario (HH:MM)</label>
                            <input
                              type="text"
                              value={newJobForm.time}
                              onChange={(e) => setNewJobForm({ ...newJobForm, time: e.target.value })}
                              placeholder="09:00"
                              className="w-full p-2 border rounded-xl bg-white"
                            />
                          </div>
                        )}

                        {newJobForm.schedule_type === 'once' && (
                          <div>
                            <label className="block text-gray-600 text-[11px] mb-1 font-medium">Data e Ora (ISO)</label>
                            <input
                              type="text"
                              value={newJobForm.target_time}
                              onChange={(e) => setNewJobForm({ ...newJobForm, target_time: e.target.value })}
                              placeholder="2026-10-27T10:00:00+01:00"
                              className="w-full p-2 border rounded-xl bg-white"
                            />
                          </div>
                        )}

                        <div>
                          <label className="block text-gray-600 text-[11px] mb-1 font-medium">Policy Job Mancati</label>
                          <select
                            value={newJobForm.missed_job_policy}
                            onChange={(e) => setNewJobForm({ ...newJobForm, missed_job_policy: e.target.value })}
                            className="w-full p-2 border rounded-xl bg-white"
                          >
                            <option value="skip">Skip (salta al prossimo futuro)</option>
                            <option value="run_once">Run Once (esegui 1 volta sola)</option>
                          </select>
                        </div>
                      </div>

                      <div className="flex justify-end gap-2 pt-1">
                        <button
                          onClick={() => setShowNewJobForm(false)}
                          className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl text-xs font-semibold cursor-pointer"
                        >
                          Annulla
                        </button>
                        <button
                          onClick={handleCreateJob}
                          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold cursor-pointer"
                        >
                          Salva e Pianifica
                        </button>
                      </div>
                    </div>
                  )}

                  {scheduledJobs.length === 0 ? (
                    <div className="p-8 text-center text-gray-400 text-xs">
                      Nessuna attività programmata configurata. Clicca su "+ Nuova Attività" per pianificare lavori autonomi.
                    </div>
                  ) : (
                    scheduledJobs.map((job) => {
                      const isActive = job.status === 'active';
                      const isPaused = job.status === 'paused';
                      return (
                        <div
                          key={job.id}
                          className="p-3.5 bg-gray-50/70 border border-gray-200 rounded-2xl flex items-start justify-between gap-4"
                        >
                          <div className="space-y-1 flex-1">
                            <div className="flex items-center gap-2">
                              <h4 className="font-bold text-xs text-gray-900">{job.name}</h4>
                              <span
                                className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  isActive
                                    ? 'bg-emerald-100 text-emerald-800'
                                    : isPaused
                                    ? 'bg-amber-100 text-amber-800'
                                    : 'bg-gray-200 text-gray-600'
                                }`}
                              >
                                {job.status}
                              </span>
                              <span className="text-[10px] text-gray-500 bg-white border px-2 py-0.5 rounded-md">
                                {job.schedule_type}
                              </span>
                              <span className="text-[10px] text-gray-500">
                                Agente: <b>{job.target_bot_id}</b>
                              </span>
                            </div>
                            <p className="text-gray-700 text-xs leading-relaxed">{job.prompt}</p>
                            <div className="flex items-center gap-4 text-[11px] text-gray-500 pt-1">
                              <span>
                                Prossima esecuzione: <b>{job.next_run_at ? new Date(job.next_run_at).toLocaleString() : 'Nessuna'}</b>
                              </span>
                              {job.last_run_at && (
                                <span>
                                  Ultima: <b>{new Date(job.last_run_at).toLocaleString()}</b>
                                </span>
                              )}
                              <span>Fuso: {job.timezone}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              onClick={() => handleRunJobNow(job.id)}
                              className="p-1.5 bg-white hover:bg-blue-50 text-blue-600 border rounded-xl text-xs flex items-center gap-1 cursor-pointer"
                              title="Esegui subito"
                            >
                              <PlayCircle className="w-4 h-4" />
                              <span className="text-[10px] font-semibold">Esegui</span>
                            </button>
                            <button
                              onClick={() => handleTogglePauseJob(job)}
                              className="p-1.5 bg-white hover:bg-gray-100 text-gray-600 border rounded-xl text-xs cursor-pointer"
                              title={isActive ? 'Metti in pausa' : 'Riattiva'}
                            >
                              {isActive ? <PauseCircle className="w-4 h-4 text-amber-600" /> : <Play className="w-4 h-4 text-emerald-600" />}
                            </button>
                            <button
                              onClick={() => handleDeleteJob(job.id)}
                              className="p-1.5 bg-white hover:bg-red-50 text-red-600 border rounded-xl text-xs cursor-pointer"
                              title="Elimina attività"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </>
              )}

              {/* TAB 2: CRONOLOGIA ESECUZIONI */}
              {schedulerTab === 'history' && (
                <div className="space-y-2">
                  {schedulerHistory.length === 0 ? (
                    <div className="p-8 text-center text-gray-400 text-xs">
                      Nessuna esecuzione registrata nella cronologia.
                    </div>
                  ) : (
                    schedulerHistory.map((exec) => (
                      <div
                        key={exec.id}
                        className="p-3 bg-gray-50/70 border border-gray-200 rounded-xl flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                exec.status === 'success'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : exec.status === 'failed'
                                  ? 'bg-red-100 text-red-800'
                                  : exec.status === 'waiting_approval'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-gray-200 text-gray-600'
                              }`}
                            >
                              {exec.status}
                            </span>
                            <span className="font-semibold text-gray-800">Job: {exec.job_id}</span>
                            {exec.task_id && (
                              <span className="text-[10px] text-gray-500 bg-white border px-1.5 py-0.5 rounded">
                                Task: {exec.task_id}
                              </span>
                            )}
                          </div>
                          {exec.error_message && (
                            <p className="text-red-600 text-[11px]">{exec.error_message}</p>
                          )}
                        </div>
                        <div className="text-right text-[11px] text-gray-500">
                          <div>{new Date(exec.executed_at).toLocaleString()}</div>
                          <div>Durata: {exec.duration_ms} ms</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 3: CONSUMI E QUOTE */}
              {schedulerTab === 'usage' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3.5 bg-blue-50/70 border border-blue-200 rounded-2xl">
                      <span className="text-[11px] font-bold text-blue-800 uppercase tracking-wider block">Richieste Oggi</span>
                      <div className="text-xl font-bold text-blue-900 mt-1">
                        {usageSummary.requests_count || 0}
                        <span className="text-xs font-normal text-blue-700 ml-1">/ {usageLimits.max_requests_daily || 200} max</span>
                      </div>
                    </div>
                    <div className="p-3.5 bg-purple-50/70 border border-purple-200 rounded-2xl">
                      <span className="text-[11px] font-bold text-purple-800 uppercase tracking-wider block">Token Rilevati</span>
                      <div className="text-xl font-bold text-purple-900 mt-1">
                        {(usageSummary.total_tokens || 0).toLocaleString()}
                      </div>
                      <span className="text-[10px] text-purple-600">In: {(usageSummary.input_tokens || 0).toLocaleString()} • Out: {(usageSummary.output_tokens || 0).toLocaleString()}</span>
                    </div>
                    <div className="p-3.5 bg-emerald-50/70 border border-emerald-200 rounded-2xl">
                      <span className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider block">Stima Costi (USD)</span>
                      <div className="text-xl font-bold text-emerald-900 mt-1">
                        ${usageSummary.estimated_cost_usd || 0.0}
                      </div>
                      <span className="text-[10px] text-emerald-700">Calcolo su tariffe standard</span>
                    </div>
                  </div>

                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 font-medium">
                    ⚠️ {usageSummary.is_estimate_notice || "Stima puramente indicativa dei consumi, non costituisce fattura reale."}
                  </div>

                  <div className="p-4 bg-gray-50 border border-gray-200 rounded-2xl space-y-3">
                    <h4 className="font-bold text-xs text-gray-900">Configurazione Quote e Limiti di Sicurezza</h4>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div>
                        <label className="block text-gray-600 text-[11px] mb-1">Max Richieste / Task</label>
                        <input
                          type="number"
                          defaultValue={usageLimits.max_requests_per_task || 15}
                          onBlur={(e) => handleSaveLimit('max_requests_per_task', e.target.value)}
                          className="w-full p-2 border rounded-xl bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-gray-600 text-[11px] mb-1">Max Richieste Giornaliere</label>
                        <input
                          type="number"
                          defaultValue={usageLimits.max_requests_daily || 200}
                          onBlur={(e) => handleSaveLimit('max_requests_daily', e.target.value)}
                          className="w-full p-2 border rounded-xl bg-white"
                        />
                      </div>
                      <div>
                        <label className="block text-gray-600 text-[11px] mb-1">Max Task Contemporanei</label>
                        <input
                          type="number"
                          defaultValue={usageLimits.max_concurrent_tasks || 3}
                          onBlur={(e) => handleSaveLimit('max_concurrent_tasks', e.target.value)}
                          className="w-full p-2 border rounded-xl bg-white"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: NOTIFICHE LOCALI */}
              {schedulerTab === 'notifications' && (
                <div className="space-y-2">
                  {notificationsList.length === 0 ? (
                    <div className="p-8 text-center text-gray-400 text-xs">
                      Nessuna notifica registrata.
                    </div>
                  ) : (
                    notificationsList.map((n) => (
                      <div
                        key={n.id}
                        className={`p-3 border rounded-xl flex items-start justify-between gap-3 text-xs ${
                          n.is_read ? 'bg-gray-50/50 border-gray-200' : 'bg-blue-50/40 border-blue-200'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                n.category === 'task_completed'
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : n.category === 'task_failed'
                                  ? 'bg-red-100 text-red-800'
                                  : n.category === 'approval_needed'
                                  ? 'bg-amber-100 text-amber-800'
                                  : 'bg-orange-100 text-orange-800'
                              }`}
                            >
                              {n.category}
                            </span>
                            <h5 className="font-bold text-gray-900">{n.title}</h5>
                            <span className="text-[10px] text-gray-400">{new Date(n.created_at).toLocaleTimeString()}</span>
                          </div>
                          <p className="text-gray-700 text-xs leading-relaxed">{n.message}</p>
                        </div>
                        {!n.is_read && (
                          <button
                            onClick={() => handleMarkNotifRead(n.id)}
                            className="px-2 py-1 bg-white hover:bg-gray-100 text-blue-600 border border-blue-200 rounded-lg text-[10px] font-semibold shrink-0 cursor-pointer"
                          >
                            Segna letta
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 5. MODALE CONFERMA PULIZIA CHAT DI TEST */}
      {showCleanupModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-[9999] p-4">
          <div className="bg-white rounded-3xl p-6 max-w-lg w-full shadow-2xl border border-gray-100 flex flex-col max-h-[85vh] animate-in fade-in duration-200">
            <div className="flex items-center justify-between pb-3 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-2xl bg-amber-100 flex items-center justify-center text-amber-700">
                  <Trash2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-gray-950">Pulizia Chat di Test</h3>
                  <p className="text-xs text-gray-500">Rimuovi in sicurezza le sessioni generate dai benchmark automatici</p>
                </div>
              </div>
              <button
                onClick={() => setShowCleanupModal(false)}
                className="p-2 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-700 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="py-3 text-xs text-gray-600 shrink-0">
              <p className="mb-2">
                Sono state individuate <b>{testChats.length}</b> chat generate automaticamente durante i collaudi tecnici.
                Le tue conversazioni e i bot principali (Chief, Architect, Builder, Scout, Archivist) <b>sono protetti</b>.
              </p>
              <div className="flex items-center justify-between pt-1">
                <span className="font-semibold text-gray-800">
                  Selezionate: {selectedTestChats.length} su {testChats.length}
                </span>
                <div className="space-x-2">
                  <button
                    onClick={() => setSelectedTestChats(testChats.map((c) => c.id))}
                    className="text-xs text-blue-600 hover:underline cursor-pointer"
                  >
                    Seleziona tutte
                  </button>
                  <span className="text-gray-300">|</span>
                  <button
                    onClick={() => setSelectedTestChats([])}
                    className="text-xs text-gray-500 hover:underline cursor-pointer"
                  >
                    Deseleziona
                  </button>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-1.5 my-2 p-2 bg-gray-50 rounded-2xl border border-gray-200 max-h-64 text-xs">
              {testChats.map((tc) => {
                const isChecked = selectedTestChats.includes(tc.id);
                return (
                  <label
                    key={tc.id}
                    className={`flex items-center gap-3 p-2 rounded-xl cursor-pointer transition ${
                      isChecked ? 'bg-amber-50/80 border border-amber-200/80' : 'hover:bg-white border border-transparent'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedTestChats((prev) => [...prev, tc.id]);
                        } else {
                          setSelectedTestChats((prev) => prev.filter((id) => id !== tc.id));
                        }
                      }}
                      className="rounded text-amber-600 focus:ring-amber-500 w-4 h-4"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="font-semibold text-gray-900 truncate">{tc.title}</div>
                      <div className="text-[10px] text-gray-400 truncate">{tc.id}</div>
                    </div>
                  </label>
                );
              })}
            </div>

            <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-3 shrink-0">
              <button
                onClick={() => setShowCleanupModal(false)}
                disabled={cleanupLoading}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-700 hover:bg-gray-100 transition cursor-pointer"
              >
                Annulla
              </button>
              <button
                onClick={handlePerformCleanup}
                disabled={cleanupLoading || selectedTestChats.length === 0}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-rose-600 hover:bg-rose-700 text-white transition disabled:opacity-50 shadow-md shadow-rose-200 cursor-pointer"
              >
                {cleanupLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Eliminazione...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Elimina {selectedTestChats.length} Chat di Test</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
