import React, { useState } from 'react';
import { SidebarHeader } from './SidebarHeader';
import { NewChatButton } from './NewChatButton';
import { ProjectSection } from './ProjectSection';
import { ChatHistoryList } from './ChatHistoryList';
import { UserMenu } from './UserMenu';
import type { ChatSession, UserProfile } from '../../types';

interface SidebarProps {
  isOpen: boolean;
  onToggleSidebar: () => void;
  onCloseMobileSidebar: () => void;
  sessions: ChatSession[];
  activeSessionId: number | null;
  onSelectSession: (id: number) => void;
  onRenameSession?: (id: number, newTitle: string) => Promise<void>;
  onDeleteSession?: (id: number) => Promise<void>;
  onNewChat: () => void;
  user: UserProfile | null;
  onLogout: () => void;
  onOpenLoginModal: () => void;
  onOpenProfileModal?: () => void;
  onExploreProjects?: () => void;
  isLoadingSessions?: boolean;
  errorSessions?: string | null;
  onRetrySessions?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggleSidebar,
  onCloseMobileSidebar,
  sessions,
  activeSessionId,
  onSelectSession,
  onRenameSession,
  onDeleteSession,
  onNewChat,
  user,
  onLogout,
  onOpenLoginModal,
  onOpenProfileModal,
  onExploreProjects,
  isLoadingSessions = false,
  errorSessions = null,
  onRetrySessions,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  return (
    <>
      {/* Mobile Backdrop overlay */}
      {isOpen && (
        <div
          onClick={onCloseMobileSidebar}
          className="fixed inset-0 bg-slate-900/50 z-40 md:hidden backdrop-blur-2xs transition-opacity"
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container (~280px, collapsible, mobile slide-out drawer) */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col h-full bg-[#F8FAFC] dark:bg-[#162338] border-r border-slate-200/90 dark:border-slate-800 transition-all duration-300 ease-in-out select-none shadow-xl md:shadow-none ${
          isOpen
            ? 'w-[280px] translate-x-0'
            : '-translate-x-full md:-ml-[280px] md:w-[280px]'
        }`}
      >
        {/* 1. Header with Logo & search */}
        <SidebarHeader
          onToggleSidebar={onToggleSidebar}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        {/* 2. Cuộc trò chuyện mới (+ New Chat Button) */}
        <NewChatButton
          onClick={() => {
            onNewChat();
            if (typeof window !== 'undefined' && window.innerWidth < 768) {
              onCloseMobileSidebar();
            }
          }}
        />

        {/* 3. Section khám phá dự án */}
        <ProjectSection onExploreProjects={onExploreProjects} />

        {/* 4. Nhóm lịch sử cuộc trò chuyện (Hôm nay / Hôm qua / 7 ngày trước / Cũ hơn) */}
        <ChatHistoryList
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={(id) => {
            onSelectSession(id);
            if (typeof window !== 'undefined' && window.innerWidth < 768) {
              onCloseMobileSidebar();
            }
          }}
          onRenameSession={onRenameSession}
          onDeleteSession={onDeleteSession}
          searchQuery={searchQuery}
          isLoading={isLoadingSessions}
          error={errorSessions}
          onRetry={onRetrySessions}
        />

        {/* 5. Footer thông tin người dùng */}
        <UserMenu
          user={user}
          onLogout={onLogout}
          onOpenLoginModal={onOpenLoginModal}
          onOpenProfileModal={onOpenProfileModal}
        />
      </aside>
    </>
  );
};
