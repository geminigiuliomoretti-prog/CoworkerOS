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
  Cpu,
  Power,
  Loader2,
} from 'lucide-react';
import {
  getSettings,
  saveApiKey,
  resetDatabase,
  getModelStatus,
  setModelProvider,
  startLocalModel,
  stopLocalModel,
} from '../services/api';

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
  const [modelStatus, setModelStatus] = useState(null);
  const [providerMode, setProviderMode] = useState('AUTO');
  const [isModelActionLoading, setIsModelActionLoading] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setUserName(currentUserName);
    setStatusMessage(null);
    setIsResetConfirmOpen(false);

    async function loadSettings() {
      try {
        setIsLoading(true);
        const [data, statusData] = await Promise.all([
          getSettings(),
          getModelStatus().catch(() => null),
        ]);
        if (data?.gemini_api_key) {
          setApiKey(data.gemini_api_key);
        }
        if (statusData) {
          setModelStatus(statusData);
          if (statusData.provider_mode) {
            setProviderMode(statusData.provider_mode);
          }
        }
      } catch (err) {
        console.warn('Failed to load settings:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadSettings();
  }, [isOpen, currentUserName]);

  const handleSetProvider = async (mode) => {
    try {
      setIsModelActionLoading(true);
      const res = await setModelProvider(mode);
      setProviderMode(mode);
      if (res?.status) setModelStatus(res.status);
      setStatusMessage({ type: 'success', text: `Modalità motore impostata su: ${mode}` });
    } catch (err) {
      setStatusMessage({ type: 'error', text: err.message || 'Errore cambio provider' });
    } finally {
      setIsModelActionLoading(false);
    }
  };

  const handleToggleServer = async () => {
    try {
      setIsModelActionLoading(true);
      if (modelStatus?.local_model?.is_alive) {
        await stopLocalModel();
        setStatusMessage({ type: 'success', text: 'llama-server arrestato con successo.' });
      } else {
        const res = await startLocalModel(false);
        if (!res.success) {
          setStatusMessage({ type: 'error', text: res.error || 'Impossibile avviare il modello locale.' });
        } else {
          setStatusMessage({ type: 'success', text: res.message || 'Qwen3.5-4B avviato con successo!' });
        }
      }
      const updated = await getModelStatus();
      if (updated) setModelStatus(updated);
    } catch (err) {
      setStatusMessage({ type: 'error', text: err.message || 'Errore controllo server locale' });
    } finally {
      setIsModelActionLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleSaveApiKey = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setStatusMessage({ type: 'error', text: 'La chiave API non può essere vuota.' });
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

          {/* SEZIONE MOTORE AI: PROVIDER E MODELLO LOCALE */}
          <div className="bg-gray-50 border border-gray-200 rounded-2xl p-4 space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-emerald-600" />
                <span className="text-xs font-bold text-gray-800 uppercase tracking-wider">
                  Motore di Inferenza AI
                </span>
              </div>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-700">
                {modelStatus?.active_provider || providerMode}
              </span>
            </div>

            {/* Pulsanti Modalità */}
            <div>
              <label className="text-[11px] font-medium text-gray-500 block mb-1.5">
                Modalità Operativa:
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleSetProvider('LOCAL')}
                  disabled={isModelActionLoading}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition cursor-pointer flex flex-col items-center gap-0.5 ${
                    providerMode === 'LOCAL'
                      ? 'bg-emerald-50 border-emerald-500 text-emerald-800 shadow-sm'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span>LOCAL</span>
                  <span className="text-[10px] font-normal text-gray-400">Qwen 4B CPU</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleSetProvider('AUTO')}
                  disabled={isModelActionLoading}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition cursor-pointer flex flex-col items-center gap-0.5 ${
                    providerMode === 'AUTO'
                      ? 'bg-indigo-50 border-indigo-500 text-indigo-800 shadow-sm'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span>AUTO</span>
                  <span className="text-[10px] font-normal text-gray-400">Locale + Cloud</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleSetProvider('CLOUD')}
                  disabled={isModelActionLoading}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition cursor-pointer flex flex-col items-center gap-0.5 ${
                    providerMode === 'CLOUD'
                      ? 'bg-blue-50 border-blue-500 text-blue-800 shadow-sm'
                      : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span>CLOUD</span>
                  <span className="text-[10px] font-normal text-gray-400">Gemini Flash</span>
                </button>
              </div>
            </div>

            {/* Dettagli Qwen Locale */}
            <div className="bg-white rounded-xl border border-gray-200 p-3 text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-gray-700">Qwen3.5-4B (llama.cpp CPU):</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  modelStatus?.local_model?.is_alive
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {modelStatus?.local_model?.is_alive ? 'IN ESECUZIONE' : 'ARRESTATO'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-500">
                <div>RAM Libera: <b className="text-gray-800">{modelStatus?.ram_info?.available_gb ?? '-'} GB</b></div>
                <div>Server RSS: <b className="text-gray-800">{modelStatus?.local_model?.server_rss_mb ? `${modelStatus.local_model.server_rss_mb} MB` : '0 MB'}</b></div>
              </div>

              {modelStatus?.ram_info?.available_gb < 3.2 && (
                <div className="text-[11px] text-amber-700 bg-amber-50 p-2 rounded-lg flex items-center gap-1.5 border border-amber-200">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-600" />
                  <span>RAM disponibile limitata. Chiudi altre applicazioni prima di caricare il modello locale.</span>
                </div>
              )}

              <div className="pt-1 flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleToggleServer}
                  disabled={isModelActionLoading}
                  className={`flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer ${
                    modelStatus?.local_model?.is_alive
                      ? 'bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200'
                      : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm'
                  }`}
                >
                  {isModelActionLoading ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Power className="w-3.5 h-3.5" />
                  )}
                  <span>{modelStatus?.local_model?.is_alive ? 'Arresta llama-server' : 'Avvia Qwen3.5-4B Locale'}</span>
                </button>
              </div>
            </div>
          </div>

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
                  Sei sicuro di voler cancellare tutte le chat? Questa azione è irreversibile.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleResetDatabase}
                    disabled={isLoading}
                    className="flex-1 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs transition"
                  >
                    Sì, Cancella Tutto
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
