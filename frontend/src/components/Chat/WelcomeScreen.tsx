import React from 'react';
import { LhuLogo } from '../Common/LhuLogo';
import { Composer } from './Composer';
import { getTimeGreeting } from '../../utils/dateGrouping';

interface WelcomeScreenProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  onAttachClick?: () => void;
  onSelectPrompt?: (prompt: string) => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  input,
  onInputChange,
  onSend,
  isLoading = false,
  onAttachClick,
  onSelectPrompt,
}) => {
  const greeting = getTimeGreeting();

  const samplePrompts = [
    'Kiểm tra điều kiện tốt nghiệp của tôi',
    'Điểm của tôi có môn nào dưới 4.0 không?',
    'Quy chế học vụ và cảnh báo học tập',
    'Tôi còn thiếu bao nhiêu tín chỉ để tốt nghiệp?',
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 max-w-5xl mx-auto w-full animate-fade-in select-none">
      {/* 1. Logo tròn vàng (có viền mờ, bo tròn) */}
      <div className="mb-4">
        <LhuLogo size="lg" withGlow />
      </div>

      {/* 2. Dòng nhỏ: "LHU AI · Đại học Lạc Hồng" */}
      <div className="text-sm md:text-base text-[#6B6B6B] mb-5 tracking-wide">
        <span className="font-bold text-[#1F1F1F]">LHU AI</span> · Đại học Lạc Hồng
      </div>

      {/* 3. Tiêu đề lớn (~44px, đậm vừa): Lời chào theo thời gian trong ngày */}
      <div className="text-center max-w-3xl mb-8 px-2">
        <h2 className="text-3xl sm:text-4xl md:text-[44px] font-medium text-[#1F1F1F] leading-tight tracking-tight">
          {greeting}
          <br className="hidden sm:inline" />
          <span className="text-[#374151]"> Mình là LHU AI. Mình có thể giúp gì cho bạn?</span>
        </h2>
      </div>

      {/* 4. Ô nhập liệu (Composer) nằm ngay dưới tiêu đề */}
      <div className="w-full">
        <Composer
          input={input}
          onInputChange={onInputChange}
          onSend={onSend}
          isLoading={isLoading}
          onAttachClick={onAttachClick}
          autoFocus
        />
      </div>

      {/* Gợi ý câu hỏi nhanh */}
      {onSelectPrompt && (
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2 max-w-3xl">
          {samplePrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onSelectPrompt(prompt)}
              className="text-xs px-3.5 py-2 rounded-full border border-[#E5E7EB] bg-white text-[#4B5563] hover:text-[#1F1F1F] hover:bg-[#F9FAFB] hover:border-[#D1D5DB] transition-all"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
