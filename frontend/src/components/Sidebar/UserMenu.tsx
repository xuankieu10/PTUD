import React, { useState, useRef, useEffect } from 'react';
import { ChevronsUpDown, LogOut, Settings, GraduationCap, KeyRound } from 'lucide-react';
import type { UserProfile } from '../../types';

interface UserMenuProps {
  user: UserProfile | null;
  onLogout: () => void;
  onOpenLoginModal: () => void;
  onOpenProfileModal?: () => void;
}

export const UserMenu: React.FC<UserMenuProps> = ({
  user,
  onLogout,
  onOpenLoginModal,
  onOpenProfileModal,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fullName = user?.full_name || 'Kiều Ngô Xuân';
  const studentCode = user?.student_code || user?.username || '123000969';
  const major = user?.major || 'KCT';
  const initial = fullName.trim().charAt(fullName.trim().lastIndexOf(' ') + 1 || 0).toUpperCase() || 'X';

  return (
    <div ref={menuRef} className="relative p-2.5 bg-[#F7F7F8]">
      {/* Dropdown Menu Popup */}
      {isOpen && (
        <div className="absolute bottom-full left-2.5 right-2.5 mb-2 bg-white rounded-2xl shadow-xl border border-[#E5E5E5] p-1.5 z-50 animate-fade-in text-xs text-[#1F1F1F]">
          <div className="px-3 py-2 border-b border-gray-100 mb-1">
            <p className="font-semibold text-sm truncate">{fullName}</p>
            <p className="text-[#6B6B6B] text-[11px] truncate">
              Mã: {studentCode} · Khoa: {major}
            </p>
          </div>

          {onOpenProfileModal && (
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onOpenProfileModal();
              }}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#F3F4F6] text-[#4B5563] hover:text-[#1F1F1F] transition-colors"
            >
              <GraduationCap className="w-4 h-4 text-[#6B6B6B]" />
              <span>Hồ sơ học vụ & Tốt nghiệp</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onOpenLoginModal();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#F3F4F6] text-[#4B5563] hover:text-[#1F1F1F] transition-colors"
          >
            <KeyRound className="w-4 h-4 text-[#6B6B6B]" />
            <span>Đổi tài khoản / Đăng nhập</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#F3F4F6] text-[#4B5563] hover:text-[#1F1F1F] transition-colors"
          >
            <Settings className="w-4 h-4 text-[#6B6B6B]" />
            <span>Cài đặt</span>
          </button>

          <div className="h-px bg-gray-100 my-1" />

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onLogout();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-rose-50 text-rose-600 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Đăng xuất</span>
          </button>
        </div>
      )}

      {/* Footer trigger button exactly matching screenshot */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-2.5 p-1.5 rounded-xl hover:bg-[#ECECF1] transition-colors group text-left"
        aria-label="Menu tài khoản người dùng"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          {/* Avatar tròn chứa chữ cái đầu với nền xám nhạt như trong ảnh */}
          <div className="w-8 h-8 rounded-full bg-[#EBECEF] text-[#1F1F1F] flex items-center justify-center font-medium text-xs shrink-0 border border-black/5">
            {initial}
          </div>

          {/* Tên • mã và khoa */}
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium text-[#1F1F1F] truncate leading-tight">
              {fullName} • {studentCode.length > 5 ? `${studentCode.slice(0, 4)}...` : studentCode}
            </p>
            <p className="text-[11px] text-[#6B6B6B] truncate leading-normal">
              {major}
            </p>
          </div>
        </div>

        {/* Icon mũi tên lên-xuống */}
        <ChevronsUpDown className="w-3.5 h-3.5 text-[#9CA3AF] group-hover:text-[#4B5563] shrink-0" />
      </button>
    </div>
  );
};
