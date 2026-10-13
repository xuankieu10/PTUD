import React from 'react';
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
  // Fallback demo items if database has no sessions yet so it looks exactly like the screenshot
  const displaySessions: ChatSession[] =
    sessions.length > 0
      ? sessions
      : [
          { id: 101, title: 'Phòng Khoa Công Nghệ Thông Tin', created_at: '2026-10-01' },
          { id: 102, title: 'Giáo viên Bộ Môn CNTT', created_at: '2026-10-01' },
          { id: 103, title: 'Hiệu trưởng trường mình tên', created_at: '2026-10-01' },
          { id: 104, title: 'đề thi của trường môn lập trình', created_at: '2026-10-01' },
          { id: 105, title: 'G405 trường lạc hồng ở cơ sở', created_at: '2026-10-01' },
          { id: 106, title: 'Xác nhận môn học ở đâu', created_at: '2026-10-01' },
        ];

  const filteredSessions = searchQuery.trim()
    ? displaySessions.filter((s) =>
        s.title.toLowerCase().includes(searchQuery.toLowerCase().trim())
      )
    : displaySessions;

  const grouped = groupSessionsByDate(filteredSessions);

  if (isLoading && sessions.length === 0) {
    return (
      <div className="flex-1 p-4 space-y-2.5 animate-pulse">
        <div className="h-3 w-14 bg-gray-200 rounded"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
        <div className="h-7 bg-gray-200/70 rounded-xl"></div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2 space-y-3.5 select-none">
      {grouped.map((group) => (
        <div key={group.groupName} className="space-y-0.5">
          {/* Nhãn nhóm thời gian: Cũ hơn / Hôm nay / Hôm qua / 7 ngày trước */}
          <div className="px-3 py-1 text-[11px] font-semibold text-[#6B6B6B]">
            {group.groupName}
          </div>

          {/* Danh sách các cuộc trò chuyện - text thuần không icon như ảnh mẫu */}
          <div className="space-y-0.5">
            {group.sessions.map((session) => {
              const isActive = activeSessionId === session.id;
              return (
                <button
                  key={session.id}
                  type="button"
                  onClick={() => onSelectSession(session.id)}
                  title={session.title}
                  className={`w-full text-left block px-3 py-1.5 rounded-xl text-xs md:text-[13px] transition-colors truncate ${
                    isActive
                      ? 'bg-[#ECECF1] text-[#1F1F1F] font-medium'
                      : 'text-[#2D2D2D] hover:bg-[#EBECEF] hover:text-[#1F1F1F]'
                  }`}
                >
                  {session.title || 'Cuộc trò chuyện mới'}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};
