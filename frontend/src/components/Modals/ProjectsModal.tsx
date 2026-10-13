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
      icon: <GraduationCap className="w-5 h-5 text-[#F5B800]" />,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-2xs animate-fade-in">
      <div className="bg-white rounded-3xl max-w-xl w-full p-6 shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-[#F5B800]" />
            <h3 className="text-base font-bold text-[#1F1F1F]">Khám phá dự án AI LHU</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500 hover:text-gray-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-[#6B6B6B] mt-3 mb-4">
          Các dự án và mô-đun chuyên biệt phục vụ học vụ sinh viên và cán bộ giảng viên LHU:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {projects.map((p, idx) => (
            <div
              key={idx}
              onClick={() => {
                if (onSelectProjectPrompt) {
                  onSelectProjectPrompt(p.prompt);
                }
                onClose();
              }}
              className="p-4 rounded-2xl border border-gray-100 bg-[#F9FAFB] hover:bg-white hover:border-[#F5B800] hover:shadow-md cursor-pointer transition-all duration-200 group"
            >
              <div className="w-10 h-10 rounded-xl bg-white shadow-2xs flex items-center justify-center mb-3 group-hover:scale-105 transition-transform">
                {p.icon}
              </div>
              <h4 className="font-semibold text-xs text-[#1F1F1F] mb-1 group-hover:text-[#F5B800] transition-colors">
                {p.title}
              </h4>
              <p className="text-[11px] text-[#6B6B6B] leading-relaxed line-clamp-3">
                {p.desc}
              </p>
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
