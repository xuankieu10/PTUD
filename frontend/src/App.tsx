import { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ChatHeader } from './components/Chat/ChatHeader';
import { WelcomeScreen } from './components/Chat/WelcomeScreen';
import { MessageList } from './components/Chat/MessageList';
import { Composer } from './components/Chat/Composer';
import { LoginModal } from './components/Modals/LoginModal';
import { ProfileModal } from './components/Modals/ProfileModal';
import { ProjectsModal } from './components/Modals/ProjectsModal';
import { chatApi, authApi, healthApi, removeAuthToken } from './services/api';
import type { ChatSession, ChatMessage, UserProfile, OllamaHealth, AttachedFile } from './types';

const SIDEBAR_STORAGE_KEY = 'lhu_ai_sidebar_open';
const ALLOWED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.pdf', '.docx', '.txt'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_FILES_COUNT = 5;

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
        // Fallback
      }
    }
    return typeof window !== 'undefined' ? window.innerWidth >= 768 : true;
  });

  // Chat Sessions & Active Session State
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);

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
    if (window.innerWidth < 768) {
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
    try {
      const msgs = await chatApi.getSessionMessages(sessionId);
      setMessages(msgs);
    } catch (err: any) {
      setMessages([
        {
          id: 'error-load',
          role: 'assistant',
          content: '',
          error: err.message || 'Không thể tải lịch sử tin nhắn của cuộc trò chuyện này.',
        },
      ]);
    }
  };

  // Create new chat
  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setInput('');
    setAttachedFiles([]);
    setUploadError(null);
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
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
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

    // Người dùng có thể nhập câu hỏi hoặc để trống nếu có tệp đính kèm
    if ((!messageContent && filesToSend.length === 0) || isSending) return;

    // Reset input và files ở Composer ngay lập tức
    setInput('');
    setUploadError(null);
    const filesSnapshot = [...attachedFiles];
    setAttachedFiles([]);

    // Lưu lại phòng trường hợp gửi thất bại cần thử lại
    lastFailedRequestRef.current = { text: messageContent, files: filesToSend };

    // Thêm tin nhắn user vào danh sách kèm thẻ tệp
    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      role: 'user',
      content: messageContent,
      files: filesSnapshot,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      let res;
      if (filesToSend.length > 0) {
        // Tải tệp lên endpoint /chat/upload
        res = await chatApi.uploadFiles(filesToSend, messageContent || undefined, activeSessionId);
      } else {
        // Gửi tin nhắn thông thường
        res = await chatApi.sendMessage(messageContent, activeSessionId);
      }

      // Tin nhắn phản hồi từ AI
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
      };

      setMessages((prev) => [...prev, aiMessage]);
      lastFailedRequestRef.current = null;

      // Cập nhật session active & làm mới danh sách session
      if (!activeSessionId && res.session_id) {
        setActiveSessionId(res.session_id);
      }
      refreshSessions();
    } catch (err: any) {
      const errMsg = err?.message || 'Không thể gửi tin nhắn hoặc tải tệp lên. Vui lòng thử lại.';
      setUploadError(errMsg);

      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: '',
        error: errMsg,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsSending(false);
    }
  };

  // Thử lại khi gửi / tải tệp thất bại
  const handleRetry = () => {
    if (lastFailedRequestRef.current) {
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

  // Login handler
  const handleLoginSuccess = (newUser: UserProfile) => {
    setUser(newUser);
    // Reset toàn bộ state hội thoại cũ khi đổi người dùng
    setActiveSessionId(null);
    setMessages([]);
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
    setMessages([]);
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
          className="flex-1 flex flex-col h-full overflow-hidden bg-white relative min-w-0"
          onDragOver={handleChatDragOver}
          onDragLeave={handleChatDragLeave}
          onDrop={handleChatDrop}
        >
          {/* Header */}
          <ChatHeader
            isSidebarOpen={isSidebarOpen}
            onToggleSidebar={toggleSidebar}
            onNewChat={handleNewChat}
            health={health}
          />

          {/* Overlay khi đang kéo tệp vào khung chat */}
          {isDraggingOverChat && (
            <div className="absolute inset-0 bg-white/80 backdrop-blur-xs border-2 border-dashed border-[#F5B800] z-40 flex flex-col items-center justify-center p-6 text-center select-none animate-fade-in pointer-events-none">
              <div className="w-16 h-16 rounded-full bg-amber-50 text-[#F5B800] flex items-center justify-center mb-3">
                <span className="text-2xl font-bold">+</span>
              </div>
              <p className="text-base font-semibold text-[#1F1F1F]">
                Thả tệp vào đây để tải lên
              </p>
              <p className="text-xs text-[#6B6B6B] mt-1">
                Hỗ trợ PNG, JPG, PDF, DOCX, TXT · Tối đa 5 tệp, tối đa 10MB/tệp
              </p>
            </div>
          )}

          {/* Nội dung hội thoại */}
          {messages.length === 0 ? (
            /* Màn hình chào (Welcome Screen) */
            <WelcomeScreen
              input={input}
              onInputChange={setInput}
              onSend={() => handleSendMessage()}
              isLoading={isSending}
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
              <MessageList messages={messages} isLoading={isSending} />

              {/* Ô nhập liệu cố định ở đáy */}
              <div className="pb-3 pt-2 bg-gradient-to-t from-white via-white to-white/80 shrink-0 px-4 max-w-4xl mx-auto w-full">
                <Composer
                  input={input}
                  onInputChange={setInput}
                  onSend={() => handleSendMessage()}
                  isLoading={isSending}
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
