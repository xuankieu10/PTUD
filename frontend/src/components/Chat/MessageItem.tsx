import React, { useState } from 'react';
import { Copy, Check, ExternalLink, BookOpen, AlertCircle } from 'lucide-react';
import { LhuLogo } from '../Common/LhuLogo';
import { FileCard } from './FileCard';
import type { ChatMessage, AttachedFile } from '../../types';

interface MessageItemProps {
  message: ChatMessage;
}

export const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const [copied, setCopied] = useState(false);
  const [showSources, setShowSources] = useState(false);

  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    // Thu thập danh sách tệp đính kèm từ message.files hoặc message.sources
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
      <div className="flex flex-col items-end mb-6 animate-fade-in max-w-[85%] md:max-w-[75%] ml-auto">
        {/* Các thẻ tệp đính kèm gửi kèm */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 justify-end">
            {attachedFiles.map((file, idx) => (
              <FileCard key={idx} file={file} />
            ))}
          </div>
        )}

        {/* Nội dung câu hỏi (nếu có) */}
        {message.content && (
          <div className="bg-[#F4F4F5] text-[#1F1F1F] text-sm md:text-base px-5 py-3.5 rounded-3xl whitespace-pre-wrap leading-relaxed shadow-2xs">
            {message.content}
          </div>
        )}
      </div>
    );
  }

  // AI Message
  return (
    <div className="flex items-start gap-3.5 mb-8 animate-fade-in group">
      {/* AI Avatar */}
      <div className="shrink-0 mt-0.5">
        <LhuLogo size="sm" />
      </div>

      <div className="flex-1 min-w-0">
        {/* Error message */}
        {message.error && (
          <div className="mb-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
            <span>{message.error}</span>
          </div>
        )}

        {/* AI Content - Không bong bóng */}
        <div className="text-sm md:text-base text-[#1F1F1F] leading-relaxed whitespace-pre-wrap selection:bg-[#F5B800]/25">
          {message.content || (
            <div className="flex items-center gap-1.5 py-2">
              <span className="w-2 h-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-[#9CA3AF] animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
        </div>

        {/* Trích dẫn nguồn (Sources) nếu có */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-2">
            <button
              type="button"
              onClick={() => setShowSources(!showSources)}
              className="inline-flex items-center gap-1.5 text-xs text-[#6B6B6B] hover:text-[#1F1F1F] py-1 px-2.5 rounded-lg bg-[#F7F7F8] hover:bg-[#EBECEF] transition-colors cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5 text-[#F5B800]" />
              <span>Nguồn tài liệu ({message.sources.length})</span>
            </button>

            {showSources && (
              <div className="mt-2 space-y-2 pl-2 border-l-2 border-[#E5E5E5] animate-fade-in">
                {message.sources.map((src, idx) => (
                  <div key={idx} className="text-xs bg-[#F9FAFB] p-2.5 rounded-xl border border-gray-100">
                    <div className="flex items-center justify-between font-medium text-[#1F1F1F] mb-1">
                      <span className="truncate">{src.title || `Tài liệu tham khảo #${idx + 1}`}</span>
                      {src.source_url && (
                        <a
                          href={src.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[#6B6B6B] hover:text-[#1F1F1F] ml-2 inline-flex items-center gap-1"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                    {src.snippet && (
                      <p className="text-[#6B6B6B] line-clamp-2 italic text-[11px]">
                        "{src.snippet}..."
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Message action buttons */}
        {message.content && (
          <div className="mt-2 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={handleCopy}
              title="Sao chép câu trả lời"
              className="p-1.5 rounded-lg text-[#9CA3AF] hover:text-[#1F1F1F] hover:bg-[#F3F4F6] transition-colors cursor-pointer"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
