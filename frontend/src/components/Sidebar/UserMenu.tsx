import React, { useState, useRef, useEffect } from 'react';
import { ChevronsUpDown, LogOut, Settings, GraduationCap, KeyRound, User as UserIcon, LogIn } from 'lucide-react';
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

  // Guest Mode (Chưa đăng nhập)
  if (!user) {
    return (
      <div className="p-3 bg-white dark:bg-[#162338] border-t border-slate-200/80 dark:border-slate-800">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-full bg-[#E3F0FC] dark:bg-slate-700 text-[#1565C0] dark:text-[#4D8FE0] flex items-center justify-center font-medium text-xs shrink-0 border border-blue-200 dark:border-slate-600">
              <UserIcon className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 leading-tight">
                Khách
              </p>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-normal">
                Chưa đăng nhập
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenLoginModal}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] bg-[#1565C0] hover:bg-[#0D47A1] text-white text-xs font-medium transition shadow-xs cursor-pointer"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Đăng nhập</span>
          </button>
        </div>
      </div>
    );
  }

  // Logged-in User
  const fullName = user.full_name || user.username;
  const studentCode = user.student_code || user.username;
  const major = user.major || 'Đại học Lạc Hồng';
  const initial = fullName.trim().charAt(fullName.trim().lastIndexOf(' ') + 1 || 0).toUpperCase() || 'U';

  return (
    <div ref={menuRef} className="relative p-2.5 bg-white dark:bg-[#162338] border-t border-slate-200/80 dark:border-slate-800">
      {/* Dropdown Menu Popup */}
      {isOpen && (
        <div className="absolute bottom-full left-2.5 right-2.5 mb-2 bg-white dark:bg-[#162338] rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700 p-1.5 z-50 animate-fade-in text-xs text-slate-800 dark:text-slate-100">
          <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-700 mb-1">
            <p className="font-semibold text-sm truncate text-[#1565C0] dark:text-[#4D8FE0]">{fullName}</p>
            <p className="text-slate-500 dark:text-slate-400 text-[11px] truncate">
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
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#E3F0FC] dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
            >
              <GraduationCap className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />
              <span>Hồ sơ học vụ & Tốt nghiệp</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onOpenLoginModal();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#E3F0FC] dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
          >
            <KeyRound className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />
            <span>Đổi tài khoản</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              if (onOpenProfileModal) onOpenProfileModal();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-[#E3F0FC] dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
          >
            <Settings className="w-4 h-4 text-slate-500" />
            <span>Cài đặt</span>
          </button>

          <div className="h-px bg-slate-100 dark:bg-slate-700 my-1" />

          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onLogout();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-xl hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            <span>Đăng xuất</span>
          </button>
        </div>
      )}

      {/* Footer trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between gap-2.5 p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors group text-left cursor-pointer"
        aria-label="Menu tài khoản người dùng"
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-[#1565C0] text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
            {initial}
          </div>

          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate leading-tight">
              {fullName}
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate leading-normal">
              {studentCode} · {major}
            </p>
          </div>
        </div>

        <ChevronsUpDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200 shrink-0" />
      </button>
    </div>
  );
};
