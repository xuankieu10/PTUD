import React from 'react';
import { UserCheck, FileUp, Sparkles, ArrowRight } from 'lucide-react';

interface HowItWorksProps {
  onStartNow: () => void;
}

export const HowItWorks: React.FC<HowItWorksProps> = ({ onStartNow }) => {
  const steps = [
    {
      step: '01',
      icon: UserCheck,
      title: 'Đăng Ký & Đăng Nhập',
      desc: 'Tạo tài khoản với Mã số sinh viên (MSSV) và Khoa theo học tại LHU để hệ thống cá nhân hóa khung chương trình đào tạo của bạn.',
      badge: 'Chỉ mất 30 giây'
    },
    {
      step: '02',
      icon: FileUp,
      title: 'Tải Bảng Điểm Hoặc Tra Cứu',
      desc: 'Kéo thả file ảnh chụp hoặc PDF bảng điểm để AI tự động trích xuất điểm số, phát hiện các môn đánh dấu đỏ và tổng hợp số tín chỉ đã đạt.',
      badge: 'Đọc tự động'
    },
    {
      step: '03',
      icon: Sparkles,
      title: 'Nhận Tư Vấn Tốt Nghiệp',
      desc: 'Chat trực tiếp với AI để xem số tín chỉ còn thiếu (chuẩn 150 TC), hướng dẫn đăng ký thi lại lần 2, lịch thi chứng chỉ ngoại ngữ và lộ trình ra trường.',
      badge: 'Chính xác 100%'
    }
  ];

  return (
    <section id="how-it-works" className="py-16 md:py-24 bg-slate-50/70 dark:bg-[#0F1B2D] border-y border-slate-200/70 dark:border-slate-800/80 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
            Quy Trình Sử Dụng
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Chỉ 3 Bước Đơn Giản Để Làm Chủ Kế Hoạch Học Tập
          </h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300">
            Không còn phải tự tính toán tín chỉ thủ công hay băn khoăn về quy chế thi lại.
          </p>
        </div>

        {/* Steps Grid */}
        <div className="mt-12 sm:mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 relative">
          {steps.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div 
                key={idx}
                className="relative rounded-3xl p-7 bg-white dark:bg-[#162338] border border-slate-200 dark:border-slate-700/80 shadow-xs hover:shadow-lg transition-all duration-300 flex flex-col justify-between"
              >
                <div>
                  {/* Step Number & Badge */}
                  <div className="flex items-center justify-between">
                    <span className="text-3xl sm:text-4xl font-black text-blue-100 dark:text-slate-700 select-none">
                      {item.step}
                    </span>
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/60 text-[#1565C0] dark:text-[#4D8FE0] border border-blue-100 dark:border-blue-900/60">
                      {item.badge}
                    </span>
                  </div>

                  {/* Icon */}
                  <div className="mt-4 w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-900/30 text-[#1565C0] dark:text-[#4D8FE0] flex items-center justify-center">
                    <Icon className="w-6 h-6" />
                  </div>

                  {/* Step Content */}
                  <h3 className="mt-5 text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-normal">
                    {item.desc}
                  </p>
                </div>

                <div className="mt-6 pt-4 border-t border-slate-100 dark:border-slate-800 text-xs font-semibold text-slate-400">
                  Bước {idx + 1} trên 3
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom CTA */}
        <div className="mt-12 text-center">
          <button
            onClick={onStartNow}
            className="inline-flex items-center gap-2 px-6 py-3 text-sm font-bold text-white bg-[#1565C0] hover:bg-[#0D47A1] rounded-xl shadow-md transition-all cursor-pointer"
          >
            Bắt đầu trải nghiệm ngay
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>

      </div>
    </section>
  );
};

