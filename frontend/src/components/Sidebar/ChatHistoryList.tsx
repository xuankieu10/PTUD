import React from 'react';
import { MessageSquare, Clock } from 'lucide-react';
import type { ChatSession } from '../../types';
import { groupSessionsByDate } from '../../utils/dateGrouping';

interface ChatHistoryListProps {
  sessions: ChatSession[];
  activeSessionId: number | null;
  onSelectSession: (sessionId: number) => void;
  searchQuery?: string;
  isLoading?: boolean;
}

export const ChatHistoryList: React.FC<ChatHistoryListProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  searchQuery = '',
  isLoading = false,
}) => {
  // Filter by search query if any
  const filteredSessions = searchQuery.trim()
    ? sessions.filter((s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase().trim())
      )
    : sessions;

  const grouped = groupSessionsByDate(filteredSessions);

  if (isLoading && sessions.length === 0) {
    return (
      <div className="flex-1 p-4 space-y-3 animate-pulse">
        <div className="h-3 w-16 bg-gray-200 rounded"></div>
        <div className="h-8 bg-gray-200/70 rounded-xl"></div>
        <div className="h-8 bg-gray-200/70 rounded-xl"></div>
        <div className="h-3 w-20 bg-gray-200 rounded mt-4"></div>
        <div className="h-8 bg-gray-200/70 rounded-xl"></div>
      </div>
    );
  }

  if (filteredSessions.length === 0) {
    return (
      <div className="flex-1 p-6 flex flex-col items-center justify-center text-center text-[#8E8E93]">
        <Clock className="w-8 h-8 stroke-1 mb-2 text-gray-300" />
        <p className="text-xs">
          {searchQuery
            ? 'Không tìm thấy cuộc trò chuyện phù hợp.'
            : 'Chưa có lịch sử cuộc trò chuyện.'}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-2 py-2 space-y-4">
      {grouped.map((group) => (
        <div key={group.groupName} className="space-y-0.5">
          {/* Nhãn nhóm thời gian (Hôm nay / Hôm qua / 7 ngày trước / Cũ hơn) */}
          <div className="px-3 py-1.5 text-[11px] font-semibold text-[#8E8E93] tracking-wide">
            {group.groupName}
          </div>

          {/* Danh sách các cuộc trò chuyện */}
          <div className="space-y-0.5">
            {group.sessions.map((session) => {
              const isActive = activeSessionId === session.id;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelectSession(session.id)}
                  title={session.title}
                  className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-colors group relative ${
                    isActive
                      ? 'bg-[#ECECF1] text-[#1F1F1F] font-semibold shadow-2xs'
                      : 'text-[#4B5563] hover:bg-[#EBECEF]/80 hover:text-[#1F1F1F]'
                  }`}
                >
                  <MessageSquare
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isActive ? 'text-[#1F1F1F]' : 'text-[#9CA3AF] group-hover:text-[#6B6B6B]'
                    }`}
                  />
                  <span className="truncate flex-1">
                    {session.title || 'Cuộc trò chuyện mới'}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
