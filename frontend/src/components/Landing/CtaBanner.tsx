import React from 'react';
import { ArrowRight, Sparkles, UserPlus } from 'lucide-react';

interface CtaBannerProps {
  onSignUp: () => void;
  onOpenChat: () => void;
}

export const CtaBanner: React.FC<CtaBannerProps> = ({ onSignUp, onOpenChat }) => {
  return (
    <section className="py-16 md:py-20 bg-white dark:bg-[#121E31] transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        <div className="relative rounded-3xl overflow-hidden p-8 sm:p-12 md:p-16 bg-gradient-to-r from-[#0D47A1] via-[#1565C0] to-[#3949AB] text-white shadow-2xl">
          
          {/* Decorative Background Shapes */}
          <div className="absolute top-0 right-0 -mt-12 -mr-12 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 -mb-12 -ml-12 w-80 h-80 bg-blue-300/10 rounded-full blur-2xl pointer-events-none" />

          <div className="relative z-10 max-w-2xl mx-auto text-center space-y-6">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 backdrop-blur-xs text-blue-100">
              <Sparkles className="w-3.5 h-3.5" />
              Sẵn sàng cho ngày tốt nghiệp
            </div>

            <h2 className="text-2xl sm:text-4xl md:text-5xl font-black tracking-tight leading-tight">
              Bắt Đầu Lộ Trình Tốt Nghiệp Đúng Hạn Cùng HocVuAI
            </h2>

            <p className="text-sm sm:text-base text-blue-100/90 leading-relaxed font-normal">
              Tham gia cùng hàng nghìn sinh viên Đại học Lạc Hồng để được giải đáp mọi thắc mắc học vụ 24/7 hoàn toàn miễn phí.
            </p>

            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5">
              <button
                onClick={onSignUp}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-7 py-3.5 text-sm sm:text-base font-bold text-[#1565C0] bg-white hover:bg-blue-50 rounded-2xl shadow-lg transition-all transform hover:-translate-y-0.5 cursor-pointer"
              >
                <UserPlus className="w-4 h-4" />
                Đăng ký tài khoản miễn phí
              </button>

              <button
                onClick={onOpenChat}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3.5 text-sm sm:text-base font-bold text-white bg-white/15 hover:bg-white/25 border border-white/25 rounded-2xl backdrop-blur-xs transition-all cursor-pointer"
              >
                Trải nghiệm Chatbot ngay
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
};

