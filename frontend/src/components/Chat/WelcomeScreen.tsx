import React from 'react';
import { GraduationCap, Award, FileSearch, BookOpen, Sparkles } from 'lucide-react';
import { Composer } from './Composer';
import type { AttachedFile } from '../../types';

interface WelcomeScreenProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  files?: AttachedFile[];
  onAddFiles?: (files: File[]) => void;
  onRemoveFile?: (index: number) => void;
  error?: string | null;
  onRetry?: () => void;
  onSelectPrompt?: (prompt: string) => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  input,
  onInputChange,
  onSend,
  isLoading = false,
  files = [],
  onAddFiles,
  onRemoveFile,
  error = null,
  onRetry,
  onSelectPrompt,
}) => {
  // 4 gợi ý câu hỏi mẫu
  const suggestions = [
    {
      title: 'Xét tốt nghiệp',
      desc: 'Kiểm tra điều kiện tốt nghiệp và phân tích các môn còn nợ',
      icon: <GraduationCap className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />,
      prompt: 'Kiểm tra điều kiện tốt nghiệp của tôi và phân tích các môn còn nợ.',
    },
    {
      title: 'Chứng chỉ chuẩn đầu ra',
      desc: 'Chuẩn đầu ra chứng chỉ tiếng Anh & tin học tốt nghiệp',
      icon: <Award className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />,
      prompt: 'Quy định về chuẩn đầu ra chứng chỉ tiếng Anh và tin học tốt nghiệp là gì?',
    },
    {
      title: 'Phân tích bảng điểm',
      desc: 'Hướng dẫn quét bảng điểm & nhận diện vùng cảnh báo F',
      icon: <FileSearch className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />,
      prompt: 'Hướng dẫn tôi cách tải lên bảng điểm học tập để hệ thống AI phân tích môn không đạt.',
    },
    {
      title: 'Quy chế đào tạo',
      desc: 'Quy chế bảo lưu kết quả học tập & nghỉ học tạm thời',
      icon: <BookOpen className="w-4 h-4 text-[#1565C0] dark:text-[#4D8FE0]" />,
      prompt: 'Quy chế về việc bảo lưu kết quả học tập và nghỉ học tạm thời như thế nào?',
    },
  ];

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto px-4 py-6 md:py-8 max-w-[760px] mx-auto w-full select-none animate-fade-in">
      {/* Trung tâm: Logo Khoa CNTT + Lời chào + 4 thẻ gợi ý */}
      <div className="flex-1 flex flex-col items-center justify-center my-auto py-4">
        {/* Logo Khoa CNTT lớn ở giữa (cao ~96px) */}
        <div className="mb-5 p-3 rounded-2xl bg-white dark:bg-[#162338] shadow-sm border border-slate-200/80 dark:border-slate-700/80 inline-flex items-center justify-center">
          <img
            src="/fit-logo-transparent.png"
            alt="Khoa Công nghệ Thông tin"
            className="h-20 sm:h-24 w-auto object-contain select-none transition-transform hover:scale-105 duration-200"
          />
        </div>

        {/* Dòng định danh đơn vị */}
        <div className="flex items-center gap-1.5 text-xs sm:text-sm font-semibold text-slate-500 dark:text-slate-400 mb-2 tracking-wide uppercase">
          <Sparkles className="w-3.5 h-3.5 text-[#1565C0] dark:text-[#4D8FE0]" />
          <span>Khoa Công nghệ Thông tin · Đại học Lạc Hồng</span>
        </div>

        {/* Lời chào: "Xin chào, tôi có thể giúp gì cho bạn?" (chữ đậm, màu --accent) */}
        <h2 className="text-2xl sm:text-3xl md:text-[34px] font-bold text-[#3F51B5] dark:text-[#7986CB] text-center mb-6 tracking-tight leading-snug max-w-xl">
          Xin chào, tôi có thể giúp gì cho bạn?
        </h2>

        {/* 4 thẻ gợi ý câu hỏi (card trắng, bo góc 12px, viền nhạt, hover nổi bóng nhẹ và viền xanh) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mt-2 mb-4">
          {suggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt?.(item.prompt)}
              className="group p-3.5 text-left rounded-[12px] bg-white dark:bg-[#162338] border border-slate-200/90 dark:border-slate-700/90 shadow-2xs hover:shadow-md hover:border-[#1565C0] dark:hover:border-[#4D8FE0] hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className="p-1.5 rounded-lg bg-[#E3F0FC] dark:bg-slate-800 text-[#1565C0] dark:text-[#4D8FE0] group-hover:scale-110 transition-transform">
                  {item.icon}
                </div>
                <span className="text-xs font-bold text-slate-800 dark:text-slate-100 group-hover:text-[#1565C0] dark:group-hover:text-[#4D8FE0] transition-colors">
                  {item.title}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                {item.desc}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Ô nhập tin nhắn cố định ở đáy */}
      <div className="w-full shrink-0 pt-2 pb-1">
        <Composer
          input={input}
          onInputChange={onInputChange}
          onSend={onSend}
          isLoading={isLoading}
          files={files}
          onAddFiles={onAddFiles}
          onRemoveFile={onRemoveFile}
          error={error}
          onRetry={onRetry}
          autoFocus
        />
      </div>
    </div>
  );
};
