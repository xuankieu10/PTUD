import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import App from "./App";

// Mock child components to keep integration test focused
vi.mock("./components/FileUploader", () => ({
  FileUploader: () => <div data-testid="file-uploader" />
}));

vi.mock("./components/ResultSummary", () => ({
  ResultSummary: () => <div data-testid="result-summary" />
}));

vi.mock("./components/TranscriptTable", () => ({
  TranscriptTable: () => <div data-testid="transcript-table" />
}));

vi.mock("./components/VisualPreview", () => ({
  VisualPreview: () => <div data-testid="visual-preview" />
}));

describe("App Integration", () => {
  it("renders main app layout", () => {
    render(<App />);
    expect(screen.getByText(/Hệ thống Xét Tốt Nghiệp/i)).toBeInTheDocument();
    expect(screen.getByTestId("file-uploader")).toBeInTheDocument();
  });
});

