import type { FC } from 'react';
import { BookOpen, CheckCircle, AlertTriangle, Crosshair } from 'lucide-react';
import type { ProcessSummary } from '../types';

interface ResultSummaryProps {
  summary: ProcessSummary;
}

export const ResultSummary: FC<ResultSummaryProps> = ({ summary }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Tổng số môn */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
          <BookOpen className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Tổng số môn</p>
          <p className="text-2xl font-bold text-slate-800">{summary.total_subjects}</p>
        </div>
      </div>

      {/* Môn Đạt */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
          <CheckCircle className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Số môn đạt</p>
          <p className="text-2xl font-bold text-emerald-600">{summary.passed_count}</p>
        </div>
      </div>

      {/* Môn Không Đạt */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Môn không đạt</p>
          <p className="text-2xl font-bold text-rose-600">{summary.failed_count}</p>
        </div>
      </div>

      {/* Vùng màu đỏ phát hiện */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
          <Crosshair className="w-6 h-6" />
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Dấu đỏ OpenCV</p>
          <p className="text-2xl font-bold text-amber-600">{summary.red_regions_count} vùng</p>
        </div>
      </div>
    </div>
  );
};
