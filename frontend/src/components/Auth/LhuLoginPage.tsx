import React, { useState } from 'react';
import { User, Lock, ShieldCheck, AlertCircle, Loader2, Sun, Moon } from 'lucide-react';
import { authApi } from '../../services/api';
import type { UserProfile } from '../../types';

interface LhuLoginPageProps {
  onLoginSuccess: (user: UserProfile) => void;
  isDarkMode?: boolean;
  onToggleDarkMode?: () => void;
}

export const LhuLoginPage: React.FC<LhuLoginPageProps> = ({
  onLoginSuccess,
  isDarkMode = false,
  onToggleDarkMode,
}) => {
  const [mode, setMode] = useState<'student' | 'admin'>('student');
  const [studentId, setStudentId] = useState('');
  const [password, setPassword] = useState('');

  const [adminUsername, setAdminUsername] = useState('test01');
  const [adminPassword, setAdminPassword] = useState('Test@123');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStudentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || !password) return;

    const pwd = password;
    // Xóa mật khẩu khỏi state ngay sau khi gửi theo yêu cầu an toàn
    setPassword('');
    setIsLoading(true);
    setError(null);

    try {
      await authApi.loginLhu(studentId, pwd);
      const user = await authApi.getMe();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err?.message || 'Đăng nhập Cổng trường LHU thất bại.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdminSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminUsername || !adminPassword) return;

    const pwd = adminPassword;
    // Xóa mật khẩu khỏi state ngay sau khi gửi
    setAdminPassword('');
    setIsLoading(true);
    setError(null);

    try {
      await authApi.login(adminUsername, pwd);
      const user = await authApi.getMe();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err?.message || 'Đăng nhập tài khoản quản trị thất bại.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickAdminLogin = async (usr: string, pwd: string) => {
    setAdminUsername(usr);
    setAdminPassword('');
    setIsLoading(true);
    setError(null);
    try {
      await authApi.login(usr, pwd);
      const user = await authApi.getMe();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err?.message || 'Đăng nhập thất bại.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-screen flex flex-col justify-between bg-slate-50 dark:bg-[#0F1B2D] text-slate-800 dark:text-slate-100 transition-colors duration-200">
      {/* Top Navbar Header */}
      <header className="h-16 px-6 flex items-center justify-between border-b border-slate-200/80 dark:border-slate-800 bg-white/70 dark:bg-[#162338]/70 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <img
            src="/fit-logo-transparent.png"
            alt="Khoa Công nghệ Thông tin"
            className="h-10 w-auto object-contain select-none"
          />
          <div>
            <h1 className="text-sm font-bold text-[#1565C0] dark:text-[#4D8FE0] tracking-tight">
              Đại học Lạc Hồng · Khoa CNTT
            </h1>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Trợ lý AI Cố vấn Học vụ Sinh viên
            </p>
          </div>
        </div>

        {onToggleDarkMode && (
          <button
            type="button"
            onClick={onToggleDarkMode}
            title={isDarkMode ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
            className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition cursor-pointer"
          >
            {isDarkMode ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
          </button>
        )}
      </header>

      {/* Main Login Card Center */}
      <main className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white dark:bg-[#162338] rounded-3xl p-7 shadow-xl border border-slate-200/90 dark:border-slate-700/80">
          {mode === 'student' ? (
            <>
              <div className="text-center mb-5">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                  Đăng nhập tài khoản Sinh viên
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Nhập mã số sinh viên và mật khẩu Cổng trường{' '}
                  <span className="font-semibold text-[#1565C0] dark:text-[#4D8FE0]">me.lhu.edu.vn</span>
                </p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="mb-4 p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs rounded-xl flex items-start gap-2.5 border border-rose-200 dark:border-rose-900/50 animate-fade-in"
                >
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleStudentSubmit} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Mã số sinh viên (MSSV)
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={studentId}
                      onChange={(e) => setStudentId(e.target.value)}
                      placeholder="Ví dụ: 121000123"
                      aria-label="Mã số sinh viên"
                      className="w-full text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition"
                      required
                      autoFocus
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Mật khẩu cổng trường (me.lhu.edu.vn)
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Nhập mật khẩu cổng sinh viên..."
                      aria-label="Mật khẩu cổng trường"
                      className="w-full text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition"
                      required
                    />
                  </div>
                </div>

                {/* Dòng cam kết an toàn bảo mật */}
                <div className="p-3 bg-blue-50/80 dark:bg-blue-950/40 rounded-xl border border-blue-200/70 dark:border-blue-900/40 flex items-start gap-2.5 text-xs text-blue-950 dark:text-blue-200">
                  <ShieldCheck className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0] shrink-0 mt-0.5" />
                  <div className="leading-relaxed text-[11px]">
                    <span className="font-bold text-[#1565C0] dark:text-[#4D8FE0]">Cam kết bảo mật:</span> Mật khẩu chỉ dùng một lần để xác thực, tuyệt đối không lưu trữ. Token chỉ lưu trong RAM 30 phút.
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 py-2.5 rounded-xl bg-[#1565C0] hover:bg-[#0D47A1] text-white text-xs font-semibold flex items-center justify-center gap-2 transition shadow-xs cursor-pointer active:scale-[0.99] disabled:opacity-60"
                >
                  {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{isLoading ? 'Đang xác thực với Cổng trường...' : 'Đăng nhập'}</span>
                </button>
              </form>

              {/* Link nhỏ cho luồng quản trị cũ */}
              <div className="mt-5 pt-3 border-t border-slate-100 dark:border-slate-800 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode('admin');
                    setError(null);
                  }}
                  className="text-[11px] text-slate-500 hover:text-[#1565C0] dark:text-slate-400 dark:hover:text-[#4D8FE0] hover:underline cursor-pointer"
                >
                  Đăng nhập quản trị
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="text-center mb-5">
                <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">
                  Đăng nhập Quản trị viên
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                  Dành cho ban quản trị và tài khoản kiểm thử hệ thống
                </p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="mb-4 p-3 bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs rounded-xl flex items-start gap-2.5 border border-rose-200 dark:border-rose-900/50 animate-fade-in"
                >
                  <AlertCircle className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleAdminSubmit} className="space-y-3.5">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                    Tên tài khoản
                  </label>
                  <div className="relative">
                    <User className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={adminUsername}
                      onChange={(e) => setAdminUsername(e.target.value)}
                      placeholder="Nhập tên tài khoản..."
                      aria-label="Tên tài khoản quản trị"
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
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                      placeholder="Nhập mật khẩu..."
                      aria-label="Mật khẩu quản trị"
                      className="w-full text-xs bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl pl-9 pr-3 py-2.5 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1565C0] dark:focus:border-[#4D8FE0] focus:ring-1 focus:ring-[#1565C0] dark:focus:ring-[#4D8FE0] transition"
                      required
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 py-2.5 rounded-xl bg-[#1565C0] hover:bg-[#0D47A1] text-white text-xs font-semibold flex items-center justify-center gap-2 transition shadow-xs cursor-pointer active:scale-[0.99] disabled:opacity-60"
                >
                  {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{isLoading ? 'Đang xác thực...' : 'Đăng nhập Quản trị'}</span>
                </button>
              </form>

              {/* Tài khoản mẫu */}
              <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800">
                <p className="text-[11px] text-slate-400 dark:text-slate-500 mb-2">Chọn nhanh tài khoản kiểm thử:</p>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleQuickAdminLogin('test01', 'Test@123')}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-[#E3F0FC] dark:bg-slate-800 hover:bg-blue-100 text-[#1565C0] dark:text-[#4D8FE0] font-medium transition cursor-pointer"
                  >
                    Sinh viên test01
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickAdminLogin('sv01', '123')}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-[#E3F0FC] dark:bg-slate-800 hover:bg-blue-100 text-[#1565C0] dark:text-[#4D8FE0] font-medium transition cursor-pointer"
                  >
                    Sinh viên sv01
                  </button>
                  <button
                    type="button"
                    onClick={() => handleQuickAdminLogin('admin', 'change_me')}
                    className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 text-slate-700 dark:text-slate-300 font-medium transition cursor-pointer"
                  >
                    Quản trị admin
                  </button>
                </div>
              </div>

              {/* Quay lại đăng nhập sinh viên */}
              <div className="mt-4 pt-2 text-center">
                <button
                  type="button"
                  onClick={() => {
                    setMode('student');
                    setError(null);
                  }}
                  className="text-[11px] text-[#1565C0] dark:text-[#4D8FE0] font-semibold hover:underline cursor-pointer"
                >
                  ← Quay lại Đăng nhập Sinh viên LHU
                </button>
              </div>
            </>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 text-center text-xs text-slate-400 dark:text-slate-500 border-t border-slate-200/60 dark:border-slate-800/60">
        © 2026 Khoa Công nghệ Thông tin · Trường Đại học Lạc Hồng (LHU)
      </footer>
    </div>
  );
};
