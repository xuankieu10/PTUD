import React, { useRef, useEffect } from 'react';
import { MessageItem } from './MessageItem';
import type { ChatMessage } from '../../types';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ messages, isLoading }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      {/* Cột tối đa ~800px ở giữa */}
      <div className="max-w-[800px] mx-auto w-full">
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} />
        ))}

        {isLoading && (
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
    </div>
  );
};
