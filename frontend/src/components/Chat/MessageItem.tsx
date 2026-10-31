import React, { useState } from 'react';
import { Copy, Check, ThumbsUp, ThumbsDown, RotateCcw, BookOpen, ExternalLink, AlertCircle } from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';
import { FileCard } from './FileCard';
import { MarkdownRenderer } from '../Common/MarkdownRenderer';
import type { ChatMessage, AttachedFile } from '../../types';

interface MessageItemProps {
  message: ChatMessage;
  onRegenerate?: () => void;
}

// Hàm lọc bỏ các dòng bắt đầu bằng Nguồn:, - Nguồn:, * Nguồn:, Tham khảo:, hoặc URL cs.lhu.edu.vn
function cleanSourceText(content: string): string {
  if (!content) return '';
  const lines = content.split('\n');
  const cleaned: string[] = [];
  const sourcePrefixRegex = /^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo|Tài liệu tham khảo)\s*:/i;
  const urlOnlyRegex = /^\s*https?:\/\/\S+\s*$/i;
  let inSourceBlock = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (sourcePrefixRegex.test(trimmed)) {
      inSourceBlock = true;
      continue;
    }
    if (inSourceBlock) {
      if (urlOnlyRegex.test(trimmed) || trimmed.includes('cs.lhu.edu.vn')) {
        continue;
      }
      if (/^\s*([-*•]|\d+\.)\s+/i.test(trimmed) && /(mục|điều kiện|quy định|thủ tục|căn cứ|qd|qđ)/i.test(trimmed)) {
        continue;
      }
      if (!trimmed) {
        continue;
      }
      inSourceBlock = false;
    }
    if (trimmed.includes('cs.lhu.edu.vn') && urlOnlyRegex.test(trimmed)) {
      continue;
    }
    cleaned.push(line);
  }
  return cleaned.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

export const MessageItem: React.FC<MessageItemProps> = ({ message, onRegenerate }) => {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'like' | 'dislike' | null>(null);
  const [showSources, setShowSources] = useState(false);

  const isUser = message.role === 'user';
  const displayContent = isUser ? message.content : cleanSourceText(message.content);

  const handleCopy = () => {
    navigator.clipboard.writeText(displayContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleLike = () => {
    setFeedback((prev) => (prev === 'like' ? null : 'like'));
  };

  const handleDislike = () => {
    setFeedback((prev) => (prev === 'dislike' ? null : 'dislike'));
  };

  // 1. User Message: Bong bóng bo góc 16px, nền --primary-light, căn phải
  if (isUser) {
    const attachedFiles: AttachedFile[] =
      message.files ||
      (Array.isArray(message.sources)
        ? message.sources
            .filter((s: any) => s.filename || s.name)
            .map((s: any) => ({
              name: s.filename || s.name,
              size: s.size || 0,
              type: s.type || 'file',
            }))
        : []);

    return (
      <div className="flex flex-col items-end mb-6 animate-fade-in max-w-[85%] md:max-w-[78%] ml-auto">
        {/* Thẻ tệp gửi kèm */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 justify-end">
            {attachedFiles.map((file, idx) => (
              <FileCard key={idx} file={file} />
            ))}
          </div>
        )}

        {/* Bong bóng tin nhắn người dùng */}
        {message.content && (
          <div className="bg-[#E3F0FC] dark:bg-[#1E3A5F] text-[#1565C0] dark:text-[#E3F0FC] font-normal text-sm sm:text-[15px] px-4.5 py-3 rounded-[16px] rounded-br-[4px] whitespace-pre-wrap leading-relaxed shadow-2xs border border-blue-200/50 dark:border-blue-700/40">
            {message.content}
          </div>
        )}
      </div>
    );
  }

  // 2. Chatbot Message: Không bong bóng, nền trong suốt, avatar logo tròn nhỏ bên trái
  return (
    <div className="flex items-start gap-3 sm:gap-3.5 mb-7 animate-fade-in group">
      {/* Avatar biểu tượng tròn Khoa CNTT bên trái */}
      <div className="shrink-0 mt-0.5">
        <LhuLogo variant="avatar" size="sm" alt="Khoa Công nghệ Thông tin" />
      </div>

      <div className="flex-1 min-w-0">
        {/* Error message */}
        {message.error && (
          <div className="mb-2 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 rounded-xl text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{message.error}</span>
          </div>
        )}

        {/* Chatbot Content - Hỗ trợ Markdown, code block có sao chép, bảng, danh sách */}
        {displayContent ? (
          <MarkdownRenderer
            content={displayContent}
            className="text-slate-800 dark:text-slate-200"
          />
        ) : (
          /* Hiệu ứng "đang gõ" 3 chấm xanh nhấp nháy khi bot đang trả lời */
          <div className="flex items-center gap-2 py-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#1565C0] dark:bg-[#4D8FE0] animate-blue-dot-1" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#1565C0] dark:bg-[#4D8FE0] animate-blue-dot-2" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#1565C0] dark:bg-[#4D8FE0] animate-blue-dot-3" />
            <span className="text-xs text-slate-400 dark:text-slate-500 ml-1 font-medium select-none">
              {message.statusText || 'Đang phản hồi...'}
            </span>
          </div>
        )}

        {/* Trích dẫn nguồn (Sources) */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-2">
            <button
              type="button"
              onClick={() => setShowSources(!showSources)}
              className="inline-flex items-center gap-1.5 text-xs text-[#1565C0] dark:text-[#4D8FE0] hover:underline py-1 px-2 rounded-lg bg-[#E3F0FC]/70 dark:bg-slate-800 transition cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5 text-[#1565C0] dark:text-[#4D8FE0]" />
              <span>Nguồn tài liệu tham khảo ({message.sources.length})</span>
            </button>

            {showSources && (
              <div className="mt-2 space-y-2 pl-2 border-l-2 border-[#1565C0]/40 dark:border-[#4D8FE0]/40 animate-fade-in">
                {message.sources.map((src, idx) => {
                  const sourceLink = (src as any).url || src.source_url;
                  const sectionName = (src as any).section;
                  return (
                    <div
                      key={idx}
                      className="text-xs bg-white dark:bg-[#162338] p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 shadow-2xs"
                    >
                      <div className="flex items-center justify-between font-semibold text-slate-800 dark:text-slate-100 mb-1">
                        <span className="truncate">
                          {src.title || `Tài liệu tham khảo #${idx + 1}`}
                          {sectionName ? ` - Mục ${sectionName}` : ''}
                        </span>
                        {sourceLink && (
                          <a
                            href={sourceLink}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[#1565C0] dark:text-[#4D8FE0] hover:underline ml-2 inline-flex items-center gap-1 shrink-0"
                          >
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                      {src.snippet && (
                        <p className="text-slate-500 dark:text-slate-400 line-clamp-2 italic text-[11px]">
                          "{src.snippet}..."
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Dưới mỗi câu trả lời: các nút nhỏ (sao chép, thích, không thích, tạo lại) */}
        {displayContent && (
          <div className="mt-3 flex items-center gap-1 text-slate-400 dark:text-slate-500 select-none">
            {/* 1. Nút sao chép */}
            <button
              type="button"
              onClick={handleCopy}
              title={copied ? "Đã sao chép!" : "Sao chép câu trả lời"}
              aria-label="Sao chép câu trả lời"
              className="p-1.5 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors cursor-pointer"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
            </button>

            {/* 2. Nút thích */}
            <button
              type="button"
              onClick={handleLike}
              title="Câu trả lời hữu ích"
              aria-label="Thích câu trả lời"
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                feedback === 'like'
                  ? 'text-[#1565C0] dark:text-[#4D8FE0] bg-blue-50 dark:bg-blue-950/40'
                  : 'hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800'
              }`}
            >
              <ThumbsUp className={`w-3.5 h-3.5 ${feedback === 'like' ? 'fill-current' : ''}`} />
            </button>

            {/* 3. Nút không thích */}
            <button
              type="button"
              onClick={handleDislike}
              title="Câu trả lời chưa tốt"
              aria-label="Không thích câu trả lời"
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                feedback === 'dislike'
                  ? 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40'
                  : 'hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800'
              }`}
            >
              <ThumbsDown className={`w-3.5 h-3.5 ${feedback === 'dislike' ? 'fill-current' : ''}`} />
            </button>

            {/* 4. Nút tạo lại (Regenerate) */}
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                title="Tạo lại câu trả lời"
                aria-label="Tạo lại câu trả lời"
                className="p-1.5 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
