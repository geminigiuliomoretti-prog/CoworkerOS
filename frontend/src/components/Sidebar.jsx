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
