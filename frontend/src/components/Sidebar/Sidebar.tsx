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
  onNewChat: () => void;
  user: UserProfile | null;
  onLogout: () => void;
  onOpenLoginModal: () => void;
  onOpenProfileModal?: () => void;
  onExploreProjects?: () => void;
  isLoadingSessions?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggleSidebar,
  onCloseMobileSidebar,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  user,
  onLogout,
  onOpenLoginModal,
  onOpenProfileModal,
  onExploreProjects,
  isLoadingSessions = false,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);

  const handleToggleSearch = () => {
    setIsSearchOpen((prev) => {
      if (prev) setSearchQuery('');
      return !prev;
    });
  };

  return (
    <>
      {/* Mobile Backdrop overlay */}
      {isOpen && (
        <div
          onClick={onCloseMobileSidebar}
          className="fixed inset-0 bg-black/30 z-40 md:hidden backdrop-blur-2xs transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col h-full bg-[#F7F7F8] border-r border-[#E5E5E5] transition-all duration-300 ease-in-out select-none ${
          isOpen
            ? 'w-[320px] sm:w-[360px] md:w-[390px] translate-x-0'
            : '-translate-x-full md:-ml-[390px] md:w-[390px]'
        }`}
      >
        {/* 1. Header */}
        <SidebarHeader
          onToggleSidebar={onToggleSidebar}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          isSearchOpen={isSearchOpen}
          onToggleSearch={handleToggleSearch}
        />

        {/* 2. Cuộc trò chuyện mới */}
        <NewChatButton
          onClick={() => {
            onNewChat();
            if (window.innerWidth < 768) {
              onCloseMobileSidebar();
            }
          }}
        />

        {/* 3 & 4. Khám phá dự án & Nhóm Dự án */}
        <ProjectSection onExploreProjects={onExploreProjects} />

        {/* 5. Nhóm lịch sử cuộc trò chuyện (Hôm nay / Hôm qua / 7 ngày trước / Cũ hơn) */}
        <ChatHistoryList
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={(id) => {
            onSelectSession(id);
            if (window.innerWidth < 768) {
              onCloseMobileSidebar();
            }
          }}
          searchQuery={searchQuery}
          isLoading={isLoadingSessions}
        />

        {/* 6. Footer thông tin người dùng */}
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
