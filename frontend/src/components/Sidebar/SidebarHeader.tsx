import React from 'react';
import { Search, PanelLeft, X } from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';

interface SidebarHeaderProps {
  onToggleSidebar: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  isSearchOpen: boolean;
  onToggleSearch: () => void;
}

export const SidebarHeader: React.FC<SidebarHeaderProps> = ({
  onToggleSidebar,
  searchQuery,
  onSearchChange,
  isSearchOpen,
  onToggleSearch,
}) => {
  return (
    <div className="p-3.5 pb-2">
      <div className="flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-2">
          <LhuLogo size="md" />
          <span className="text-base font-bold tracking-tight text-[#1F1F1F]">
            LHU AI
          </span>
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleSearch}
            title="Tìm kiếm cuộc trò chuyện"
            aria-label="Tìm kiếm cuộc trò chuyện"
            className={`p-1.5 rounded-lg transition-colors ${
              isSearchOpen
                ? 'bg-[#E5E7EB] text-[#1F1F1F]'
                : 'text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-[#EBECEF]'
            }`}
          >
            <Search className="w-4 h-4 stroke-[1.8]" />
          </button>

          {/* Panel toggle button matching screenshot */}
          <button
            type="button"
            onClick={onToggleSidebar}
            title="Thu gọn thanh bên"
            aria-label="Thu gọn thanh bên"
            className="p-1.5 rounded-lg text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-[#EBECEF] transition-colors"
          >
            <PanelLeft className="w-4 h-4 stroke-[1.8]" />
          </button>
        </div>
      </div>

      {/* Expandable search input */}
      {isSearchOpen && (
        <div className="mt-2.5 relative animate-fade-in">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Tìm kiếm cuộc trò chuyện..."
            autoFocus
            className="w-full text-xs bg-white border border-[#E5E5E5] rounded-xl px-3 py-1.5 pr-7 text-[#1F1F1F] placeholder-[#9CA3AF] focus:outline-none focus:border-[#F5B800] focus:ring-1 focus:ring-[#F5B800]"
          />
          {searchQuery ? (
            <button
              type="button"
              onClick={() => onSearchChange('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
};
