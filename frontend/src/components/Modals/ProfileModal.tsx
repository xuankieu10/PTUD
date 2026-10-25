import React, { useEffect, useState } from 'react';
import { X, GraduationCap, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import type { UserProfile } from '../../types';
import { getAuthToken } from '../../services/api';

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: UserProfile | null;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({
  isOpen,
  onClose,
  user,
}) => {
  const [data, setData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !user) return;
    const fetchGradCheck = async () => {
      setIsLoading(true);
      setError(null);
      const token = getAuthToken();
      const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || '';

      try {
        const res = await fetch(`${API_BASE_URL}/students/${user.id}/graduation-check?explain=true`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        if (res.ok) {
          const resData = await res.json();
          setData(resData);
        } else {
          setError('Chưa thể lấy thông tin xét tốt nghiệp của sinh viên này.');
        }
      } catch {
        setError('Không thể kết nối đến máy chủ.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchGradCheck();
  }, [isOpen, user]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-2xs animate-fade-in select-none">
      <div className="bg-white dark:bg-[#162338] rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-700 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <GraduationCap className="w-5 h-5 text-[#1565C0] dark:text-[#4D8FE0]" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Hồ sơ học vụ & Xét tốt nghiệp
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Info header */}
        {user && (
          <div className="my-4 p-3.5 bg-[#E3F0FC]/60 dark:bg-slate-800/80 rounded-2xl border border-blue-100 dark:border-slate-700 flex items-center justify-between">
            <div>
              <p className="font-bold text-sm text-[#1565C0] dark:text-[#4D8FE0]">
                {user.full_name || user.username}
              </p>
              <p className="text-xs text-slate-600 dark:text-slate-300">
                MSSV: {user.student_code || user.username} · Khoa: {user.major || 'Đại học Lạc Hồng'}
              </p>
            </div>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-[#1565C0] text-white">
              {user.role}
            </span>
          </div>
        )}

        {isLoading && (
          <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-[#1565C0] dark:text-[#4D8FE0]" />
            <span className="text-xs">Đang tải phân tích tốt nghiệp...</span>
          </div>
        )}

        {error && (
          <div className="p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs rounded-xl flex items-center gap-2 border border-rose-200 dark:border-rose-900/50">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        {data && (
          <div className="space-y-4 text-xs">
            {/* Status card */}
            <div
              className={`p-4 rounded-2xl border flex items-center gap-3 ${
                data.is_eligible
                  ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-200 text-emerald-800 dark:text-emerald-300'
                  : 'bg-amber-50 dark:bg-amber-950/30 border-amber-200 text-amber-800 dark:text-amber-300'
              }`}
            >
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <div>
                <p className="font-bold text-sm">
                  {data.is_eligible ? 'ĐỦ ĐIỀU KIỆN TỐT NGHIỆP' : 'CHƯA ĐỦ ĐIỀU KIỆN TỐT NGHIỆP'}
                </p>
                <p className="text-[11px] mt-0.5">
                  Tín chỉ tích lũy: {data.total_credits_earned || 0} / {data.total_credits_required || 140}
                </p>
              </div>
            </div>

            {/* Missing criteria */}
            {data.missing_criteria && data.missing_criteria.length > 0 && (
              <div>
                <h4 className="font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  Các điều kiện còn thiếu:
                </h4>
                <ul className="space-y-1 pl-4 list-disc text-rose-600 dark:text-rose-400">
                  {data.missing_criteria.map((c: string, i: number) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Explanation / Advice */}
            {data.explanation && (
              <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                {data.explanation}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
