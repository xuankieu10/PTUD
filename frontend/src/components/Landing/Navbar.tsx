import React, { useState } from 'react';
import { LhuLogo } from '../Common/LhuLogo';
import { 
  Sparkles, 
  Sun, 
  Moon, 
  Menu, 
  X, 
  ArrowRight, 
  LogIn, 
  UserPlus, 
  MessageSquare
} from 'lucide-react';

interface NavbarProps {
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  onNavigateToSignUp: () => void;
  onOpenLoginModal: () => void;
  onNavigateToChat: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isDarkMode,
  onToggleDarkMode,
  onNavigateToSignUp,
  onOpenLoginModal,
  onNavigateToChat,
}) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const scrollToSection = (id: string) => {
    setIsMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full backdrop-blur-md bg-white/85 dark:bg-[#0F1B2D]/85 border-b border-slate-200/80 dark:border-slate-800/80 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20">
          
          {/* Logo Brand */}
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <LhuLogo size="md" variant="avatar" className="shadow-xs" />
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="text-xl sm:text-2xl font-black tracking-tight text-[#1565C0] dark:text-[#4D8FE0]">
                  HocVu<span className="text-[#3F51B5] dark:text-[#7986CB]">AI</span>
                </span>
                <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
                  LHU
                </span>
              </div>
              <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 hidden sm:inline-block">
                Khoa Công nghệ Thông tin • ĐH Lạc Hồng
              </span>
            </div>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center gap-8 text-sm font-semibold text-slate-600 dark:text-slate-300">
            <button 
              onClick={() => scrollToSection('features')}
              className="hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
            >
              Tính năng
            </button>
            <button 
              onClick={() => scrollToSection('how-it-works')}
              className="hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
            >
              Cách hoạt động
            </button>
            <button 
              onClick={() => scrollToSection('stats')}
              className="hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
            >
              Chuẩn đầu ra
            </button>
            <button 
              onClick={() => scrollToSection('faq')}
              className="hover:text-[#1565C0] dark:hover:text-[#4D8FE0] transition-colors cursor-pointer"
            >
              Câu hỏi thường gặp
            </button>
          </nav>

          {/* Desktop Action Buttons */}
          <div className="hidden md:flex items-center gap-3">
            {/* Dark Mode Toggle */}
            <button
              onClick={onToggleDarkMode}
              className="p-2 rounded-xl text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              title={isDarkMode ? 'Chuyển sang chế độ sáng' : 'Chuyển sang chế độ tối'}
              aria-label="Toggle dark mode"
            >
              {isDarkMode ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5 text-slate-600" />}
            </button>

            {/* Login Button */}
            <button
              onClick={onOpenLoginModal}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-slate-700 dark:text-slate-200 hover:text-[#1565C0] dark:hover:text-[#4D8FE0] rounded-xl hover:bg-slate-100/70 dark:hover:bg-slate-800/70 transition-colors cursor-pointer"
            >
              <LogIn className="w-4 h-4" />
              Đăng nhập
            </button>

            {/* Sign Up Button */}
            <button
              onClick={onNavigateToSignUp}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-[#1565C0] dark:text-[#4D8FE0] bg-blue-50 dark:bg-blue-950/50 hover:bg-blue-100 dark:hover:bg-blue-900/60 border border-blue-200 dark:border-blue-800/80 rounded-xl transition-all cursor-pointer shadow-2xs"
            >
              <UserPlus className="w-4 h-4" />
              Đăng ký
            </button>

            {/* Launch Chatbot CTA */}
            <button
              onClick={onNavigateToChat}
              className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-bold text-white bg-gradient-to-r from-[#1565C0] to-[#3F51B5] hover:from-[#0D47A1] hover:to-[#303F9F] rounded-xl shadow-md shadow-blue-500/25 hover:shadow-lg hover:shadow-blue-500/35 transition-all transform hover:-translate-y-0.5 cursor-pointer"
            >
              <Sparkles className="w-4 h-4 animate-pulse" />
              Vào Chatbot
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>

          {/* Mobile Right Controls */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={onToggleDarkMode}
              className="p-2 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Toggle theme"
            >
              {isDarkMode ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
            </button>

            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2 rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Open menu"
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-[#0F1B2D]/95 backdrop-blur-md px-4 pt-3 pb-6 space-y-3 animate-in slide-in-from-top-2 duration-200">
          <div className="flex flex-col space-y-2 py-2">
            <button
              onClick={() => scrollToSection('features')}
              className="text-left px-3 py-2 text-sm font-medium rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Tính năng
            </button>
            <button
              onClick={() => scrollToSection('how-it-works')}
              className="text-left px-3 py-2 text-sm font-medium rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Cách hoạt động
            </button>
            <button
              onClick={() => scrollToSection('stats')}
              className="text-left px-3 py-2 text-sm font-medium rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Chuẩn đầu ra 150 TC
            </button>
            <button
              onClick={() => scrollToSection('faq')}
              className="text-left px-3 py-2 text-sm font-medium rounded-lg text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Câu hỏi thường gặp
            </button>
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex flex-col gap-2.5">
            <button
              onClick={() => {
                setIsMobileMenuOpen(false);
                onOpenLoginModal();
              }}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 text-sm font-semibold rounded-xl text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800/80"
            >
              <LogIn className="w-4 h-4" />
              Đăng nhập sinh viên
            </button>
            <button
              onClick={() => {
                setIsMobileMenuOpen(false);
                onNavigateToSignUp();
              }}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 text-sm font-semibold rounded-xl text-[#1565C0] dark:text-[#4D8FE0] bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800"
            >
              <UserPlus className="w-4 h-4" />
              Đăng ký tài khoản
            </button>
            <button
              onClick={() => {
                setIsMobileMenuOpen(false);
                onNavigateToChat();
              }}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 text-sm font-bold text-white bg-gradient-to-r from-[#1565C0] to-[#3F51B5] rounded-xl shadow-md"
            >
              <MessageSquare className="w-4 h-4" />
              Mở Trợ Lý Tư Vấn Học Vụ
            </button>
          </div>
        </div>
      )}
    </header>
  );
};

