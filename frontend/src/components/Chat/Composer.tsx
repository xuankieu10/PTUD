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
  placeholder = 'Bạn muốn tìm hiểu điều gì?',
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

  // Tự động giãn chiều cao theo nội dung và ẩn thanh cuộn khi < 200px
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const maxHeight = 200;
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
      className={`w-full mx-auto ${className}`}
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
        <div className="mb-2.5 px-3.5 py-2 bg-rose-50 border border-rose-200 rounded-2xl flex items-center justify-between text-xs text-rose-700 animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>{error}</span>
          </div>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1 font-medium text-rose-700 hover:text-rose-900 underline ml-2 shrink-0 cursor-pointer"
            >
              <RotateCw className="w-3 h-3" />
              <span>Thử lại</span>
            </button>
          )}
        </div>
      )}

      {/* Danh sách các thẻ tệp (File Cards) phía trên ô nhập */}
      {files.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-2.5 px-1 animate-fade-in">
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

      {/* Khung ô nhập bo tròn dạng viên thuốc (border-radius ~32px) */}
      <div
        className={`relative flex items-center gap-2 bg-white border rounded-full px-4 py-2 shadow-2xs transition-all ${
          isDragging
            ? 'border-[#F5B800] bg-amber-50/20 ring-2 ring-[#F5B800]/30'
            : 'border-[#E5E7EB] hover:border-[#D1D5DB] focus-within:border-[#BDBDBD]'
        }`}
      >
        {/* Nút '+' bên trái (Tải tệp lên) */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          title="Tải tệp lên"
          aria-label="Tải tệp lên"
          className="p-1 rounded-full text-[#6B6B6B] hover:text-[#1F1F1F] transition-colors shrink-0 cursor-pointer"
        >
          <Plus className="w-5 h-5 stroke-[2]" />
        </button>

        {/* Textarea tự giãn chiều cao ở giữa, ẩn thanh cuộn nếu dưới 200px */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={files.length > 0 ? 'Nhập câu hỏi về tệp hoặc bấm gửi...' : placeholder}
          rows={1}
          autoFocus={autoFocus}
          disabled={isLoading}
          className="flex-1 py-1.5 px-2 text-sm md:text-[15px] text-[#1F1F1F] placeholder-[#6B6B6B]/80 bg-transparent resize-none focus:outline-none leading-relaxed transition-all"
          style={{
            minHeight: '26px',
            maxHeight: '200px',
            overflowY: isOverMaxHeight ? 'auto' : 'hidden',
          }}
        />

        {/* Nút gửi tròn bên phải */}
        <button
          type="button"
          onClick={() => canSend && onSend()}
          disabled={!canSend}
          title="Gửi tin nhắn"
          aria-label="Gửi tin nhắn"
          className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-150 ${
            canSend
              ? 'bg-[#1F1F1F] hover:bg-black text-white cursor-pointer shadow-xs active:scale-95'
              : 'bg-[#71717A] text-white/90 cursor-not-allowed opacity-90'
          }`}
        >
          <ArrowUp className="w-4 h-4 stroke-[2.5]" />
        </button>
      </div>

      {/* Dòng lưu ý nhỏ, màu xám, căn giữa bên dưới ô nhập */}
      <p className="text-center text-[11px] text-[#8E8E93] mt-3 font-normal select-none">
        Trợ lý AI có thể mắc lỗi. Hãy kiểm tra lại thông tin quan trọng.
      </p>
    </div>
  );
};
