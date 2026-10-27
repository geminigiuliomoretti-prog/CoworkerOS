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
                {lastUpdated && ` • Ultimo scatto: ${lastUpdated}`}
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
