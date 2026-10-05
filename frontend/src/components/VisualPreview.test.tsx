import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { VisualPreview } from "./VisualPreview";

describe("VisualPreview", () => {
  it("renders empty state", () => {
    const { container } = render(<VisualPreview annotatedImage={null} filename={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders image", () => {
    render(<VisualPreview annotatedImage="data:image/png;base64,dummy" filename="dummy.png" />);
    const img = screen.getByRole("img", { name: /Annotated preview/i });
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", "data:image/png;base64,dummy");
  });
});

