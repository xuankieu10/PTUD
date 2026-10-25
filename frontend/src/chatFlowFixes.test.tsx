import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MessageList } from "./components/Chat/MessageList";
import { MessageItem } from "./components/Chat/MessageItem";
import App from "./App";
import * as apiModule from "./services/api";
import type { ChatMessage } from "./types";

describe("Sửa 3 Lỗi Chat Flow & Giao diện", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.spyOn(apiModule.healthApi, 'checkHealth').mockResolvedValue(null);
  });

  // ==========================================
  // TEST LỖI 1: CHỈ HIỆN ĐÚNG 1 CHỈ BÁO "ĐANG PHẢN HỒI..."
  // ==========================================
  describe("Lỗi 1: Chỉ báo Đang phản hồi... (Avatar bot duy nhất)", () => {
    it("chỉ render đúng 1 chỉ báo 'Đang phản hồi...' khi tin nhắn placeholder đang stream và rỗng", () => {
      const messages: ChatMessage[] = [
        { id: "u1", role: "user", content: "Điều kiện tốt nghiệp là gì?" },
        { id: "ai-placeholder", role: "assistant", content: "", isStreaming: true },
      ];

      render(<MessageList messages={messages} isLoading={true} />);

      // Tìm tất cả các đoạn text "Đang phản hồi..."
      const indicators = screen.getAllByText(/Đang phản hồi\.\.\./i);
      expect(indicators).toHaveLength(1);
    });

    it("ẩn 'Đang phản hồi...' và thay thế bằng text khi nhận được token đầu tiên", () => {
      const { rerender } = render(
        <MessageItem
          message={{ id: "ai-1", role: "assistant", content: "", isStreaming: true }}
        />
      );
      expect(screen.getByText(/Đang phản hồi\.\.\./i)).toBeInTheDocument();

      // Rerender khi token đầu tiên cập nhật vào content
      rerender(
        <MessageItem
          message={{ id: "ai-1", role: "assistant", content: "Sinh viên cần đạt 120 tín chỉ", isStreaming: true }}
        />
      );
      expect(screen.queryByText(/Đang phản hồi\.\.\./i)).not.toBeInTheDocument();
      expect(screen.getByText(/Sinh viên cần đạt 120 tín chỉ/i)).toBeInTheDocument();
    });
  });

  // ==========================================
  // TEST LỖI 2: LỌC BỎ "NGUỒN: ..." TRONG NỘI DUNG, GIỮ Ở NÚT NGUỒN (N)
  // ==========================================
  describe("Lỗi 2: Bỏ chuỗi Nguồn trong câu trả lời, hiển thị qua nút Nguồn tài liệu tham khảo", () => {
    it("lọc bỏ các dòng Nguồn: và URL cs.lhu.edu.vn khỏi nội dung hiển thị", () => {
      const rawContent = `Điều kiện tốt nghiệp gồm:
- Tích lũy đủ 120 tín chỉ.
- Đạt chuẩn ngoại ngữ Bậc 3.

- Nguồn: Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học - Mục A.4 (https://cs.lhu.edu.vn/724/44104/Dieu-kien.html)
https://cs.lhu.edu.vn/724/44104/Dieu-kien.html`;

      const sources = [
        {
          document_id: 79,
          title: "Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học",
          section: "A.4",
          source_url: "https://cs.lhu.edu.vn/724/44104/Dieu-kien.html",
        },
      ];

      render(
        <MessageItem
          message={{ id: "ai-2", role: "assistant", content: rawContent, sources }}
        />
      );

      // Nội dung chính không còn chứa chữ "Nguồn:"
      expect(screen.queryByText(/- Nguồn:/i)).not.toBeInTheDocument();

      // Nút badge nguồn hiển thị chính xác số lượng
      const sourceBtn = screen.getByText(/Nguồn tài liệu tham khảo \(1\)/i);
      expect(sourceBtn).toBeInTheDocument();

      // Mở rộng phần nguồn và kiểm tra chi tiết
      fireEvent.click(sourceBtn);
      expect(screen.getByText(/Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học - Mục A.4/i)).toBeInTheDocument();
    });
  });

  // ==========================================
  // TEST LỖI 3: CÔ LẬP MESSAGES VÀ LOADING THEO TỪNG PHIÊN (KHÔNG HIỆN SANG PHIÊN KHÁC)
  // ==========================================
  describe("Lỗi 3: Không hiển thị stream của phiên này sang phiên khác", () => {
    it("giữ stream của phiên cũ chạy nền và không hiển thị sang phiên mới được chọn", async () => {
      let streamOnToken: ((token: string) => void) | undefined;
      let streamResolver: ((val: any) => void) | undefined;

      vi.spyOn(apiModule.authApi, 'ensureAuthenticated').mockResolvedValue({
        id: 1,
        username: 'test',
        role: 'student',
      });

      vi.spyOn(apiModule.chatApi, 'getSessions').mockResolvedValue([
        { id: 10, title: 'Phiên A', created_at: new Date().toISOString() },
        { id: 20, title: 'Phiên B', created_at: new Date().toISOString() },
      ]);

      vi.spyOn(apiModule.chatApi, 'getSessionMessages').mockImplementation(async (sid: number) => {
        if (sid === 10) return [{ id: 101, role: 'user', content: 'Câu hỏi phiên A' }];
        if (sid === 20) return [{ id: 201, role: 'user', content: 'Câu hỏi phiên B' }];
        return [];
      });

      vi.spyOn(apiModule.chatApi, 'sendMessageStream').mockImplementation(
        async (_msg: string, _sid?: number | null, onToken?: (t: string) => void) => {
          streamOnToken = onToken;
          return new Promise((resolve) => {
            streamResolver = resolve;
          });
        }
      );

      render(<App />);

      // Chọn Phiên A
      await waitFor(() => expect(screen.getByText('Phiên A')).toBeInTheDocument());
      fireEvent.click(screen.getByText('Phiên A'));
      await waitFor(() => expect(screen.getByText('Câu hỏi phiên A')).toBeInTheDocument());

      // Gửi câu hỏi ở Phiên A
      const textarea = await screen.findByPlaceholderText(/Nhập tin nhắn cho trợ lý AI/i);
      fireEvent.change(textarea, { target: { value: 'Hỏi tiếp ở A' } });
      const sendBtn = screen.getByTitle('Gửi tin nhắn');
      fireEvent.click(sendBtn);

      // Kiểm tra Phiên A đang hiện chỉ báo phản hồi
      await waitFor(() => {
        expect(screen.getByText(/Đang phản hồi\.\.\./i)).toBeInTheDocument();
      });

      // Người dùng chuyển ngay sang Phiên B
      fireEvent.click(screen.getByText('Phiên B'));

      // Phiên B phải hiện tin nhắn của B và KHÔNG hiển thị chỉ báo hoặc token của A
      await waitFor(() => {
        expect(screen.getByText('Câu hỏi phiên B')).toBeInTheDocument();
        expect(screen.queryByText(/Đang phản hồi\.\.\./i)).not.toBeInTheDocument();
      });

      // Stream của A tiếp tục phát sinh token trong nền
      act(() => {
        if (streamOnToken) {
          streamOnToken('Token bí mật của A');
        }
      });

      // Phiên B vẫn KHÔNG thấy token của A
      expect(screen.queryByText(/Token bí mật của A/i)).not.toBeInTheDocument();

      // Kết thúc stream của A
      await act(async () => {
        if (streamResolver) {
          streamResolver({ session_id: 10, answer: 'Câu trả lời hoàn chỉnh A', sources: [] });
        }
      });

      // Người dùng chuyển quay lại Phiên A: nhìn thấy đúng câu trả lời hoàn chỉnh của A
      fireEvent.click(screen.getByText('Phiên A'));
      await waitFor(() => {
        expect(screen.getByText(/Câu trả lời hoàn chỉnh A/i)).toBeInTheDocument();
      });
    });
  });
});
