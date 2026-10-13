import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import App from "./App";

// Mock fetch for tests
global.fetch = vi.fn().mockImplementation(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve([]),
  })
);

describe("LHU AI App Integration", () => {
  it("renders new ChatGPT/Claude styled LHU AI interface", () => {
    render(<App />);

    // Brand and logo presence
    const brandElements = screen.getAllByText(/LHU AI/i);
    expect(brandElements.length).toBeGreaterThan(0);

    // New chat button
    expect(screen.getByText(/Cuộc trò chuyện mới/i)).toBeInTheDocument();

    // Welcome screen greeting
    expect(screen.getByText(/Đại học Lạc Hồng/i)).toBeInTheDocument();
    expect(screen.getByText(/Mình là LHU AI/i)).toBeInTheDocument();

    // Composer placeholder
    expect(screen.getByPlaceholderText(/Bạn muốn tìm hiểu điều gì\?/i)).toBeInTheDocument();

    // Disclaimer line
    expect(
      screen.getByText(/Trợ lý AI có thể mắc lỗi\. Hãy kiểm tra lại thông tin quan trọng\./i)
    ).toBeInTheDocument();
  });
});
