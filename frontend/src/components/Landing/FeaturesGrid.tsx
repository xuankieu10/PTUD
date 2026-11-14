import React from 'react';
import { 
  GraduationCap, 
  ScanLine, 
  GitFork, 
  BookMarked, 
  CalendarCheck, 
  ShieldCheck,
  CheckCircle2,
  ArrowRight
} from 'lucide-react';

interface FeaturesGridProps {
  onSelectFeature?: (featureId: string) => void;
}

export const FeaturesGrid: React.FC<FeaturesGridProps> = ({ onSelectFeature }) => {
  const features = [
    {
      id: 'grad-check',
      icon: GraduationCap,
      color: 'from-blue-500 to-indigo-600',
      badge: 'Chuẩn 150 tín chỉ',
      title: 'Tư Vấn Chuẩn Đầu Ra Tốt Nghiệp',
      description: 'Tự động rà soát tiến độ tích lũy 150 tín chỉ, phát hiện các môn bắt buộc còn thiếu theo khung chương trình đào tạo từng chuyên ngành.',
      highlights: ['Chuẩn hóa 150 tín chỉ / 8 học kỳ', 'Điều 27 Quy chế đào tạo', 'Kiểm tra chứng chỉ GDQP & GDTC']
    },
    {
      id: 'ocr-scanner',
      icon: ScanLine,
      color: 'from-cyan-500 to-blue-600',
      badge: 'Vision AI + OpenCV',
      title: 'Quét & Nhận Diện Bảng Điểm',
      description: 'Đọc file ảnh và PDF scan bảng điểm, nhận diện điểm số và kết hợp thuật toán OpenCV HSV phát hiện chính xác các ô bị khoanh đỏ.',
      highlights: ['Hỗ trợ PNG, JPG, PDF scan', 'Phát hiện vùng đỏ đánh dấu', 'Tự động trích xuất điểm số']
    },
    {
      id: 'grade-filter',
      icon: GitFork,
      color: 'from-amber-500 to-orange-600',
      badge: '3 Nhánh Phân Loại',
      title: 'Phân Loại Môn Chưa Đạt Chuẩn Xác',
      description: 'Phân loại môn nợ thông minh: môn bị cấm thi (bắt buộc học lại), môn được quyền thi lại lần 2 cuối kỳ, và môn cần xác nhận với giáo vụ.',
      highlights: ['Tách biệt điểm 0 và thi lần 2', 'Không khuyên học lại nhầm lẫn', 'Hướng dẫn form trực tuyến & Zalo']
    },
    {
      id: 'regulations',
      icon: BookMarked,
      color: 'from-purple-500 to-indigo-600',
      badge: 'RAG Không Ảo Giác',
      title: 'Tra Cứu Quy Chế Đào Tạo & Học Vụ',
      description: 'Trích dẫn chính xác từng điều khoản quy chế (cấm thi Điều 19, học lại Điều 12, cảnh báo học vụ Điều 24), kèm hướng dẫn trễ hạn đăng ký.',
      highlights: ['100% Trích nguồn có số hiệu', 'Chống bịa đặt quy chế học vụ', 'Thông tin liên hệ Khoa CNTT B301']
    },
    {
      id: 'center-schedule',
      icon: CalendarCheck,
      color: 'from-emerald-500 to-teal-600',
      badge: 'Đồng Bộ Tự Động',
      title: 'Lịch Thi & Khóa Học NNTH LHU',
      description: 'Cập nhật liên tục lịch thi VSTEP, chuẩn 6 bậc CEFR, Ứng dụng CNTT cơ bản và các lớp ôn thi trực tuyến từ Trung tâm Ngoại ngữ - Tin học.',
      highlights: ['Đồng bộ lịch thi chính thức & dự kiến', 'Hạn đăng ký & mức lệ phí rõ ràng', 'Lớp ôn thi VSTEP, CNTT Cơ bản']
    },
    {
      id: 'privacy-security',
      icon: ShieldCheck,
      color: 'from-rose-500 to-pink-600',
      badge: 'Bảo Mật Tuyệt Đối',
      title: 'Cá Nhân Hóa & Bảo Mật Dữ Liệu',
      description: 'Mỗi sinh viên sở hữu không gian tư vấn riêng biệt, xác thực JWT an toàn. Tự động xóa file upload ngay sau khi xử lý xong.',
      highlights: ['Ngăn chặn truy cập chéo ID', 'Dọn dẹp file tạm 100%', 'Tư vấn riêng theo mã số sinh viên']
    },
  ];

  return (
    <section id="features" className="py-16 md:py-24 bg-white dark:bg-[#121E31] transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Section Header */}
        <div className="text-center max-w-3xl mx-auto space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-[#1565C0] dark:bg-blue-900/40 dark:text-[#4D8FE0]">
            Tính Năng Vượt Trội
          </div>
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            Giải Quyết Toàn Bộ Nỗi Lo Học Vụ Của Bạn
          </h2>
          <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300">
            Được thiết kế riêng theo đặc thù quy chế đào tạo tín chỉ Đại học Lạc Hồng, HocVuAI mang đến công cụ hỗ trợ học tập đắc lực và đáng tin cậy.
          </p>
        </div>

        {/* Feature Grid */}
        <div className="mt-12 sm:mt-16 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          {features.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.id}
                className="group relative rounded-3xl p-6 sm:p-7 bg-slate-50/80 dark:bg-[#18273E] border border-slate-200/90 dark:border-slate-700/70 hover:border-blue-400 dark:hover:border-blue-500/80 shadow-xs hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 transform hover:-translate-y-1 flex flex-col justify-between"
              >
                <div>
                  {/* Top Header */}
                  <div className="flex items-center justify-between">
                    <div className={`w-12 h-12 rounded-2xl bg-gradient-to-tr ${item.color} text-white flex items-center justify-center shadow-md shadow-blue-500/20`}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 shadow-2xs">
                      {item.badge}
                    </span>
                  </div>

                  {/* Title & Description */}
                  <h3 className="mt-5 text-lg sm:text-xl font-bold text-slate-900 dark:text-white group-hover:text-[#1565C0] dark:group-hover:text-[#4D8FE0] transition-colors">
                    {item.title}
                  </h3>
                  <p className="mt-2.5 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-normal">
                    {item.description}
                  </p>

                  {/* Key Highlights */}
                  <div className="mt-5 pt-4 border-t border-slate-200/70 dark:border-slate-700/60 space-y-2">
                    {item.highlights.map((h, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-300">
                        <CheckCircle2 className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                        <span>{h}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Bottom Action */}
                <div className="mt-6 pt-2">
                  <button 
                    onClick={() => onSelectFeature && onSelectFeature(item.id)}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-[#1565C0] dark:text-[#4D8FE0] hover:text-[#0D47A1] group-hover:translate-x-1 transition-all cursor-pointer"
                  >
                    Trải nghiệm tính năng
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

