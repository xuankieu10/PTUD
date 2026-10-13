import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "./App";
import * as apiModule from "./services/api";

describe("LHU AI App Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders guest state when unauthenticated ('Khách' and 'Đăng nhập')", async () => {
    vi.spyOn(apiModule.authApi, 'ensureAuthenticated').mockResolvedValue(null);
    vi.spyOn(apiModule.chatApi, 'getSessions').mockResolvedValue([]);
    vi.spyOn(apiModule.healthApi, 'checkHealth').mockResolvedValue(null);

    render(<App />);

    expect(screen.getByText(/Cuộc trò chuyện mới/i)).toBeInTheDocument();
    expect(screen.getByText(/Đại học Lạc Hồng/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Khách')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Đăng nhập/i })).toBeInTheDocument();
    });
  });

  it("renders user profile and empty chat history when authenticated user has no chats", async () => {
    vi.spyOn(apiModule.authApi, 'ensureAuthenticated').mockResolvedValue({
      id: 2,
      username: 'sv01',
      role: 'student',
      student_code: '20210001',
      full_name: 'Nguyễn Văn A',
      major: 'Công nghệ Thông tin',
    });
    vi.spyOn(apiModule.chatApi, 'getSessions').mockResolvedValue([]);
    vi.spyOn(apiModule.healthApi, 'checkHealth').mockResolvedValue(null);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Nguyễn Văn A/i)).toBeInTheDocument();
      expect(screen.getByText(/Chưa có cuộc trò chuyện nào\./i)).toBeInTheDocument();
    });
  });

  it("renders user chat history with date grouping", async () => {
    const now = new Date().toISOString();
    vi.spyOn(apiModule.authApi, 'ensureAuthenticated').mockResolvedValue({
      id: 10,
      username: 'test01',
      role: 'student',
      student_code: 'T01',
      full_name: 'Sinh Vien Test',
      major: 'Kỹ thuật Phần mềm',
    });
    vi.spyOn(apiModule.chatApi, 'getSessions').mockResolvedValue([
      { id: 101, title: 'Hỏi về điều kiện tốt nghiệp', created_at: now, updated_at: now },
    ]);
    vi.spyOn(apiModule.healthApi, 'checkHealth').mockResolvedValue(null);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Hỏi về điều kiện tốt nghiệp')).toBeInTheDocument();
      expect(screen.getByText('Hôm nay')).toBeInTheDocument();
    });
  });
});
