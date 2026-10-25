import React, { useRef, useEffect, useState, useCallback } from 'react';
import { ArrowDown } from 'lucide-react';
import { MessageItem } from './MessageItem';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  onRegenerate?: () => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  onRegenerate,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = useState(false);

  // Auto scroll to bottom when messages or loading changes, if user is close to bottom
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (typeof bottomRef.current?.scrollIntoView === 'function') {
      bottomRef.current.scrollIntoView({ behavior });
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  // Track scroll position to show/hide scroll-to-bottom button
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBottom(distanceToBottom > 160);
  };

  // Rule LỖI 1: Nếu tin nhắn bot placeholder (đang stream hoặc rỗng) đã tồn tại thì KHÔNG render TypingIndicator riêng
  const hasActivePlaceholder = messages.some(
    (m) => m.role === 'assistant' && (m.isStreaming || (!m.content && !m.error))
  );

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto px-4 py-6 bg-[#F4F6F8] dark:bg-[#0F1B2D] relative"
    >
      {/* Khu hội thoại căn giữa, rộng tối đa ~760px */}
      <div className="max-w-[760px] mx-auto w-full pb-6">
        {messages.map((message) => (
          <MessageItem
            key={message.id}
            message={message}
            onRegenerate={onRegenerate}
          />
        ))}

        {isLoading && !hasActivePlaceholder && (
          <MessageItem
            message={{
              id: 'temp-loading',
              role: 'assistant',
              content: '',
              isStreaming: true,
            }}
          />
        )}

        <div ref={bottomRef} className="h-4" />
      </div>

      {/* Nút mũi tên cuộn xuống khi người dùng đang xem tin cũ */}
      {showScrollBottom && (
        <button
          type="button"
          onClick={() => scrollToBottom('smooth')}
          title="Cuộn xuống tin mới nhất"
          aria-label="Cuộn xuống tin mới nhất"
          className="fixed bottom-24 right-6 sm:right-10 z-20 p-2.5 rounded-full bg-white dark:bg-[#162338] text-[#1565C0] dark:text-[#4D8FE0] shadow-lg border border-slate-200 dark:border-slate-700 hover:bg-[#E3F0FC] dark:hover:bg-slate-700 transition-all duration-200 animate-fade-in cursor-pointer"
        >
          <ArrowDown className="w-4 h-4 stroke-[2.2]" />
        </button>
      )}
    </div>
  );
};
