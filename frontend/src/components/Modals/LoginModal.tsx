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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-2xs animate-fade-in">
      <div className="bg-white rounded-3xl max-w-sm w-full p-6 shadow-2xl border border-gray-100">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <h3 className="text-base font-bold text-[#1F1F1F]">
            Đăng nhập tài khoản LHU AI
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-3 p-3 bg-rose-50 text-rose-700 text-xs rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="block text-xs font-semibold text-[#4B5563] mb-1">
              Tên tài khoản / Mã sinh viên
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Nhập tên tài khoản..."
                className="w-full text-xs bg-[#F9FAFB] border border-gray-200 rounded-xl pl-9 pr-3 py-2.5 text-[#1F1F1F] focus:outline-none focus:border-[#F5B800] focus:ring-1 focus:ring-[#F5B800]"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#4B5563] mb-1">
              Mật khẩu
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Nhập mật khẩu..."
                className="w-full text-xs bg-[#F9FAFB] border border-gray-200 rounded-xl pl-9 pr-3 py-2.5 text-[#1F1F1F] focus:outline-none focus:border-[#F5B800] focus:ring-1 focus:ring-[#F5B800]"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full mt-2 py-2.5 rounded-xl bg-[#1F1F1F] hover:bg-black text-white text-xs font-semibold flex items-center justify-center gap-2 transition"
          >
            {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            <span>{isLoading ? 'Đang xác thực...' : 'Đăng nhập'}</span>
          </button>
        </form>

        {/* Tài khoản mẫu */}
        <div className="mt-4 pt-3 border-t border-gray-100">
          <p className="text-[11px] text-gray-400 mb-2">Chọn nhanh tài khoản kiểm thử:</p>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => handleQuickLogin('test01', 'Test@123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
            >
              Sinh viên test01
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('sv01', '123')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
            >
              Sinh viên sv01
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('admin', 'change_me')}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium"
            >
              Quản trị admin
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
