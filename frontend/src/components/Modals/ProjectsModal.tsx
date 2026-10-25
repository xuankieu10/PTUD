import React from 'react';
import { X, BookOpen, GraduationCap, Award, FileSearch, Sparkles } from 'lucide-react';

interface ProjectsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectProjectPrompt?: (prompt: string) => void;
}

export const ProjectsModal: React.FC<ProjectsModalProps> = ({
  isOpen,
  onClose,
  onSelectProjectPrompt,
}) => {
  if (!isOpen) return null;

  const projects = [
    {
      title: 'Tư Vấn Tốt Nghiệp & Học Vụ AI',
      desc: 'Trợ lý tra cứu quy chế, cảnh báo điểm F, tính toán tín chỉ tích lũy và kiểm tra điều kiện tốt nghiệp.',
      icon: <GraduationCap className="w-5 h-5 text-[#1565C0] dark:text-[#4D8FE0]" />,
      prompt: 'Kiểm tra điều kiện tốt nghiệp của tôi và phân tích các môn còn nợ.',
    },
    {
      title: 'Trích Xuất Bảng Điểm & OCR Vùng Đỏ',
      desc: 'Pipeline xử lý thị giác máy tính OpenCV + Ollama Vision tự động nhận diện môn học dưới 4.0.',
      icon: <FileSearch className="w-5 h-5 text-indigo-500" />,
      prompt: 'Hướng dẫn tôi cách quét và tải lên bảng điểm học tập để phân tích.',
    },
    {
      title: 'Đối Chiếu Chứng Chỉ Ngoại Ngữ & Tin Học',
      desc: 'Tự động bóc tách thông tin chứng chỉ và so khớp chuẩn đầu ra tốt nghiệp của Đại học Lạc Hồng.',
      icon: <Award className="w-5 h-5 text-amber-500" />,
      prompt: 'Quy định chuẩn đầu ra chứng chỉ tiếng Anh và tin học tốt nghiệp là gì?',
    },
    {
      title: 'Tra Cứu Quy Chế Đào Tạo & Niên Giám',
      desc: 'Hệ thống RAG tìm kiếm ngữ nghĩa trên cơ sở dữ liệu văn bản quy định của nhà trường.',
      icon: <BookOpen className="w-5 h-5 text-emerald-500" />,
      prompt: 'Quy chế về việc bảo lưu kết quả học tập và nghỉ học tạm thời như thế nào?',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-2xs animate-fade-in select-none">
      <div className="bg-white dark:bg-[#162338] rounded-3xl max-w-xl w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-700 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[#1565C0] dark:text-[#4D8FE0]" />
            <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
              Khám phá tính năng AI LHU
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-500 dark:text-slate-400 my-3">
          Chọn một chủ đề chuyên biệt bên dưới để bắt đầu hội thoại với trợ lý trí tuệ nhân tạo:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-2">
          {projects.map((proj, idx) => (
            <div
              key={idx}
              onClick={() => {
                if (onSelectProjectPrompt) {
                  onSelectProjectPrompt(proj.prompt);
                  onClose();
                }
              }}
              className="p-4 rounded-2xl border border-slate-200 dark:border-slate-700 hover:border-[#1565C0] dark:hover:border-[#4D8FE0] bg-slate-50/50 dark:bg-slate-800/40 hover:bg-white dark:hover:bg-slate-800 transition-all cursor-pointer shadow-2xs hover:shadow-md group flex flex-col justify-between"
            >
              <div>
                <div className="p-2 rounded-xl bg-white dark:bg-slate-700 shadow-2xs inline-block mb-2 group-hover:scale-105 transition-transform">
                  {proj.icon}
                </div>
                <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100 group-hover:text-[#1565C0] dark:group-hover:text-[#4D8FE0] transition-colors mb-1">
                  {proj.title}
                </h4>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                  {proj.desc}
                </p>
              </div>

              <div className="mt-3 pt-2 border-t border-slate-100 dark:border-slate-700/60 flex items-center justify-between text-[11px] text-[#1565C0] dark:text-[#4D8FE0] font-medium">
                <span>Bắt đầu ngay</span>
                <span className="group-hover:translate-x-1 transition-transform">→</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
