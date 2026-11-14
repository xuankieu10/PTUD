import React from 'react';
import { Star, Quote, User } from 'lucide-react';

export const Testimonials: React.FC = () => {
  const reviews = [
    {
      name: 'Nguyễn Thành Luân',
      role: 'Sinh viên K65 • Kỹ thuật phần mềm',
      content: 'Nhờ HocVuAI mà mình biết được điểm 3.8 môn Cơ sở dữ liệu của mình vẫn còn quyền thi lại lần 2 chứ không phải đóng tiền học lại! AI còn hướng dẫn rõ lịch đăng ký thi.',
      rating: 5
    },
    {
      name: 'Trần Thị Thu Thảo',
      role: 'Sinh viên K64 • Khoa CNTT',
      content: 'Lúc nộp hồ sơ tốt nghiệp mình rất lo vì không biết đã đủ 150 tín chỉ chưa. Hệ thống đối chiếu một cái là ra liền số tín chỉ còn thiếu và nhắc mình nộp bổ sung chứng chỉ VSTEP.',
      rating: 5
    },
    {
      name: 'Lê Hoàng Phúc',
      role: 'Sinh viên K66 • Hệ thống thông tin',
      content: 'Tính năng quét bảng điểm bằng camera rất tiện! Mình upload ảnh bảng điểm bị mờ một chút mà bot vẫn đọc đúng môn và phân loại chuẩn. Giao diện trực quan, dễ dùng.',
      rating: 5
    }
  ];

  return (
    <section className="py-16 md:py-24 bg-white dark:bg-[#121E31] transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
            Trải Nghiệm Thực Tế
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Được Tin Dùng Bởi Sinh Viên Đại Học Lạc Hồng
          </h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300">
            HocVuAI đồng hành cùng các bạn vượt qua từng kỳ học và tự tin bước tới ngày nhận bằng tốt nghiệp.
          </p>
        </div>

        {/* Reviews Grid */}
        <div className="mt-12 sm:mt-16 grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-8">
          {reviews.map((rev, idx) => (
            <div 
              key={idx}
              className="rounded-3xl p-7 bg-slate-50/90 dark:bg-[#18273E] border border-slate-200/80 dark:border-slate-700/80 shadow-xs flex flex-col justify-between"
            >
              <div>
                {/* Rating Stars & Quote */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex gap-1 text-amber-400">
                    {[...Array(rev.rating)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-amber-400" />
                    ))}
                  </div>
                  <Quote className="w-6 h-6 text-slate-300 dark:text-slate-600" />
                </div>

                <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-200 leading-relaxed font-normal italic">
                  "{rev.content}"
                </p>
              </div>

              {/* Author */}
              <div className="mt-6 pt-4 border-t border-slate-200/70 dark:border-slate-700/60 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 text-[#1565C0] dark:bg-blue-900/40 dark:text-[#4D8FE0] flex items-center justify-center font-bold">
                  <User className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                    {rev.name}
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {rev.role}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
};

