import React from 'react';
import { Plus } from 'lucide-react';

interface NewChatButtonProps {
  onClick: () => void;
}

export const NewChatButton: React.FC<NewChatButtonProps> = ({ onClick }) => {
  return (
    <div className="px-3 py-2">
      <button
        type="button"
        onClick={onClick}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-[10px] bg-[#1565C0] hover:bg-[#0D47A1] active:scale-[0.99] text-white font-medium text-sm transition-all duration-200 shadow-xs cursor-pointer select-none"
        aria-label="Cuộc trò chuyện mới"
      >
        <Plus className="w-4 h-4 text-white shrink-0 stroke-[2.2]" />
        <span className="truncate font-semibold">Cuộc trò chuyện mới</span>
      </button>
    </div>
  );
};
