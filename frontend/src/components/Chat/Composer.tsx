import React, { useRef, useEffect, useState } from 'react';
import { ArrowUp, Plus, AlertCircle, RotateCw } from 'lucide-react';
import { FileCard } from './FileCard';
import type { AttachedFile } from '../../types';

interface ComposerProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  files?: AttachedFile[];
  onAddFiles?: (files: File[]) => void;
  onRemoveFile?: (index: number) => void;
  error?: string | null;
  onRetry?: () => void;
}

export const Composer: React.FC<ComposerProps> = ({
  input,
  onInputChange,
  onSend,
  isLoading = false,
  placeholder = 'Nhập tin nhắn cho trợ lý AI...',
  className = '',
  autoFocus = false,
  files = [],
  onAddFiles,
  onRemoveFile,
  error = null,
  onRetry,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isOverMaxHeight, setIsOverMaxHeight] = useState(false);

  // Tự động giãn chiều cao theo nội dung (tối đa ~6 dòng / 150px)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const maxHeight = 150; // Khoảng 6 dòng
    const scrollHeight = el.scrollHeight;

    if (scrollHeight > maxHeight) {
      el.style.height = `${maxHeight}px`;
      setIsOverMaxHeight(true);
    } else {
      el.style.height = `${Math.max(scrollHeight, 26)}px`;
      setIsOverMaxHeight(false);
    }
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && (input.trim() || files.length > 0)) {
        onSend();
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0 && onAddFiles) {
      onAddFiles(Array.from(e.target.files));
    }
    if (e.target) {
      e.target.value = '';
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0 && onAddFiles) {
      onAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const canSend = (input.trim().length > 0 || files.length > 0) && !isLoading;

  return (
    <div
      className={`w-full mx-auto select-none ${className}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Hidden File Input kích hoạt trực tiếp từ hệ điều hành */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".png,.jpg,.jpeg,.pdf,.docx,.txt"
        className="hidden"
        onChange={handleFileChange}
      />

      {/* Thông báo lỗi bằng tiếng Việt (nếu có) */}
      {error && (
        <div className="mb-2 px-3.5 py-2 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 rounded-2xl flex items-center justify-between text-xs text-rose-700 dark:text-rose-300 animate-fade-in shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{error}</span>
          </div>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1 font-medium text-rose-700 dark:text-rose-300 hover:text-rose-900 dark:hover:text-white underline ml-2 shrink-0 cursor-pointer"
            >
              <RotateCw className="w-3 h-3" />
              <span>Thử lại</span>
            </button>
          )}
        </div>
      )}

      {/* Danh sách các thẻ tệp (File Cards) phía trên ô nhập */}
      {files.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-2 px-1 animate-fade-in">
          {files.map((file, idx) => (
            <FileCard
              key={file.id || `${file.name}-${idx}`}
              file={file}
              onRemove={onRemoveFile ? () => onRemoveFile(idx) : undefined}
              isUploading={isLoading}
            />
          ))}
        </div>
      )}

      {/* Khung ô nhập bo góc lớn 24px (rounded-[24px]), bóng nhẹ, nền trắng */}
      <div
        className={`relative flex items-end gap-2 bg-white dark:bg-[#162338] border rounded-[24px] px-3.5 py-2 shadow-sm transition-all duration-200 ${
          isDragging
            ? 'border-[#1565C0] bg-blue-50/30 dark:bg-blue-900/20 ring-2 ring-[#1565C0]/30'
            : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 focus-within:border-[#1565C0] dark:focus-within:border-[#4D8FE0] focus-within:ring-2 focus-within:ring-[#1565C0]/15'
        }`}
      >
        {/* Nút đính kèm file bên trái */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          title="Tải tệp lên"
          aria-label="Tải tệp lên"
          className="p-1.5 rounded-full text-slate-500 hover:text-[#1565C0] dark:text-slate-400 dark:hover:text-[#4D8FE0] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors shrink-0 cursor-pointer mb-0.5"
        >
          <Plus className="w-5 h-5 stroke-[2]" />
        </button>

        {/* Textarea tự giãn chiều cao (tối đa ~6 dòng) */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={files.length > 0 ? 'Nhập câu hỏi về tệp hoặc bấm gửi...' : placeholder}
          rows={1}
          autoFocus={autoFocus}
          disabled={isLoading}
          className="flex-1 py-1 px-1 text-sm sm:text-base text-slate-800 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 bg-transparent resize-none focus:outline-none leading-relaxed transition-all"
          style={{
            minHeight: '26px',
            maxHeight: '150px',
            overflowY: isOverMaxHeight ? 'auto' : 'hidden',
          }}
        />

        {/* Nút gửi hình tròn nền --primary bên phải, chuyển xám khi ô trống */}
        <button
          type="button"
          onClick={() => canSend && onSend()}
          disabled={!canSend}
          title="Gửi tin nhắn"
          aria-label="Gửi tin nhắn"
          className={`w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center shrink-0 transition-all duration-150 mb-0.5 ${
            canSend
              ? 'bg-[#1565C0] hover:bg-[#0D47A1] text-white cursor-pointer shadow-xs active:scale-95'
              : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
          }`}
        >
          <ArrowUp className="w-4 h-4 sm:w-4.5 sm:h-4.5 stroke-[2.5]" />
        </button>
      </div>

      {/* Dòng chú thích nhỏ bên dưới theo yêu cầu */}
      <p className="text-center text-[11px] sm:text-xs text-slate-400 dark:text-slate-500 mt-2 font-normal select-none">
        Chatbot có thể mắc sai sót. Hãy kiểm tra thông tin quan trọng.
      </p>
    </div>
  );
};
