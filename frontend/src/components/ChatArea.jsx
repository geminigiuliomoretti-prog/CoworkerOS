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
                  .replace(/^[*-]\s+/, '• ')
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
              {activeWorkingBot ? ` • ${activeWorkingBot.name} is working...` : ' • Ready'}
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
