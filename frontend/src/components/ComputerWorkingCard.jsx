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
