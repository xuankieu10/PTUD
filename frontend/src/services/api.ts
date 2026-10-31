import type {
  ChatMessage,
  ChatSession,
  ChatSendResponse,
  UserProfile,
  AuthLoginResponse,
  OllamaHealth
} from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || '';

const TOKEN_KEY = 'lhu_ai_access_token';
const USER_KEY = 'lhu_ai_current_user';

export const getAuthToken = (): string | null => {
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage.getItem(TOKEN_KEY);
  }
  return null;
};

export const setAuthToken = (token: string): void => {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.setItem(TOKEN_KEY, token);
  }
};

export const removeAuthToken = (): void => {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USER_KEY);
  }
};

export const getStoredUser = (): UserProfile | null => {
  if (typeof window !== 'undefined' && window.localStorage) {
    const data = window.localStorage.getItem(USER_KEY);
    if (!data) return null;
    try {
      return JSON.parse(data);
    } catch {
      return null;
    }
  }
  return null;
};

export const setStoredUser = (user: UserProfile): void => {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
};

const getAuthHeaders = (): HeadersInit => {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const chatApi = {
  // Lấy danh sách hội thoại của người dùng hiện tại
  async getSessions(): Promise<ChatSession[]> {
    const token = getAuthToken();
    if (!token) return [];

    const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      if (res.status === 401) {
        removeAuthToken();
      }
      throw new Error(`Lỗi tải danh sách cuộc trò chuyện (${res.status})`);
    }
    return await res.json();
  },

  // Lấy tin nhắn của 1 session
  async getSessionMessages(sessionId: number): Promise<ChatMessage[]> {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      throw new Error(`Không thể tải tin nhắn (mã lỗi ${res.status})`);
    }
    return await res.json();
  },

  // Gửi tin nhắn
  async sendMessage(message: string, sessionId?: number | null): Promise<ChatSendResponse> {
    const body: { message: string; session_id?: number } = { message };
    if (sessionId) {
      body.session_id = sessionId;
    }

    const res = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const detail = errData?.detail || `Lỗi máy chủ (${res.status})`;
      throw new Error(detail);
    }

    return await res.json();
  },

  // Gửi tin nhắn với SSE streaming (chữ chạy ngay khi model sinh)
  async sendMessageStream(
    message: string,
    sessionId?: number | null,
    onToken?: (token: string) => void,
    onSources?: (sources: any[]) => void,
  ): Promise<ChatSendResponse> {
    const body: { message: string; session_id?: number } = { message };
    if (sessionId) {
      body.session_id = sessionId;
    }

    const res = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      const detail = errData?.detail || `Lỗi máy chủ (${res.status})`;
      throw new Error(detail);
    }

    const reader = res.body?.getReader();
    if (!reader) {
      throw new Error('ReadableStream không được trình duyệt hỗ trợ.');
    }

    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let finalAnswer = '';
    let resSessionId = sessionId || 0;
    let resSources: any[] = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.slice(6);
          try {
            const data = JSON.parse(jsonStr);
            if (data.token) {
              finalAnswer += data.token;
              if (onToken) onToken(data.token);
            }
            if (data.done) {
              if (data.session_id) resSessionId = data.session_id;
              if (data.sources) {
                resSources = data.sources;
                if (onSources) onSources(data.sources);
              }
            }
          } catch {
            // bỏ qua lỗi parse json tạm thời
          }
        }
      }
    }

    return { session_id: resSessionId, answer: finalAnswer, sources: resSources };
  },

  // Tải tệp lên kèm tin nhắn (tối đa 5 tệp, tối đa 10MB)
  async uploadFiles(
    files: File[],
    message?: string,
    sessionId?: number | null
  ): Promise<ChatSendResponse> {
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    if (message) {
      formData.append('message', message);
    }
    if (sessionId) {
      formData.append('session_id', String(sessionId));
    }

    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 190000);

    try {
      const res = await fetch(`${API_BASE_URL}/chat/upload`, {
        method: 'POST',
        headers,
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const detail = errData?.detail || `Lỗi tải tệp lên (${res.status})`;
        throw new Error(detail);
      }

      return await res.json();
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        throw new Error('Quá thời gian xử lý khi đọc bảng điểm (timeout). Vui lòng kiểm tra lại độ rõ nét của ảnh hoặc thử lại sau.');
      }
      throw err;
    }
  },

  // Đổi tên cuộc trò chuyện
  async renameSession(sessionId: number, title: string): Promise<{ success: boolean; title: string }> {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify({ title }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail || 'Không thể đổi tên cuộc trò chuyện');
    }

    return await res.json();
  },

  // Xoá cuộc trò chuyện
  async deleteSession(sessionId: number): Promise<{ success: boolean }> {
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail || 'Không thể xoá cuộc trò chuyện');
    }

    return await res.json();
  },
};

export const authApi = {
  // Đăng nhập
  async login(username: string, password: string): Promise<AuthLoginResponse> {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.detail || 'Tài khoản hoặc mật khẩu không chính xác');
    }

    const data: AuthLoginResponse = await res.json();
    setAuthToken(data.access_token);
    return data;
  },

  // Lấy thông tin user thật từ /auth/me
  async getMe(): Promise<UserProfile> {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      throw new Error('Chưa đăng nhập');
    }

    const userData = await res.json();
    const fullProfile: UserProfile = {
      id: userData.id,
      user_id: userData.user_id || userData.id,
      student_id: userData.student_id ?? null,
      username: userData.username,
      role: userData.role,
      student_code: userData.student_code || userData.username,
      full_name: userData.full_name || userData.username,
      major: userData.major || 'Chưa cập nhật',
      cohort: userData.cohort,
    };

    setStoredUser(fullProfile);
    return fullProfile;
  },

  // Kiểm tra xác thực khi mở ứng dụng (không hard-code mock profile)
  async ensureAuthenticated(): Promise<UserProfile | null> {
    const token = getAuthToken();
    if (token) {
      try {
        return await this.getMe();
      } catch {
        removeAuthToken();
        return null;
      }
    }
    return null;
  },
};

export const healthApi = {
  async checkHealth(): Promise<OllamaHealth | null> {
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`);
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  },
};
