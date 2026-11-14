import React, { useState } from 'react';
import { PanelLeftOpen, Menu, SquarePen, AlertCircle, Share2, Sun, Moon, Check, Sparkles, Home } from 'lucide-react';
import type { OllamaHealth } from '../../types';

interface ChatHeaderProps {
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  onNewChat: () => void;
  health: OllamaHealth | null;
  isDarkMode?: boolean;
  onToggleDarkMode?: () => void;
  onNavigateToHome?: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  isSidebarOpen,
  onToggleSidebar,
  onNewChat,
  health,
  isDarkMode = false,
  onToggleDarkMode,
  onNavigateToHome,
}) => {
  const [copiedShare, setCopiedShare] = useState(false);

  const handleShare = () => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href);
      setCopiedShare(true);
      setTimeout(() => setCopiedShare(false), 2000);
    }
  };

  return (
    <header className="h-14 bg-[#1565C0] dark:bg-[#0D3875] text-white px-3 sm:px-4 flex items-center justify-between shrink-0 sticky top-0 z-30 select-none shadow-sm transition-colors duration-200">
      {/* Left: Mobile hamburger or desktop toggle + Chatbot name */}
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <button
          type="button"
          onClick={onToggleSidebar}
          title={isSidebarOpen ? "Thu gọn thanh bên" : "Mở thanh bên"}
          aria-label="Mở thanh bên"
          className="p-1.5 sm:p-2 rounded-lg text-white/90 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors cursor-pointer"
        >
          {/* On mobile show Hamburger Menu icon, on desktop show PanelLeftOpen if sidebar is closed */}
          <span className="md:hidden">
            <Menu className="w-5 h-5 stroke-[2]" />
          </span>
          <span className="hidden md:inline">
            <PanelLeftOpen className="w-5 h-5 stroke-[2]" />
          </span>
        </button>

        {/* Tên chatbot ở giữa / trái chữ trắng */}
        <div className="flex items-center gap-2 truncate">
          <h1 className="text-sm sm:text-base font-bold text-white tracking-tight truncate flex items-center gap-1.5">
            <span>Trợ lý AI</span>
            <span className="text-white/60 font-normal hidden sm:inline">·</span>
            <span className="text-white/90 font-medium text-xs sm:text-sm hidden sm:inline">Khoa CNTT LHU</span>
          </h1>
        </div>
      </div>

      {/* Center/Right: Model selector, Share, Dark/Light mode toggle, New chat */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Model badge/selector */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/10 hover:bg-white/15 text-white/90 text-xs border border-white/15 transition">
          <Sparkles className="w-3 h-3 text-amber-300" />
          <span className="font-medium">
            {health?.chat_model 
              ? (health.chat_model.toLowerCase().includes('ollama') ? health.chat_model : `Ollama ${health.chat_model}`)
              : health?.ollama?.chat_model 
                ? (health.ollama.chat_model.toLowerCase().includes('ollama') ? health.ollama.chat_model : `Ollama ${health.ollama.chat_model}`)
                : 'Không rõ model'}
          </span>
        </div>

        {/* Ollama Offline Warning Badge */}
        {health && !health.ollama.online && (
          <div
            className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/90 text-white text-[11px] font-medium"
            title={`Ollama không phản hồi tại ${health.ollama.host}`}
          >
            <AlertCircle className="w-3 h-3" />
            <span className="hidden sm:inline">Offline</span>
          </div>
        )}

        {/* Nút về Trang chủ */}
        {onNavigateToHome && (
          <button
            type="button"
            onClick={onNavigateToHome}
            title="Quay lại Trang chủ"
            aria-label="Quay lại Trang chủ"
            className="p-1.5 sm:p-2 rounded-lg text-white/85 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors cursor-pointer"
          >
            <Home className="w-4 h-4 stroke-[1.8]" />
          </button>
        )}

        {/* Nút chia sẻ */}
        <button
          type="button"
          onClick={handleShare}
          title={copiedShare ? "Đã sao chép liên kết!" : "Chia sẻ cuộc trò chuyện"}
          aria-label="Chia sẻ cuộc trò chuyện"
          className="p-1.5 sm:p-2 rounded-lg text-white/85 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors cursor-pointer relative"
        >
          {copiedShare ? (
            <Check className="w-4 h-4 text-emerald-300" />
          ) : (
            <Share2 className="w-4 h-4 stroke-[1.8]" />
          )}
        </button>

        {/* Nút bật tắt sáng / tối */}
        {onToggleDarkMode && (
          <button
            type="button"
            onClick={onToggleDarkMode}
            title={isDarkMode ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối"}
            aria-label="Bật tắt giao diện sáng tối"
            className="p-1.5 sm:p-2 rounded-lg text-white/85 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors cursor-pointer"
          >
            {isDarkMode ? (
              <Sun className="w-4 h-4 text-amber-300 stroke-[2]" />
            ) : (
              <Moon className="w-4 h-4 text-white stroke-[2]" />
            )}
          </button>
        )}

        {/* Nút chat mới nhanh trên header */}
        <button
          type="button"
          onClick={onNewChat}
          title="Cuộc trò chuyện mới"
          aria-label="Cuộc trò chuyện mới"
          className="p-1.5 sm:p-2 rounded-lg text-white/85 hover:text-white hover:bg-white/15 active:bg-white/20 transition-colors cursor-pointer"
        >
          <SquarePen className="w-4 h-4 stroke-[2]" />
        </button>
      </div>
    </header>
  );
};
