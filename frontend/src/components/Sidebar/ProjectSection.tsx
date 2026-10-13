import React from 'react';
import { AlignLeft } from 'lucide-react';

interface ProjectSectionProps {
  onExploreProjects?: () => void;
}

export const ProjectSection: React.FC<ProjectSectionProps> = ({ onExploreProjects }) => {
  return (
    <div className="px-3 py-1 space-y-2">
      {/* Mục "Khám phá dự án" với icon danh sách */}
      <button
        type="button"
        onClick={onExploreProjects}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs md:text-sm text-[#1F1F1F] hover:bg-[#EBECEF] transition-colors text-left"
      >
        <AlignLeft className="w-4 h-4 text-[#1F1F1F] stroke-[1.8]" />
        <span>Khám phá dự án</span>
      </button>

      {/* Nhãn nhóm "Dự án" */}
      <div className="px-3 pt-1">
        <span className="text-[11px] font-semibold text-[#6B6B6B] block">
          Dự án
        </span>
        <p className="text-[11px] text-[#8E8E93] mt-1.5 leading-snug">
          Chưa có dự án cá nhân hoặc đã lưu.
        </p>
      </div>
    </div>
  );
};
