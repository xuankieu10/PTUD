import React from 'react';
import { LayoutGrid, FolderPlus } from 'lucide-react';

interface ProjectSectionProps {
  onExploreProjects?: () => void;
}

export const ProjectSection: React.FC<ProjectSectionProps> = ({ onExploreProjects }) => {
  return (
    <div className="px-3 py-2 space-y-2 border-b border-[#EAEAEB] pb-3">
      {/* Mục "Khám phá dự án" với icon danh sách */}
      <button
        type="button"
        onClick={onExploreProjects}
        className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-[#1F1F1F] hover:bg-[#EBECEF] transition-colors"
      >
        <LayoutGrid className="w-4 h-4 text-[#6B6B6B]" />
        <span>Khám phá dự án</span>
      </button>

      {/* Nhãn nhóm "Dự án" */}
      <div className="pt-1">
        <div className="flex items-center justify-between px-3 mb-1">
          <span className="text-[11px] font-semibold text-[#6B6B6B] tracking-wide uppercase">
            Dự án
          </span>
          <button
            type="button"
            title="Tạo dự án mới"
            aria-label="Tạo dự án mới"
            onClick={onExploreProjects}
            className="text-[#9CA3AF] hover:text-[#1F1F1F] p-1 rounded-md transition-colors"
          >
            <FolderPlus className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Trạng thái rỗng */}
        <p className="px-3 py-1.5 text-xs text-[#8E8E93] leading-relaxed">
          Chưa có dự án cá nhân hoặc đã lưu.
        </p>
      </div>
    </div>
  );
};
