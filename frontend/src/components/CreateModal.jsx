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
                  {botRole.trim() || 'Ruolo'} • Effort {botEffort}
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
