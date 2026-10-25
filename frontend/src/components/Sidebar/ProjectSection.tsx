import React from 'react';
import { Sparkles } from 'lucide-react';

interface ProjectSectionProps {
  onExploreProjects?: () => void;
}

export const ProjectSection: React.FC<ProjectSectionProps> = ({ onExploreProjects }) => {
  return (
    <div className="px-3 py-1 space-y-1.5">
      {/* Mục "Khám phá dự án" */}
      <button
        type="button"
        onClick={onExploreProjects}
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-[8px] text-xs md:text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800/60 transition-colors text-left cursor-pointer"
      >
        <Sparkles className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0] shrink-0" />
        <span className="truncate">Khám phá tính năng AI</span>
      </button>

      {/* Nhãn nhóm "Dự án" */}
      <div className="px-3 pt-0.5 pb-1">
        <span className="text-[11px] font-semibold text-[#3F51B5] dark:text-[#7986CB] uppercase tracking-wider block">
          Tính năng chuyên môn
        </span>
        <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5 leading-snug">
          Tra cứu quy chế · Bảng điểm · Xét tốt nghiệp
        </p>
      </div>
    </div>
  );
};
