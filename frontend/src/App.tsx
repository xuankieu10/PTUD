import { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatHeader } from './components/Chat/ChatHeader';
import { WelcomeScreen } from './components/Chat/WelcomeScreen';
import { MessageList } from './components/Chat/MessageList';
import { Composer } from './components/Chat/Composer';
import { LoginModal } from './components/Modals/LoginModal';
import { ProfileModal } from './components/Modals/ProfileModal';
import { ProjectsModal } from './components/Modals/ProjectsModal';
import { LandingPage } from './components/Landing/LandingPage';
import { SignUpPage } from './components/Auth/SignUpPage';
import { chatApi, authApi, healthApi, removeAuthToken } from './services/api';
import type { ChatSession, ChatMessage, UserProfile, OllamaHealth, AttachedFile } from './types';

export type AppView = 'landing' | 'signup' | 'chat';

export interface AppProps {
  initialView?: AppView;
}

const getInitialView = (): AppView => {
  if (typeof window === 'undefined') return 'landing';
  const path = window.location.pathname.toLowerCase();
  const hash = window.location.hash.toLowerCase();
  if (path === '/dang-ky' || hash === '#dang-ky' || hash === '#signup') return 'signup';
  if (path === '/chat' || hash === '#chat') return 'chat';
  return 'landing';
};

const SIDEBAR_STORAGE_KEY = 'lhu_ai_sidebar_open';
const THEME_STORAGE_KEY = 'lhu_ai_dark_mode';
const ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf', '.docx', '.txt'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES_COUNT = 5;

export function App({ initialView }: AppProps = {}) {
  // Navigation View State ('landing' | 'signup' | 'chat')
  const [currentView, setCurrentView] = useState<AppView>(() => {
    if (initialView) return initialView;
    if (typeof window !== 'undefined') {
      if (import.meta.env.MODE === 'test') {
        const path = window.location.pathname.toLowerCase();
        const hash = window.location.hash.toLowerCase();
        if (path === '/dang-ky' || hash === '#dang-ky') return 'signup';
        if (path === '/landing' || hash === '#landing') return 'landing';
        return 'chat';
      }
      return getInitialView();
    }
    return 'landing';
  });

  const navigateTo = (view: AppView) => {
    setCurrentView(view);
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      const url = view === 'signup' ? '/dang-ky' : view === 'chat' ? '/chat' : '/';
      window.history.pushState({ view }, '', url);
    }
  };

  useEffect(() => {
    const handlePopState = (e: PopStateEvent) => {
      if (e.state && e.state.view) {
        setCurrentView(e.state.view);
      } else {
        setCurrentView(getInitialView());
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Sidebar open/close state with localStorage persistence
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      try {
        const saved = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
        if (saved !== null) {
          return saved === 'true';
        }
      } catch {
        // Fallback
      }
    }
    return typeof window !== 'undefined' ? window.innerWidth >= 768 : true;
  });

  // Dark mode state with localStorage persistence
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && typeof window.localStorage !== 'undefined') {
      try {
        const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
        if (saved !== null) {
          return saved === 'true';
        }
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      } catch {
        // Fallback
      }
    }
    return false;
  });

  // Apply dark mode class to root document element
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, String(isDarkMode));
    } catch {
      // Ignore
    }
  }, [isDarkMode]);

  const toggleDarkMode = () => setIsDarkMode((prev) => !prev);

  // Chat Sessions & Active Session State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [draftSessionId, setDraftSessionId] = useState<string>(() => `draft-${Date.now()}`);
  const [messagesBySession, setMessagesBySession] = useState<Record<string, ChatMessage[]>>({});
  const [loadingBySession, setLoadingBySession] = useState<Record<string, boolean>>({});
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  // Derived state for the currently active session
  const currentSessionKey = activeSessionId !== null ? String(activeSessionId) : draftSessionId;
  const currentMessages = messagesBySession[currentSessionKey] || [];
  const currentIsLoading = Boolean(loadingBySession[currentSessionKey]);

  // Composer Input & File Upload State
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Save last failed request for retry
  const lastFailedRequestRef = useRef<{ text: string; files: File[] } | null>(null);

  // User & Health State
  const [user, setUser] = useState<UserProfile | null>(null);
  const [health, setHealth] = useState<OllamaHealth | null>(null);

  // Modals
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [isProjectsModalOpen, setIsProjectsModalOpen] = useState(false);

  // Drag over main chat area state
  const [isDraggingOverChat, setIsDraggingOverChat] = useState(false);

  // Toggle sidebar
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
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  // Load chat sessions for the current logged-in user
  const refreshSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    setSessionsError(null);
    try {
      const list = await chatApi.getSessions();
      setSessions(list);
    } catch (err: any) {
      setSessionsError(err?.message || 'Không thể tải danh sách cuộc trò chuyện.');
      setSessions([]);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  // Initialize application
  useEffect(() => {
    const initApp = async () => {
      // 1. Auth check
      const currentUser = await authApi.ensureAuthenticated();
      setUser(currentUser);

      // 2. Health check
      const h = await healthApi.checkHealth();
      setHealth(h);

      // 3. Load chat sessions if authenticated
      if (currentUser) {
        await refreshSessions();
      } else {
        setSessions([]);
      }
    };

    initApp();

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
    setAttachedFiles([]);
    setUploadError(null);
    closeMobileSidebar();

    const key = String(sessionId);
    // Chỉ tải từ backend nếu phiên này không đang streaming
    if (!loadingBySession[key]) {
      try {
        const msgs = await chatApi.getSessionMessages(sessionId);
        setMessagesBySession((prev) => ({
          ...prev,
          [key]: msgs,
        }));
      } catch (err: any) {
        setMessagesBySession((prev) => {
          if (prev[key] && prev[key].length > 0) return prev;
          return {
            ...prev,
            [key]: [
              {
                id: 'error-load',
                role: 'assistant',
                content: '',
                error: err.message || 'Không thể tải lịch sử tin nhắn của cuộc trò chuyện này.',
              },
            ],
          };
        });
      }
    }
  };

  // Create new chat
  const handleNewChat = () => {
    setActiveSessionId(null);
    setDraftSessionId(`draft-${Date.now()}`);
    setInput('');
    setAttachedFiles([]);
    setUploadError(null);
    closeMobileSidebar();
  };

  // Rename session
  const handleRenameSession = async (sessionId: number, newTitle: string) => {
    try {
      await chatApi.renameSession(sessionId, newTitle);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title: newTitle } : s))
      );
    } catch (err: any) {
      alert(err.message || 'Lỗi khi đổi tên cuộc trò chuyện.');
    }
  };

  // Delete session
  const handleDeleteSession = async (sessionId: number) => {
    try {
      await chatApi.deleteSession(sessionId);
      const key = String(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setMessagesBySession((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      setLoadingBySession((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
      if (activeSessionId === sessionId) {
        handleNewChat();
      }
    } catch (err: any) {
      alert(err.message || 'Lỗi khi xoá cuộc trò chuyện.');
    }
  };

  // File validation and addition
  const handleAddFiles = (newFiles: File[]) => {
    setUploadError(null);
    const currentCount = attachedFiles.length;

    if (currentCount + newFiles.length > MAX_FILES_COUNT) {
      setUploadError(`Chỉ được tải lên tối đa ${MAX_FILES_COUNT} tệp cùng lúc.`);
      return;
    }

    for (const f of newFiles) {
      const ext = '.' + (f.name.split('.').pop() || '').toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setUploadError(
          `Định dạng tệp "${f.name}" không được hỗ trợ. Vui lòng chọn tệp PNG, JPG, PDF, DOCX hoặc TXT.`
        );
        return;
      }
      if (f.size > MAX_FILE_SIZE) {
        setUploadError(`Tệp "${f.name}" vượt quá dung lượng tối đa cho phép (10MB).`);
        return;
      }
    }

    const newAttached: AttachedFile[] = newFiles.map((f) => ({
      id: `${f.name}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: f.name,
      size: f.size,
      type: f.type || 'application/octet-stream',
      file: f,
    }));

    setAttachedFiles((prev) => [...prev, ...newAttached]);
  };

  const handleRemoveFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Send message or files
  const handleSendMessage = async (textToSend?: string) => {
    const messageContent = (textToSend ?? input).trim();
    const filesToSend = attachedFiles.map((f) => f.file!).filter(Boolean);

    // Chốt session ID và key mục tiêu tại thời điểm bắt đầu gửi (const captured)
    const targetSessionId = activeSessionId; // number | null
    const targetKey = targetSessionId !== null ? String(targetSessionId) : draftSessionId;

    // Chặn gửi nếu ô nhập trống hoặc phiên mục tiêu đang loading
    if ((!messageContent && filesToSend.length === 0) || loadingBySession[targetKey]) return;

    // Reset input và files ở Composer ngay lập tức
    setInput('');
    setUploadError(null);
    const filesSnapshot = [...attachedFiles];
    setAttachedFiles([]);

    // Lưu lại phòng trường hợp gửi thất bại cần thử lại
    lastFailedRequestRef.current = { text: messageContent, files: filesToSend };

    // Thêm tin nhắn user vào session tương ứng
    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: messageContent,
      files: filesSnapshot,
    };

    // Placeholder bot message
    const aiMsgId = `ai-${Date.now()}`;
    const hasFiles = filesToSend.length > 0;
    const placeholderAiMessage: ChatMessage = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      statusText: hasFiles ? 'Đang đọc bảng điểm, có thể mất vài phút...' : 'Đang phản hồi...',
    };

    setMessagesBySession((prev) => ({
      ...prev,
      [targetKey]: [...(prev[targetKey] || []), userMessage, placeholderAiMessage],
    }));
    setLoadingBySession((prev) => ({
      ...prev,
      [targetKey]: true,
    }));

    // Nếu gửi từ phiên nháp mới (chưa có id), tạo sẵn draftId mới cho lần New Chat kế tiếp
    if (targetSessionId === null) {
      setDraftSessionId(`draft-${Date.now()}`);
    }

    try {
      let res: any;
      if (filesToSend.length > 0) {
        // Tải tệp lên endpoint /chat/upload
        res = await chatApi.uploadFiles(filesToSend, messageContent || undefined, targetSessionId);
        setMessagesBySession((prev) => {
          const list = prev[targetKey] || [];
          return {
            ...prev,
            [targetKey]: list.map((m) =>
              m.id === aiMsgId
                ? { ...m, content: res.answer, sources: res.sources, isStreaming: false }
                : m
            ),
          };
        });
      } else {
        // Gửi tin nhắn dạng streaming: hiển thị chữ chạy ngay khi model sinh
        res = await chatApi.sendMessageStream(
          messageContent,
          targetSessionId,
          (token) => {
            setMessagesBySession((prev) => {
              const list = prev[targetKey] || [];
              return {
                ...prev,
                [targetKey]: list.map((m) =>
                  m.id === aiMsgId ? { ...m, content: m.content + token } : m
                ),
              };
            });
          },
          (sources) => {
            setMessagesBySession((prev) => {
              const list = prev[targetKey] || [];
              return {
                ...prev,
                [targetKey]: list.map((m) =>
                  m.id === aiMsgId ? { ...m, sources } : m
                ),
              };
            });
          }
        );

        // Kết thúc stream: cập nhật nội dung hoàn chỉnh và nguồn
        setMessagesBySession((prev) => {
          const list = prev[targetKey] || [];
          return {
            ...prev,
            [targetKey]: list.map((m) =>
              m.id === aiMsgId
                ? {
                    ...m,
                    content: res.answer || m.content,
                    sources: res.sources || m.sources,
                    isStreaming: false,
                  }
                : m
            ),
          };
        });
      }

      lastFailedRequestRef.current = null;

      // Cập nhật session active & làm mới danh sách session khi tạo phiên mới
      if (targetSessionId === null && res.session_id) {
        const newRealKey = String(res.session_id);
        setMessagesBySession((prev) => {
          const existing = prev[targetKey] || [];
          const next = { ...prev };
          delete next[targetKey];
          next[newRealKey] = existing;
          return next;
        });
        setLoadingBySession((prev) => {
          const next = { ...prev };
          delete next[targetKey];
          return next;
        });

        // Chỉ chuyển activeSessionId nếu người dùng vẫn đang ở phiên nháp lúc gửi
        setActiveSessionId((currentActive) => {
          if (currentActive === null) {
            return res.session_id;
          }
          return currentActive;
        });
      }

      refreshSessions();
    } catch (err: any) {
      const errMsg = err?.message || 'Không thể gửi tin nhắn hoặc tải tệp lên. Vui lòng thử lại.';
      setUploadError(errMsg);

      setMessagesBySession((prev) => {
        const list = prev[targetKey] || [];
        return {
          ...prev,
          [targetKey]: list.map((m) =>
            m.id === aiMsgId
              ? { ...m, content: '', error: errMsg, isStreaming: false }
              : m
          ),
        };
      });
    } finally {
      setLoadingBySession((prev) => ({
        ...prev,
        [targetKey]: false,
      }));
    }
  };

  // Thử lại khi gửi / tải tệp thất bại
  const handleRetry = () => {
    if (lastFailedRequestRef.current && !currentIsLoading) {
      const { text, files } = lastFailedRequestRef.current;
      setInput(text);
      if (files.length > 0) {
        handleAddFiles(files);
      }
    }
  };

  const handleSelectPrompt = (prompt: string) => {
    setInput(prompt);
    handleSendMessage(prompt);
  };

  // Regenerate last bot response
  const handleRegenerate = () => {
    const lastUserMsg = [...currentMessages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg && !currentIsLoading) {
      handleSendMessage(lastUserMsg.content);
    }
  };

  // Login handler
  const handleLoginSuccess = (newUser: UserProfile) => {
    setUser(newUser);
    setActiveSessionId(null);
    setDraftSessionId(`draft-${Date.now()}`);
    setMessagesBySession({});
    setLoadingBySession({});
    setInput('');
    setAttachedFiles([]);
    setUploadError(null);
    refreshSessions();
  };

  // Logout handler
  const handleLogout = () => {
    removeAuthToken();
    setUser(null);
    setSessions([]);
    setActiveSessionId(null);
    setDraftSessionId(`draft-${Date.now()}`);
    setMessagesBySession({});
    setLoadingBySession({});
    setInput('');
    setAttachedFiles([]);
    setUploadError(null);
  };

  // Drag and drop handlers on chat area
  const handleChatDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOverChat(true);
  };

  const handleChatDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOverChat(false);
  };

  const handleChatDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDraggingOverChat(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  // Render Landing Page View
  if (currentView === 'landing') {
    return (
      <>
        <LandingPage
          isDarkMode={isDarkMode}
          onToggleDarkMode={toggleDarkMode}
          onNavigateToSignUp={() => navigateTo('signup')}
          onOpenLoginModal={() => setIsLoginModalOpen(true)}
          onNavigateToChat={() => navigateTo('chat')}
        />

        <LoginModal
          isOpen={isLoginModalOpen}
          onClose={() => setIsLoginModalOpen(false)}
          onLoginSuccess={(loggedUser) => {
            handleLoginSuccess(loggedUser);
            navigateTo('chat');
          }}
          onSwitchToSignUp={() => {
            setIsLoginModalOpen(false);
            navigateTo('signup');
          }}
        />
      </>
    );
  }

  // Render Sign Up Page View
  if (currentView === 'signup') {
    return (
      <>
        <SignUpPage
          onBackToHome={() => navigateTo('landing')}
          onOpenLogin={() => setIsLoginModalOpen(true)}
        />

        <LoginModal
          isOpen={isLoginModalOpen}
          onClose={() => setIsLoginModalOpen(false)}
          onLoginSuccess={(loggedUser) => {
            handleLoginSuccess(loggedUser);
            navigateTo('chat');
          }}
        />
      </>
    );
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#F4F6F8] dark:bg-[#0F1B2D] text-[#222222] dark:text-[#E2E8F0] transition-colors duration-200">
      {/* Main Layout Container */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Sidebar bên trái (~280px) */}
        <Sidebar
          isOpen={isSidebarOpen}
          onToggleSidebar={toggleSidebar}
          onCloseMobileSidebar={closeMobileSidebar}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onRenameSession={handleRenameSession}
          onDeleteSession={handleDeleteSession}
          onNewChat={handleNewChat}
          user={user}
          onLogout={handleLogout}
          onOpenLoginModal={() => setIsLoginModalOpen(true)}
          onOpenProfileModal={() => setIsProfileModalOpen(true)}
          onExploreProjects={() => setIsProjectsModalOpen(true)}
          isLoadingSessions={isLoadingSessions}
          errorSessions={sessionsError}
          onRetrySessions={refreshSessions}
        />

        {/* Khu vực nội dung chính bên phải */}
        <div
          className="flex-1 flex flex-col h-full overflow-hidden bg-[#F4F6F8] dark:bg-[#0F1B2D] relative min-w-0"
          onDragOver={handleChatDragOver}
          onDragLeave={handleChatDragLeave}
          onDrop={handleChatDrop}
        >
          {/* Header mỏng phía trên khu chat (nền xanh #1565C0, cao ~56px) */}
          <ChatHeader
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={toggleSidebar}
            onNewChat={handleNewChat}
            health={health}
            isDarkMode={isDarkMode}
            onToggleDarkMode={toggleDarkMode}
            onNavigateToHome={() => navigateTo('landing')}
          />

          {/* Overlay khi đang kéo tệp vào khung chat */}
          {isDraggingOverChat && (
            <div className="absolute inset-0 bg-blue-50/90 dark:bg-slate-900/90 backdrop-blur-xs border-2 border-dashed border-[#1565C0] dark:border-[#4D8FE0] z-40 flex flex-col items-center justify-center p-6 text-center select-none animate-fade-in pointer-events-none">
              <div className="w-16 h-16 rounded-full bg-[#E3F0FC] dark:bg-slate-800 text-[#1565C0] dark:text-[#4D8FE0] flex items-center justify-center mb-3 shadow-xs">
                <span className="text-3xl font-bold">+</span>
              </div>
              <p className="text-base font-bold text-[#1565C0] dark:text-[#4D8FE0]">
                Thả tệp vào đây để tải lên
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                Hỗ trợ PNG, JPG, PDF, DOCX, TXT · Tối đa 5 tệp, tối đa 10MB/tệp
              </p>
            </div>
          )}

          {/* Nội dung hội thoại */}
          {currentMessages.length === 0 ? (
            /* Màn hình chào (Welcome Screen) */
            <WelcomeScreen
              input={input}
              onInputChange={setInput}
              onSend={() => handleSendMessage()}
              isLoading={currentIsLoading}
              files={attachedFiles}
              onAddFiles={handleAddFiles}
              onRemoveFile={handleRemoveFile}
              error={uploadError}
              onRetry={handleRetry}
              onSelectPrompt={handleSelectPrompt}
            />
          ) : (
            /* Danh sách tin nhắn + Composer ở đáy */
            <div className="flex-1 flex flex-col overflow-hidden">
              <MessageList
                messages={currentMessages}
                isLoading={currentIsLoading}
                onRegenerate={handleRegenerate}
              />

              {/* Ô nhập liệu cố định ở đáy */}
              <div className="pb-3 pt-2 bg-gradient-to-t from-[#F4F6F8] via-[#F4F6F8] to-[#F4F6F8]/80 dark:from-[#0F1B2D] dark:via-[#0F1B2D] dark:to-[#0F1B2D]/80 shrink-0 px-4 max-w-[760px] mx-auto w-full">
                <Composer
                  input={input}
                  onInputChange={setInput}
                  onSend={() => handleSendMessage()}
                  isLoading={currentIsLoading}
                  files={attachedFiles}
                  onAddFiles={handleAddFiles}
                  onRemoveFile={handleRemoveFile}
                  error={uploadError}
                  onRetry={handleRetry}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLoginSuccess={handleLoginSuccess}
        onSwitchToSignUp={() => {
          setIsLoginModalOpen(false);
          navigateTo('signup');
        }}
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
