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
