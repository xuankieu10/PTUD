import React from 'react';
import { PanelLeftOpen, SquarePen, AlertCircle } from 'lucide-react';
import type { OllamaHealth } from '../../types';

interface ChatHeaderProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onNewChat: () => void;
  health: OllamaHealth | null;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  onNewChat,
  health,
}) => {
  return (
    <header className="h-14 border-b border-[#F0F0F0] px-4 flex items-center justify-between shrink-0 bg-white/80 backdrop-blur-xs sticky top-0 z-30 select-none">
      <div className="flex items-center gap-3">
        {/* Toggle sidebar button when sidebar is closed or on mobile */}
        {(!isSidebarOpen || (typeof window !== 'undefined' && window.innerWidth < 768)) && (
          <button
            type="button"
            onClick={onToggleSidebar}
            title="Mở thanh bên"
            aria-label="Mở thanh bên"
            className="p-2 rounded-lg text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-[#F3F4F6] transition-colors"
          >
            <PanelLeftOpen className="w-5 h-5" />
          </button>
        )}

        {/* Chữ "LHU AI" ở góc trên trái, cỡ vừa, đậm */}
        <h1 className="text-base font-bold text-[#1F1F1F] tracking-tight">
          LHU AI
        </h1>
      </div>

      <div className="flex items-center gap-2">
        {/* Ollama Offline Warning Badge */}
        {health && !health.ollama.online && (
          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-50 text-rose-600 text-xs font-medium border border-rose-200"
            title={`Ollama không phản hồi tại ${health.ollama.host}`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Ollama Offline</span>
          </div>
        )}

        {/* Nút chat mới nhanh trên header */}
        <button
          type="button"
          onClick={onNewChat}
          title="Cuộc trò chuyện mới"
          aria-label="Cuộc trò chuyện mới"
          className="p-2 rounded-lg text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-[#F3F4F6] transition-colors"
        >
          <SquarePen className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
