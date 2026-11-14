import React from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  BookOpen, 
  CheckCircle2, 
  ShieldCheck, 
  Bot, 
  User, 
  FileCheck2,
  CalendarDays,
  GraduationCap
} from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';

interface HeroSectionProps {
  onStartChat: () => void;
  onExploreFeatures: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({
  onStartChat,
  onExploreFeatures,
}) => {
  return (
    <section className="relative overflow-hidden pt-8 pb-16 md:pt-16 md:pb-24 lg:pt-20 lg:pb-32 bg-gradient-to-b from-blue-50/50 via-white to-slate-50/50 dark:from-[#0F1B2D] dark:via-[#132034] dark:to-[#0F1B2D]">
      {/* Background Decorative Blur Orbs */}
      <div className="absolute top-10 left-1/2 -translate-x-1/2 w-[600px] h-[350px] bg-gradient-to-tr from-blue-400/20 to-indigo-500/20 dark:from-blue-600/15 dark:to-purple-600/15 rounded-full blur-3xl pointer-events-none -z-10" />
      <div className="absolute top-40 right-[-100px] w-72 h-72 bg-blue-300/15 dark:bg-blue-500/10 rounded-full blur-2xl pointer-events-none -z-10" />
      <div className="absolute bottom-10 left-[-80px] w-80 h-80 bg-purple-300/15 dark:bg-indigo-500/10 rounded-full blur-2xl pointer-events-none -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto space-y-6">
          
          {/* Badge Tag */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-100/80 dark:bg-blue-900/40 border border-blue-200/80 dark:border-blue-700/60 shadow-2xs">
            <Sparkles className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />
            <span className="text-xs sm:text-sm font-semibold text-[#1565C0] dark:text-[#4D8FE0]">
              Hệ thống RAG Tư Vấn Học Vụ 2026 • Đại học Lạc Hồng
            </span>
          </div>

          {/* Main Headline */}
          <h1 className="text-3xl sm:text-5xl lg:text-6xl font-black text-slate-900 dark:text-white tracking-tight leading-[1.18]">
            Tư Vấn Học Vụ Thông Minh <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-[#1565C0] via-[#283593] to-[#5C6BC0] dark:from-[#4D8FE0] dark:via-[#7986CB] dark:to-[#9FA8DA] bg-clip-text text-transparent">
              Tốt Nghiệp Đúng Hạn Cùng AI
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed font-normal">
            Trợ lý AI chuyên biệt cho sinh viên LHU: Tự động đối soát chuẩn đầu ra <strong>150 tín chỉ</strong>, phân tích bảng điểm bằng <strong>Vision OCR</strong>, hướng dẫn thi lại/học lại và cập nhật lịch thi chứng chỉ tức thì.
          </p>

          {/* CTA Buttons */}
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5">
            <button
              onClick={onStartChat}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-7 py-3.5 text-base font-bold text-white bg-gradient-to-r from-[#1565C0] to-[#3F51B5] hover:from-[#0D47A1] hover:to-[#303F9F] rounded-2xl shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/35 transition-all transform hover:-translate-y-0.5 cursor-pointer"
            >
              <Bot className="w-5 h-5" />
              Bắt đầu trò chuyện với AI
              <ArrowRight className="w-4 h-4" />
            </button>

            <button
              onClick={onExploreFeatures}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 text-base font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-[#162338] hover:bg-slate-100 dark:hover:bg-[#1F2F4A] border border-slate-200 dark:border-slate-700/80 rounded-2xl shadow-xs transition-all cursor-pointer"
            >
              <BookOpen className="w-4 h-4 text-slate-500" />
              Khám phá tính năng
            </button>
          </div>

          {/* Trust Highlights */}
          <div className="pt-3 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs sm:text-sm text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              100% Trích nguồn Quy chế Điều 27
            </span>
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-blue-500" />
              Bảo mật hồ sơ cá nhân
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileCheck2 className="w-4 h-4 text-indigo-500" />
              Đạt 202/202 Tiêu chuẩn kiểm thử
            </span>
          </div>
        </div>

        {/* Interactive Chat Mockup Card */}
        <div className="mt-12 sm:mt-16 max-w-4xl mx-auto">
          <div className="relative rounded-3xl p-2 sm:p-3 bg-gradient-to-b from-blue-200/50 via-indigo-100/30 to-purple-200/40 dark:from-blue-900/30 dark:via-slate-800/40 dark:to-indigo-950/30 shadow-2xl border border-white/60 dark:border-white/10 backdrop-blur-md">
            
            {/* Window Container */}
            <div className="rounded-2xl bg-white dark:bg-[#162338] border border-slate-200/90 dark:border-slate-700/70 overflow-hidden shadow-inner">
              
              {/* Window Header */}
              <div className="px-4 py-3 bg-slate-50/90 dark:bg-[#1B2A42] border-b border-slate-200 dark:border-slate-700/70 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-red-400 inline-block" />
                    <span className="w-3 h-3 rounded-full bg-amber-400 inline-block" />
                    <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block" />
                  </div>
                  <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 ml-2 hidden sm:inline">
                    HocVuAI • Trợ lý tư vấn học vụ chuẩn LHU
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                  <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                    Trực tuyến 24/7
                  </span>
                </div>
              </div>

              {/* Chat Canvas Simulation */}
              <div className="p-4 sm:p-6 space-y-4 text-sm font-sans bg-slate-50/40 dark:bg-[#121E31]/50">
                
                {/* User Message */}
                <div className="flex items-start gap-3 justify-end">
                  <div className="max-w-[85%] sm:max-w-md rounded-2xl rounded-tr-xs p-3.5 bg-gradient-to-r from-[#1565C0] to-[#283593] text-white shadow-xs">
                    <p className="text-sm font-medium leading-relaxed">
                      Em đang là sinh viên năm cuối Khoa CNTT. Em bị nợ 1 môn chuyên ngành (điểm 3.5) và chưa thi VSTEP, em có kịp điều kiện xét tốt nghiệp đợt tới không ạ?
                    </p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 font-bold text-xs">
                    <User className="w-4 h-4" />
                  </div>
                </div>

                {/* AI Assistant Message */}
                <div className="flex items-start gap-3 justify-start">
                  <div className="w-8 h-8 rounded-full bg-[#1565C0] text-white flex items-center justify-center shrink-0 shadow-xs">
                    <LhuLogo size="sm" variant="avatar" />
                  </div>

                  <div className="max-w-[92%] sm:max-w-xl rounded-2xl rounded-tl-xs p-4 bg-white dark:bg-[#1C2C46] border border-slate-200/80 dark:border-slate-700/80 text-slate-800 dark:text-slate-100 shadow-xs space-y-3">
                    <p className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5 text-xs text-[#1565C0] dark:text-[#4D8FE0]">
                      <GraduationCap className="w-4 h-4" />
                      TƯ VẤN ĐIỀU KIỆN TỐT NGHIỆP DỰA TRÊN HỒ SƠ & QUY CHẾ:
                    </p>

                    <div className="space-y-2 text-xs sm:text-sm text-slate-700 dark:text-slate-200">
                      <div className="p-2.5 rounded-xl bg-blue-50/80 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-900/60">
                        <p className="font-semibold text-[#1565C0] dark:text-blue-300">1. Tiến độ tín chỉ tích lũy:</p>
                        <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                          Bạn đã tích lũy <strong>137/150 tín chỉ</strong>. Cần tích lũy thêm 13 tín chỉ để đạt chuẩn đầu ra tối thiểu.
                        </p>
                      </div>

                      <div className="p-2.5 rounded-xl bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200/80 dark:border-amber-900/60">
                        <p className="font-semibold text-amber-800 dark:text-amber-300">2. Môn nợ điểm 3.5 (Cấu trúc dữ liệu):</p>
                        <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                          Theo <strong>Điều 13-23</strong>, điểm 3.5 vẫn còn quyền dự thi lại lần 2 cuối kỳ. Nếu qua lần 2, bạn không phải học lại!
                        </p>
                      </div>

                      <div className="p-2.5 rounded-xl bg-indigo-50/80 dark:bg-indigo-950/40 border border-indigo-200/80 dark:border-indigo-900/60">
                        <p className="font-semibold text-indigo-800 dark:text-indigo-300 flex items-center gap-1">
                          <CalendarDays className="w-3.5 h-3.5" />
                          3. Lịch thi chứng chỉ VSTEP sắp tới:
                        </p>
                        <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">
                          Kỳ thi gần nhất vào ngày <strong>27/12/2026</strong> (Hạn đăng ký trước 19h ngày 20/12). Bạn nên đăng ký sớm tại Trung tâm NNTH để kịp nộp hồ sơ đợt xét tốt nghiệp.
                        </p>
                      </div>
                    </div>

                    {/* Sources Badge */}
                    <div className="pt-2 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between text-[11px] text-slate-500">
                      <span className="flex items-center gap-1 text-slate-600 dark:text-slate-400">
                        <ShieldCheck className="w-3.5 h-3.5 text-blue-500" />
                        Nguồn: Quy chế Đào tạo LHU (Điều 27) & Trung tâm NNTH
                      </span>
                      <span className="text-[10px] bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-md font-mono">
                        bge-m3 • qwen2.5
                      </span>
                    </div>
                  </div>
                </div>

              </div>

              {/* Fake Input Footer */}
              <div className="p-3 bg-white dark:bg-[#162338] border-t border-slate-200 dark:border-slate-700/70 flex items-center gap-2">
                <input 
                  type="text" 
                  disabled 
                  placeholder="Hỏi AI: Em cần điều kiện gì để được xét tốt nghiệp đại học?"
                  className="flex-1 text-xs sm:text-sm bg-slate-100/80 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-slate-400 select-none cursor-pointer"
                  onClick={onStartChat}
                />
                <button 
                  onClick={onStartChat}
                  className="px-3.5 py-2 text-xs font-bold text-white bg-[#1565C0] hover:bg-[#0D47A1] rounded-xl cursor-pointer"
                >
                  Gửi
                </button>
              </div>

            </div>
          </div>
        </div>

      </div>
    </section>
  );
};

