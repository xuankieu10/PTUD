import React, { useState } from 'react';
import { ChevronDown, HelpCircle } from 'lucide-react';

export const FaqAccordion: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  const faqs = [
    {
      q: 'Điều kiện xét tốt nghiệp đại học tại LHU gồm những gì?',
      a: 'Theo Chương IV – Điều 27 Quy chế đào tạo tín chỉ, sinh viên cần đạt 5 điều kiện: (1) Không đang trong thời gian bị truy cứu trách nhiệm hình sự; (2) Tích lũy đủ số học phần theo chương trình, không còn học phần bị điểm dưới 5.0; (3) Đạt kỳ thi tốt nghiệp Mác-Lênin & Tư tưởng Hồ Chí Minh; (4) Có chứng chỉ Giáo dục Quốc phòng và Giáo dục Thể chất; (5) Đạt chuẩn đầu ra 150 tín chỉ / 8 học kỳ.'
    },
    {
      q: 'Bị điểm dưới 4.0 (hoặc dưới 5.0) có bắt buộc phải học lại ngay không?',
      a: 'Theo Điều 13-23 Quy chế đào tạo, vào cuối mỗi học kỳ nhà trường tổ chức thi lần 1 và thi lần 2 cho kỳ thi cuối kỳ. Nếu bạn không bị cấm thi (vắng không quá 20% số tiết và điểm thành phần ≥ 2.0), bạn được quyền đăng ký dự thi lại lần 2. Chỉ khi thi lần 2 vẫn không đạt hoặc bị cấm thi thì mới bắt buộc phải đăng ký học lại.'
    },
    {
      q: 'Chuẩn đầu ra Ngoại ngữ & Tin học yêu cầu những chứng chỉ nào?',
      a: 'Sinh viên Khoa Công nghệ Thông tin cần đạt chứng chỉ Tiếng Anh Bậc 3 theo Khung năng lực ngoại ngữ 6 bậc (hoặc chứng chỉ tương đương như VSTEP Bậc 3, TOEIC/IELTS theo quy định) và chứng chỉ Ứng dụng Công nghệ Thông tin cơ bản. Bạn có thể theo dõi lịch thi trực tiếp trên hệ thống HocVuAI.'
    },
    {
      q: 'Nếu lỡ trễ hạn đăng ký học phần trực tuyến thì phải làm sao?',
      a: 'Nếu quá hạn đăng ký form online, bạn cần: (1) Theo dõi thông báo mở đợt bổ sung trên App ME; (2) Tham gia group Zalo hỗ trợ học vụ của Khoa; (3) Đến trực tiếp Văn phòng Khoa CNTT tại phòng B301 - B302, Cơ sở 1 (Số 10 Huỳnh Văn Nghệ, Biên Hòa) trong giờ hành chính để được giáo vụ hỗ trợ giải quyết.'
    },
    {
      q: 'Dữ liệu bảng điểm và thông tin cá nhân của em có được bảo mật không?',
      a: 'Hệ thống bảo mật tuyệt đối. Khi bạn upload file ảnh hoặc PDF bảng điểm để trích xuất, file tạm chỉ được lưu tạm thời để xử lý và tự động xóa vĩnh viễn (cleanup 100%) ngay sau khi trích xuất xong. Dữ liệu học vụ chỉ hiển thị cho chính sinh viên đã đăng nhập qua token JWT.'
    }
  ];

  const toggleAccordion = (idx: number) => {
    setOpenIndex(openIndex === idx ? null : idx);
  };

  return (
    <section id="faq" className="py-16 md:py-24 bg-slate-50/60 dark:bg-[#0F1B2D] border-t border-slate-200/80 dark:border-slate-800/80 transition-colors">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Header */}
        <div className="text-center space-y-4 mb-12 sm:mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300">
            <HelpCircle className="w-3.5 h-3.5" />
            Giải Đáp Thắc Mắc
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Những Câu Hỏi Thường Gặp
          </h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300">
            Tất cả các thắc mắc cốt lõi về quy chế học vụ, kỳ thi và điều kiện tốt nghiệp được giải đáp rõ ràng.
          </p>
        </div>

        {/* Accordion List */}
        <div className="space-y-4">
          {faqs.map((faq, idx) => {
            const isOpen = openIndex === idx;
            return (
              <div 
                key={idx}
                className="rounded-2xl bg-white dark:bg-[#162338] border border-slate-200 dark:border-slate-700/80 overflow-hidden shadow-2xs transition-all"
              >
                <button
                  onClick={() => toggleAccordion(idx)}
                  className="w-full px-5 py-4.5 sm:px-6 sm:py-5 text-left flex items-center justify-between gap-4 hover:bg-slate-50 dark:hover:bg-[#1A2942] transition-colors cursor-pointer"
                  aria-expanded={isOpen}
                >
                  <span className="text-sm sm:text-base font-bold text-slate-900 dark:text-white">
                    {faq.q}
                  </span>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 transition-transform duration-200 ${isOpen ? 'rotate-180 bg-blue-100 text-[#1565C0] dark:bg-blue-900/50 dark:text-blue-300' : ''}`}>
                    <ChevronDown className="w-4 h-4" />
                  </div>
                </button>

                {isOpen && (
                  <div className="px-5 pb-5 sm:px-6 sm:pb-6 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-t border-slate-100 dark:border-slate-800/80 pt-4 animate-in fade-in-50 duration-150">
                    {faq.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

