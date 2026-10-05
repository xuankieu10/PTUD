import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ResultSummary } from "./ResultSummary";

describe("ResultSummary", () => {
  it("displays correct summary data", () => {
    const summary = {
      total_subjects: 10,
      passed_count: 8,
      failed_count: 2,
      red_regions_count: 1
    };

    render(<ResultSummary summary={summary} />);
    
    expect(screen.getByText("10")).toBeInTheDocument(); // total
    expect(screen.getByText("8")).toBeInTheDocument();  // passed
    expect(screen.getByText("2")).toBeInTheDocument();  // failed
    expect(screen.getByText("1 vùng")).toBeInTheDocument(); // regions
  });
});

