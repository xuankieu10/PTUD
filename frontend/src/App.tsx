import { useState, useEffect, useCallback } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatHeader } from './components/Chat/ChatHeader';
import { WelcomeScreen } from './components/Chat/WelcomeScreen';
import { MessageList } from './components/Chat/MessageList';
import { Composer } from './components/Chat/Composer';
import { AttachModal } from './components/Modals/AttachModal';
import { LoginModal } from './components/Modals/LoginModal';
import { ProfileModal } from './components/Modals/ProfileModal';
import { ProjectsModal } from './components/Modals/ProjectsModal';
import { chatApi, authApi, healthApi } from './services/api';
import type { ChatSession, ChatMessage, UserProfile, OllamaHealth } from './types';

const SIDEBAR_STORAGE_KEY = 'lhu_ai_sidebar_open';

export function App() {
  // Sidebar open/close state with localStorage persistence
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      try {
        const saved = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
        if (saved !== null) {
          return saved === 'true';
        }
      } catch {
        // Fallback if localStorage is restricted
      }
    }
    return typeof window !== 'undefined' ? window.innerWidth >= 768 : true;
  });

  // Chat Sessions & Active Session State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Composer Input State
  const [input, setInput] = useState('');

  // User & Health State
  const [user, setUser] = useState<UserProfile | null>(null);
  const [health, setHealth] = useState<OllamaHealth | null>(null);

  // Modals
  const [isAttachModalOpen, setIsAttachModalOpen] = useState(false);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [isProjectsModalOpen, setIsProjectsModalOpen] = useState(false);

  // Save sidebar preference
  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
        try {
          window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
        } catch {
          // Ignore
        }
      }
      return next;
    });
  };

  const closeMobileSidebar = () => {
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  // Load User & Sessions on mount
  const refreshSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const list = await chatApi.getSessions();
      setSessions(list);
    } catch (err) {
      console.warn('Lỗi tải danh sách session:', err);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    const initApp = async () => {
      // 1. Auth check
      const currentUser = await authApi.ensureAuthenticated();
      setUser(currentUser);

      // 2. Health check
      const h = await healthApi.checkHealth();
      setHealth(h);

      // 3. Load chat sessions
      await refreshSessions();
    };

    initApp();

    // Check health periodically
    const healthInterval = setInterval(async () => {
      const h = await healthApi.checkHealth();
      setHealth(h);
    }, 30000);

    return () => clearInterval(healthInterval);
  }, [refreshSessions]);

  // Load messages when selecting a session
  const handleSelectSession = async (sessionId: number) => {
    setActiveSessionId(sessionId);
    setInput('');
    try {
      const msgs = await chatApi.getSessionMessages(sessionId);
      setMessages(msgs);
    } catch (err: any) {
      setMessages([
        {
          id: 'error-load',
          role: 'assistant',
          content: '',
          error: err.message || 'Không thể tải lịch sử tin nhắn.',
        },
      ]);
    }
  };

  // Create new chat
  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setInput('');
  };

  // Send message handler
  const handleSendMessage = async (textToSend?: string) => {
    const messageContent = (textToSend ?? input).trim();
    if (!messageContent || isSending) return;

    // Reset input
    setInput('');

    // Append user message to UI immediately
    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: messageContent,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      const res = await chatApi.sendMessage(messageContent, activeSessionId);

      // AI response message
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
      };

      setMessages((prev) => [...prev, aiMessage]);

      // If new session was started, update active session ID & refresh sessions list
      if (!activeSessionId && res.session_id) {
        setActiveSessionId(res.session_id);
        refreshSessions();
      }
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: '',
        error:
          err.message ||
          'Không thể kết nối tới trợ lý AI. Vui lòng kiểm tra lại dịch vụ Ollama hoặc backend.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSelectPrompt = (prompt: string) => {
    setInput(prompt);
    handleSendMessage(prompt);
  };

  const handleFileProcessedText = (summaryText: string) => {
    setIsAttachModalOpen(false);
    setInput(summaryText);
  };

  const handleLoginSuccess = (newUser: UserProfile) => {
    setUser(newUser);
    refreshSessions();
  };

  const handleLogout = () => {
    authApi.ensureAuthenticated().then((fallback) => {
      setUser(fallback);
      setSessions([]);
      setActiveSessionId(null);
      setMessages([]);
    });
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-white text-[#1F1F1F]">
      {/* Thanh viền tối mỏng ở mép trên cùng của trang */}
      <div className="h-[2.5px] w-full bg-[#1F1F1F] shrink-0 z-50" />

      {/* Main Layout Container */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Sidebar bên trái */}
        <Sidebar
          isOpen={isSidebarOpen}
          onToggleSidebar={toggleSidebar}
          onCloseMobileSidebar={closeMobileSidebar}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          user={user}
          onLogout={handleLogout}
          onOpenLoginModal={() => setIsLoginModalOpen(true)}
          onOpenProfileModal={() => setIsProfileModalOpen(true)}
          onExploreProjects={() => setIsProjectsModalOpen(true)}
          isLoadingSessions={isLoadingSessions}
        />

        {/* Khu vực nội dung chính bên phải (nền trắng) */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-white relative min-w-0">
          {/* Header */}
          <ChatHeader
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={toggleSidebar}
            onNewChat={handleNewChat}
            health={health}
          />

          {/* Nội dung hội thoại */}
          {messages.length === 0 ? (
            /* Màn hình chào (Welcome Screen) */
            <WelcomeScreen
              input={input}
              onInputChange={setInput}
              onSend={() => handleSendMessage()}
              isLoading={isSending}
              onAttachClick={() => setIsAttachModalOpen(true)}
              onSelectPrompt={handleSelectPrompt}
            />
          ) : (
            /* Khi đã có tin nhắn: Danh sách tin nhắn + Composer ở đáy */
            <div className="flex-1 flex flex-col overflow-hidden">
              <MessageList messages={messages} isLoading={isSending} />

              {/* Ô nhập liệu cố định ở đáy */}
              <div className="pb-3 pt-2 bg-gradient-to-t from-white via-white to-white/80 shrink-0">
                <Composer
                  input={input}
                  onInputChange={setInput}
                  onSend={() => handleSendMessage()}
                  isLoading={isSending}
                  onAttachClick={() => setIsAttachModalOpen(true)}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <AttachModal
        isOpen={isAttachModalOpen}
        onClose={() => setIsAttachModalOpen(false)}
        onFileProcessedText={handleFileProcessedText}
        health={health}
      />

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLoginSuccess={handleLoginSuccess}
      />

      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
        user={user}
      />

      <ProjectsModal
        isOpen={isProjectsModalOpen}
        onClose={() => setIsProjectsModalOpen(false)}
        onSelectProjectPrompt={handleSelectPrompt}
      />
    </div>
  );
}

export default App;
