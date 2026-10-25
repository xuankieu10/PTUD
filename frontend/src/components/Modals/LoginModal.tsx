import React, { useState } from 'react';
import { X, Lock, User, AlertCircle, Loader2 } from 'lucide-react';
import { authApi } from '../../services/api';
import type { UserProfile } from '../../types';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: UserProfile) => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLoginSuccess,
}) => {
  const [username, setUsername] = useState('test01');
  const [password, setPassword] = useState('Test@123');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;

    setIsLoading(true);
    setError(null);

    try {
      await authApi.login(username, password);
      const user = await authApi.getMe();
      onLoginSuccess(user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickLogin = async (usr: string, pwd: string) => {
    setUsername(usr);
    setPassword(pwd);
    setIsLoading(true);
    setError(null);
    try {
      await authApi.login(usr, pwd);
      const user = await authApi.getMe();
      onLoginSuccess(user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Đăng nhập thất bại.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-2xs animate-fade-in select-none">
      <div className="bg-white dark:bg-[#162338] rounded-3xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-700">
        {/* Header with Close Button */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
            Đăng nhập tài khoản LHU AI
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Logo Khoa Công nghệ Thông tin trên trang đăng nhập */}
        <div className="flex flex-col items-center justify-center my-4">
          <div className="p-2.5 rounded-xl bg-white dark:bg-white/10 shadow-xs border border-slate-200/80 dark:border-white/10">
            <img
              src="/fit-logo-transparent.png"
              alt="Khoa Công nghệ Thông tin"
              className="h-14 w-auto object-contain select-none"
            />
          </div>
          <p className="text-xs font-semibold text-[#1565C0] dark:text-[#4D8FE0] mt-2">
            Đại học Lạc Hồng · Khoa CNTT
          </p>
        </div>

        {error && (
          <div className="mt-2 p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs rounded-xl flex items-center gap-2 border border-rose-200 dark:border-rose-900/50">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-3 space-y-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Tên tài khoản / Mã sinh viên
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Nhập tên tài khoản..."
                className="w-full text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu..."
                className="w-full text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 py-2.5 rounded-xl bg-[#1565C0] hover:bg-[#0D47A1] text-white text-xs font-semibold flex items-center justify-center gap-2 transition shadow-xs cursor-pointer active:scale-[0.99]"
          >
            {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{isLoading ? 'Đang xác thực...' : 'Đăng nhập'}</span>
          </button>
        </form>

        {/* Tài khoản mẫu */}
        <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800">
          <p className="text-[11px] text-slate-400 dark:text-slate-500 mb-2">Chọn nhanh tài khoản kiểm thử:</p>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => handleQuickLogin('test01', 'Test@123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-[#E3F0FC] dark:bg-slate-800 hover:bg-blue-100 text-[#1565C0] dark:text-[#4D8FE0] font-medium transition cursor-pointer"
            >
              Sinh viên test01
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('sv01', '123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-[#E3F0FC] dark:bg-slate-800 hover:bg-blue-100 text-[#1565C0] dark:text-[#4D8FE0] font-medium transition cursor-pointer"
            >
              Sinh viên sv01
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('admin', 'change_me')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-medium transition cursor-pointer"
            >
              Quản trị admin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
