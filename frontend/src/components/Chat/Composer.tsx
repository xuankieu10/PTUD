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
    const nextHeight = Math.min(el.scrollHeight, 160);
    el.style.height = `${Math.max(nextHeight, 26)}px`;
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
    <div className={`w-full mx-auto ${className}`}>
      {/* Khung ô nhập liệu bo tròn dạng viên thuốc (border-radius ~32px) */}
      <div className="relative flex items-center gap-2 bg-white border border-[#E5E7EB] hover:border-[#D1D5DB] focus-within:border-[#BDBDBD] rounded-full px-4 py-2 shadow-2xs transition-all">
        {/* Nút '+' bên trái (đính kèm tệp) */}
        <button
          type="button"
          onClick={onAttachClick}
          title="Đính kèm tệp / Quét bảng điểm, chứng chỉ"
          aria-label="Đính kèm tệp"
          className="p-1 rounded-full text-[#6B6B6B] hover:text-[#1F1F1F] transition-colors shrink-0"
        >
          <Plus className="w-5 h-5 stroke-[2]" />
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
          className="flex-1 max-h-[160px] py-1.5 px-2 text-sm md:text-[15px] text-[#1F1F1F] placeholder-[#6B6B6B]/80 bg-transparent resize-none focus:outline-none leading-relaxed"
          style={{ minHeight: '26px' }}
        />

        {/* Nút gửi tròn bên phải giống hệt ảnh chụp */}
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
