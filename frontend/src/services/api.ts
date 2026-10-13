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
  // Lấy danh sách hội thoại
  async getSessions(): Promise<ChatSession[]> {
    const token = getAuthToken();
    if (!token) return [];

    try {
      const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        if (res.status === 401) {
          removeAuthToken();
        }
        return [];
      }
      return await res.json();
    } catch (e) {
      console.warn('Lỗi kết nối khi lấy danh sách chat:', e);
      return [];
    }
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

  // Lấy thông tin user hiện tại
  async getMe(): Promise<UserProfile> {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: getAuthHeaders(),
    });

    if (!res.ok) {
      throw new Error('Chưa đăng nhập');
    }

    const basicUser = await res.json();

    // Thử truy vấn thêm thông tin chi tiết sinh viên nếu có
    let studentInfo: Partial<UserProfile> = {};
    try {
      const stuRes = await fetch(`${API_BASE_URL}/students/${basicUser.id}/graduation-check`, {
        headers: getAuthHeaders(),
      });
      if (stuRes.ok) {
        const stuData = await stuRes.json();
        if (stuData?.student) {
          studentInfo = {
            student_code: stuData.student.student_code,
            full_name: stuData.student.full_name,
            major: stuData.student.major,
            cohort: stuData.student.cohort,
          };
        }
      }
    } catch {
      // Bỏ qua nếu sinh viên chưa có hồ sơ
    }

    const fullProfile: UserProfile = {
      id: basicUser.id,
      username: basicUser.username,
      role: basicUser.role,
      student_code: studentInfo.student_code || (basicUser.role === 'admin' ? 'AD01' : '123000969'),
      full_name: studentInfo.full_name || (basicUser.role === 'admin' ? 'Quản Trị Viên' : 'Nguyễn Văn A'),
      major: studentInfo.major || 'KCT',
      cohort: studentInfo.cohort,
    };

    setStoredUser(fullProfile);
    return fullProfile;
  },

  // Đăng nhập demo nhanh nếu chưa có token
  async ensureAuthenticated(): Promise<UserProfile | null> {
    const token = getAuthToken();
    if (token) {
      try {
        return await this.getMe();
      } catch {
        removeAuthToken();
      }
    }

    // Thử auto-login bằng tài khoản demo test01 hoặc sv01
    const testAccounts = [
      { username: 'test01', password: 'Test@123' },
      { username: 'sv01', password: '123' },
      { username: 'admin', password: 'change_me' }
    ];

    for (const acc of testAccounts) {
      try {
        await this.login(acc.username, acc.password);
        return await this.getMe();
      } catch {
        // Thử tài khoản tiếp theo
      }
    }

    // Fallback profile nếu backend chưa chạy hoặc chưa có user
    const fallbackUser: UserProfile = {
      id: 1,
      username: '123000969',
      role: 'student',
      student_code: '123000969',
      full_name: 'Nguyễn Văn A',
      major: 'KCT',
    };
    return fallbackUser;
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
