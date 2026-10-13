import React from 'react';
import { SquarePen } from 'lucide-react';

interface NewChatButtonProps {
  onClick: () => void;
}

export const NewChatButton: React.FC<NewChatButtonProps> = ({ onClick }) => {
  return (
    <div className="px-3 py-1.5">
      <button
        type="button"
        onClick={onClick}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-[#EFEFEF] hover:bg-[#E5E5E8] active:scale-[0.99] text-[#1F1F1F] font-normal text-xs md:text-sm transition-all duration-150"
        aria-label="Cuộc trò chuyện mới"
      >
        <SquarePen className="w-4 h-4 text-[#1F1F1F] shrink-0 stroke-[1.8]" />
        <span className="truncate">Cuộc trò chuyện mới</span>
      </button>
    </div>
  );
};
