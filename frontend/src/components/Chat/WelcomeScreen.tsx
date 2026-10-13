import React from 'react';
import { LhuLogo } from '../Common/LhuLogo';
import { Composer } from './Composer';
import { getTimeGreeting } from '../../utils/dateGrouping';
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
}) => {
  const greeting = getTimeGreeting();

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-8 max-w-4xl mx-auto w-full select-none animate-fade-in -mt-6">
      {/* 1. Logo tròn vàng (có viền mờ, bo tròn) */}
      <div className="mb-4">
        <LhuLogo size="lg" withGlow />
      </div>

      {/* 2. Dòng nhỏ: "LHU AI · Đại học Lạc Hồng" */}
      <div className="text-xs md:text-sm text-[#6B6B6B] mb-5 tracking-wide">
        <span className="font-bold text-[#1F1F1F]">LHU AI</span> · Đại học Lạc Hồng
      </div>

      {/* 3. Tiêu đề lớn: Lời chào theo thời gian trong ngày */}
      <div className="text-center max-w-2xl mb-8 px-2">
        <h2 className="text-3xl sm:text-4xl md:text-[40px] font-medium text-[#1F1F1F] leading-[1.25] tracking-tight">
          {greeting} Mình là LHU
          <br />
          AI. Mình có thể giúp gì cho bạn?
        </h2>
      </div>

      {/* 4. Ô nhập liệu (Composer) nằm ngay dưới tiêu đề */}
      <div className="w-full max-w-[880px]">
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
