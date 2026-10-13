import React, { useState, useRef, useEffect } from 'react';
import { MoreHorizontal, Pencil, Trash2, Check, X, RotateCw, MessageSquareDashed } from 'lucide-react';
import type { ChatSession } from '../../types';
import { groupSessionsByDate } from '../../utils/dateGrouping';

interface ChatHistoryListProps {
  sessions: ChatSession[];
  activeSessionId: number | null;
  onSelectSession: (sessionId: number) => void;
  onRenameSession?: (sessionId: number, newTitle: string) => Promise<void>;
  onDeleteSession?: (sessionId: number) => Promise<void>;
  searchQuery?: string;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export const ChatHistoryList: React.FC<ChatHistoryListProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  searchQuery = '',
  isLoading = false,
  error = null,
  onRetry,
}) => {
  const [menuSessionId, setMenuSessionId] = useState<number | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  // Close context menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuSessionId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filteredSessions = searchQuery.trim()
    ? sessions.filter((s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase().trim())
      )
    : sessions;

  const grouped = groupSessionsByDate(filteredSessions);

  const startEditing = (s: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingSessionId(s.id);
    setEditTitle(s.title);
    setMenuSessionId(null);
  };

  const handleSaveRename = async (sessionId: number, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const clean = editTitle.trim();
    if (clean && onRenameSession) {
      await onRenameSession(sessionId, clean);
    }
    setEditingSessionId(null);
  };

  const handleDelete = async (sessionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuSessionId(null);
    if (window.confirm('Bạn có chắc chắn muốn xoá cuộc trò chuyện này?')) {
      if (onDeleteSession) {
        await onDeleteSession(sessionId);
      }
    }
  };

  // Loading Skeleton
  if (isLoading && sessions.length === 0) {
    return (
      <div className="flex-1 p-3.5 space-y-3 animate-pulse">
        <div className="h-3 w-16 bg-gray-200/80 rounded"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
        <div className="h-3 w-20 bg-gray-200/80 rounded mt-4"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
      </div>
    );
  }

  // Error State with Retry
  if (error && sessions.length === 0) {
    return (
      <div className="flex-1 p-4 flex flex-col items-center justify-center text-center">
        <p className="text-xs text-rose-600 mb-2">{error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition"
          >
            <RotateCw className="w-3.5 h-3.5" />
            <span>Thử lại</span>
          </button>
        )}
      </div>
    );
  }

  // Empty State
  if (filteredSessions.length === 0) {
    return (
      <div className="flex-1 p-6 flex flex-col items-center justify-center text-center text-[#8E8E93] select-none">
        <MessageSquareDashed className="w-8 h-8 stroke-1 mb-2 text-gray-300" />
        <p className="text-xs font-normal">
          {searchQuery
            ? 'Không tìm thấy cuộc trò chuyện phù hợp.'
            : 'Chưa có cuộc trò chuyện nào.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3.5 select-none relative">
      {grouped.map((group) => (
        <div key={group.groupName} className="space-y-0.5">
          {/* Nhãn nhóm thời gian (chỉ hiện khi nhóm có dữ liệu) */}
          <div className="px-3 py-1 text-[11px] font-semibold text-[#6B6B6B]">
            {group.groupName}
          </div>

          {/* Danh sách các cuộc trò chuyện */}
          <div className="space-y-0.5">
            {group.sessions.map((session) => {
              const isActive = activeSessionId === session.id;
              const isEditing = editingSessionId === session.id;
              const isMenuOpen = menuSessionId === session.id;

              if (isEditing) {
                return (
                  <form
                    key={session.id}
                    onSubmit={(e) => handleSaveRename(session.id, e)}
                    className="flex items-center gap-1 px-2 py-1 bg-white border border-[#F5B800] rounded-xl shadow-xs"
                  >
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      autoFocus
                      className="flex-1 text-xs px-1.5 py-1 text-[#1F1F1F] bg-transparent focus:outline-none"
                    />
                    <button
                      type="submit"
                      className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                      title="Lưu"
                    >
                      <Check className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingSessionId(null)}
                      className="p-1 text-gray-400 hover:bg-gray-100 rounded"
                      title="Huỷ"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </form>
                );
              }

              return (
                <div
                  key={session.id}
                  className={`group relative flex items-center justify-between rounded-xl transition-colors ${
                    isActive
                      ? 'bg-[#ECECF1] text-[#1F1F1F] font-medium'
                      : 'text-[#2D2D2D] hover:bg-[#EBECEF] hover:text-[#1F1F1F]'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    title={session.title}
                    className="w-full text-left px-3 py-1.5 text-xs md:text-[13px] truncate pr-8"
                  >
                    {session.title || 'Cuộc trò chuyện mới'}
                  </button>

                  {/* Nút ba chấm "..." tuỳ chọn */}
                  <div className="absolute right-1 flex items-center">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuSessionId(isMenuOpen ? null : session.id);
                      }}
                      className={`p-1 rounded-md text-gray-400 hover:text-gray-700 transition ${
                        isMenuOpen || isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}
                      title="Tuỳ chọn cuộc trò chuyện"
                      aria-label="Tuỳ chọn cuộc trò chuyện"
                    >
                      <MoreHorizontal className="w-3.5 h-3.5" />
                    </button>

                    {/* Context Menu */}
                    {isMenuOpen && (
                      <div
                        ref={menuRef}
                        className="absolute right-0 top-full mt-1 w-32 bg-white border border-gray-200 rounded-xl shadow-lg p-1 z-50 animate-fade-in text-xs font-normal"
                      >
                        <button
                          type="button"
                          onClick={(e) => startEditing(session, e)}
                          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-gray-700 hover:bg-gray-100 transition"
                        >
                          <Pencil className="w-3.5 h-3.5 text-gray-500" />
                          <span>Đổi tên</span>
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleDelete(session.id, e)}
                          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-rose-600 hover:bg-rose-50 transition"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Xoá</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
