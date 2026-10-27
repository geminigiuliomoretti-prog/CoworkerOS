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
                  Live Preview • Click to Wobble
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
