import React, { useRef, useEffect } from 'react';
import { ArrowUp, Plus } from 'lucide-react';

interface ComposerProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: () => void;
  isLoading?: boolean;
  onAttachClick?: () => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  input,
  onInputChange,
  onSend,
  isLoading = false,
  onAttachClick,
  placeholder = 'Bạn muốn tìm hiểu điều gì?',
  className = '',
  autoFocus = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Tự động giãn chiều cao theo nội dung
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const nextHeight = Math.min(el.scrollHeight, 180);
    el.style.height = `${Math.max(nextHeight, 28)}px`;
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && input.trim()) {
        onSend();
      }
    }
  };

  const canSend = input.trim().length > 0 && !isLoading;

  return (
    <div className={`w-full max-w-[1100px] mx-auto px-4 ${className}`}>
      {/* Khung ô nhập liệu dạng viên thuốc (border-radius ~32px) */}
      <div className="relative flex items-end gap-2 bg-white border border-[#E5E7EB] hover:border-[#D1D5DB] focus-within:border-[#9CA3AF] rounded-[32px] p-2 pl-3.5 shadow-xs transition-all">
        {/* Nút '+' bên trái (đính kèm tệp) */}
        <button
          type="button"
          onClick={onAttachClick}
          title="Đính kèm tệp / Quét bảng điểm, chứng chỉ"
          aria-label="Đính kèm tệp"
          className="p-2 rounded-full text-[#6B6B6B] hover:text-[#1F1F1F] hover:bg-[#F3F4F6] transition-colors shrink-0 mb-0.5"
        >
          <Plus className="w-5 h-5 stroke-[2.2]" />
        </button>

        {/* Textarea tự giãn chiều cao ở giữa */}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          autoFocus={autoFocus}
          disabled={isLoading}
          className="flex-1 max-h-[180px] py-2 px-1 text-sm md:text-base text-[#1F1F1F] placeholder-[#9CA3AF] bg-transparent resize-none focus:outline-none leading-relaxed"
          style={{ minHeight: '28px' }}
        />

        {/* Nút gửi tròn bên phải */}
        <button
          type="button"
          onClick={() => canSend && onSend()}
          disabled={!canSend}
          title="Gửi tin nhắn"
          aria-label="Gửi tin nhắn"
          className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 mb-0.5 transition-all duration-200 ${
            canSend
              ? 'bg-[#1F1F1F] hover:bg-black text-white cursor-pointer shadow-xs active:scale-95'
              : 'bg-[#ECECF1] text-[#A1A1AA] cursor-not-allowed'
          }`}
        >
          <ArrowUp className="w-5 h-5 stroke-[2.4]" />
        </button>
      </div>

      {/* Dòng lưu ý nhỏ, màu xám, căn giữa bên dưới ô nhập */}
      <p className="text-center text-[11px] md:text-xs text-[#8E8E93] mt-2.5 px-4 font-normal select-none">
        Trợ lý AI có thể mắc lỗi. Hãy kiểm tra lại thông tin quan trọng.
      </p>
    </div>
  );
};
