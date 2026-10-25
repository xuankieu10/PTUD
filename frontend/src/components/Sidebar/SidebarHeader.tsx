import React from 'react';
import { Search, PanelLeft, X } from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';

interface SidebarHeaderProps {
  onToggleSidebar: () => void;
  searchQuery: string;
  onSearchChange: (query: string) => void;
  isSearchOpen?: boolean;
  onToggleSearch?: () => void;
}

export const SidebarHeader: React.FC<SidebarHeaderProps> = ({
  onToggleSidebar,
  searchQuery,
  onSearchChange,
}) => {
  return (
    <div className="p-3.5 pb-2 border-b border-slate-200/80 dark:border-slate-800">
      {/* Top row: Logo Khoa CNTT + collapse sidebar button */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <LhuLogo variant="full" size="sm" className="h-8 max-w-[170px]" />
        </div>

        {/* Nút thu gọn thanh bên */}
        <button
          type="button"
          onClick={onToggleSidebar}
          title="Thu gọn thanh bên"
          aria-label="Thu gọn thanh bên"
          className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white hover:bg-slate-200/70 dark:hover:bg-slate-800 transition-colors cursor-pointer shrink-0"
        >
          <PanelLeft className="w-4 h-4 stroke-[2]" />
        </button>
      </div>

      {/* Ô tìm kiếm cuộc trò chuyện dạng viên thuốc (pill) */}
      <div className="mt-3 relative">
        <Search className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Tìm kiếm..."
          className="w-full text-xs bg-white dark:bg-[#162338] border border-slate-200 dark:border-slate-700 rounded-full pl-8 pr-7 py-2 text-slate-800 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition-all shadow-2xs"
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            title="Xóa tìm kiếm"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : null}
      </div>
    </div>
  );
};
