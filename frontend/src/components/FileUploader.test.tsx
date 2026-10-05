import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FileUploader } from "./FileUploader";

describe("FileUploader", () => {
  it("renders upload area correctly", () => {
    const mockOnProcess = vi.fn();
    
    render(
      <FileUploader
        onProcess={mockOnProcess}
        isLoading={false}
        health={null}
      />
    );
    
    expect(screen.getByText(/Kéo thả file/i)).toBeInTheDocument();
    expect(screen.getByText(/JPG, PNG, PDF/i)).toBeInTheDocument();
  });
});

