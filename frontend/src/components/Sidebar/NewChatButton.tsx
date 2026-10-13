import React from 'react';
import { SquarePen } from 'lucide-react';

interface NewChatButtonProps {
  onClick: () => void;
}

export const NewChatButton: React.FC<NewChatButtonProps> = ({ onClick }) => {
  return (
    <div className="px-3 py-2">
      <button
        type="button"
        onClick={onClick}
        className="w-full flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-2xl bg-[#ECECF1] hover:bg-[#E2E2E8] active:scale-[0.99] text-[#1F1F1F] font-medium text-sm transition-all duration-150 shadow-xs"
        aria-label="Tạo cuộc trò chuyện mới"
      >
        <span className="truncate">Cuộc trò chuyện mới</span>
        <SquarePen className="w-4 h-4 text-[#4B5563] shrink-0" />
      </button>
    </div>
  );
};
