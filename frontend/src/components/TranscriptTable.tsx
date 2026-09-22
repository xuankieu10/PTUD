import { useState } from 'react';
import type { FC } from 'react';
import { FileSpreadsheet, FileJson, AlertCircle, CheckCircle } from 'lucide-react';
import type { SubjectRecord } from '../types';

interface TranscriptTableProps {
  failedSubjects: SubjectRecord[];
  allSubjects: SubjectRecord[];
  sessionId: string;
}

export const TranscriptTable: FC<TranscriptTableProps> = ({
  failedSubjects,
  allSubjects,
  sessionId
}) => {
  const [activeTab, setActiveTab] = useState<'failed' | 'all'>('failed');

  const handleDownload = (format: 'csv' | 'json') => {
    if (!sessionId) return;
    const url = `/api/download/${format}?session_id=${encodeURIComponent(sessionId)}`;
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `ket_qua_mon_khong_dat_${sessionId.slice(0, 8)}.${format}`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const displayedList = activeTab === 'failed' ? failedSubjects : allSubjects;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header table & actions */}
      <div className="p-5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4">
        {/* Tab switcher */}
        <div className="flex bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab('failed')}
            className={`px-4 py-2 text-xs font-semibold rounded-lg transition ${
              activeTab === 'failed'
                ? 'bg-white text-rose-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Môn không đạt ({failedSubjects.length})
          </button>
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 text-xs font-semibold rounded-lg transition ${
              activeTab === 'all'
                ? 'bg-white text-indigo-600 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Tất cả các môn ({allSubjects.length})
          </button>
        </div>

        {/* Download buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleDownload('csv')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 text-xs font-medium transition"
          >
            <FileSpreadsheet className="w-4 h-4" />
            <span>Tải CSV (Excel)</span>
          </button>
          <button
            onClick={() => handleDownload('json')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-slate-50 text-slate-700 hover:bg-slate-100 text-xs font-medium transition"
          >
            <FileJson className="w-4 h-4" />
            <span>Tải JSON</span>
          </button>
        </div>
      </div>

      {/* Table content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
              <th className="py-3.5 px-4 w-16 text-center">STT</th>
              <th className="py-3.5 px-4">Tên môn học</th>
              <th className="py-3.5 px-4 w-28 text-center">Điểm số</th>
              <th className="py-3.5 px-4 w-36 text-center">Trạng thái</th>
              <th className="py-3.5 px-4">Lý do</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {displayedList.length > 0 ? (
              displayedList.map((item, idx) => {
                const subjectName = item.course_name || 'Chưa rõ tên môn';
                const gradeVal = item.grade ?? 0;
                const isFailed = item.is_failed ?? (item.status === 'failed' || gradeVal < 4.0);
                const reasonText = item.filter_reason || (isFailed ? 'Điểm < 4.0' : 'Đạt yêu cầu');

                return (
                  <tr
                    key={idx}
                    className={`hover:bg-slate-50/80 transition ${
                      isFailed ? 'bg-rose-50/20' : ''
                    }`}
                  >
                    <td className="py-3 px-4 text-center text-slate-400 font-mono text-xs">
                      {idx + 1}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-800">
                      {subjectName}
                    </td>
                    <td className="py-3 px-4 text-center font-bold font-mono">
                      <span
                        className={`inline-block px-2.5 py-0.5 rounded-md ${
                          gradeVal < 4.0
                            ? 'bg-rose-100 text-rose-700'
                            : 'bg-emerald-100 text-emerald-700'
                        }`}
                      >
                        {gradeVal.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {isFailed ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-600 border border-rose-200">
                          <AlertCircle className="w-3.5 h-3.5" />
                          Không đạt
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Đạt
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {isFailed ? (
                        <span className="font-medium text-rose-700">
                          {reasonText}
                        </span>
                      ) : (
                        <span className="text-slate-400">Đạt yêu cầu</span>
                      )}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-400 text-sm">
                  {activeTab === 'failed'
                    ? 'Tuyệt vời! Không có môn học nào bị đánh dấu không đạt.'
                    : 'Chưa có dữ liệu môn học nào.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
