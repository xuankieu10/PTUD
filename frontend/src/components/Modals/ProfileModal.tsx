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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-2xs animate-fade-in">
      <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <GraduationCap className="w-5 h-5 text-[#F5B800]" />
            <h3 className="text-base font-bold text-[#1F1F1F]">
              Hồ sơ học vụ & Xét tốt nghiệp
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Card */}
        <div className="mt-4 p-4 bg-[#F7F7F8] rounded-2xl flex items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-[#1F1F1F] text-white flex items-center justify-center font-bold text-lg">
            {user?.full_name?.charAt(0) || 'U'}
          </div>
          <div>
            <h4 className="font-bold text-sm text-[#1F1F1F]">{user?.full_name}</h4>
            <p className="text-xs text-[#6B6B6B]">
              Mã SV: <span className="font-semibold">{user?.student_code || user?.username}</span>
            </p>
            <p className="text-xs text-[#6B6B6B]">
              Khoa: <span className="font-semibold">{user?.major || 'KCT'}</span> {user?.cohort ? `· Khóa: ${user.cohort}` : ''}
            </p>
          </div>
        </div>

        {isLoading && (
          <div className="py-8 flex flex-col items-center justify-center text-gray-500 gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-[#F5B800]" />
            <p className="text-xs">Đang kiểm tra dữ liệu học vụ...</p>
          </div>
        )}

        {error && !isLoading && (
          <div className="mt-4 p-3 bg-amber-50 text-amber-800 rounded-xl text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" />
            <span>{error}</span>
          </div>
        )}

        {data && !isLoading && (
          <div className="mt-4 space-y-3">
            {/* Status Badge */}
            <div
              className={`p-3 rounded-xl flex items-center gap-2.5 text-xs font-semibold ${
                data.eligible
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border border-amber-200'
              }`}
            >
              {data.eligible ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
              )}
              <span>{data.notes}</span>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-3 bg-gray-50 rounded-xl">
                <span className="text-gray-500 block text-[11px]">Tín chỉ tích lũy</span>
                <span className="text-base font-bold text-[#1F1F1F]">
                  {data.total_credits_passed} / {data.required_credits}
                </span>
              </div>
              <div className="p-3 bg-gray-50 rounded-xl">
                <span className="text-gray-500 block text-[11px]">Tín chỉ còn thiếu</span>
                <span className="text-base font-bold text-rose-600">
                  {data.credits_missing}
                </span>
              </div>
            </div>

            {/* Explanation from AI */}
            {data.explanation && (
              <div className="p-3.5 bg-gray-50 rounded-2xl border border-gray-100 text-xs text-[#4B5563] leading-relaxed">
                <span className="font-semibold text-[#1F1F1F] block mb-1">
                  Đánh giá từ cố vấn học tập AI:
                </span>
                <p className="whitespace-pre-line">{data.explanation}</p>
              </div>
            )}
          </div>
        )}

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
