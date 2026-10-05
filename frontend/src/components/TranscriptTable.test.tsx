import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TranscriptTable } from "./TranscriptTable";

describe("TranscriptTable", () => {
  it("renders empty state", () => {
    render(<TranscriptTable allSubjects={[]} failedSubjects={[]} sessionId="" />);
    expect(screen.getByText(/Tất cả các môn/i)).toBeInTheDocument();
  });

  it("renders subjects and highlights failed ones", () => {
    const subjects = [
      {
        course_name: "Toán",
        course_code: "MATH",
        grade: 9.0,
        credits: 3,
        semester: "HK1",
        status: "passed",
        is_red_marked: false,
        filter_reason: null
      },
      {
        course_name: "Lý",
        course_code: "PHYS",
        grade: 3.0,
        credits: 2,
        semester: "HK1",
        status: "failed",
        is_red_marked: true,
        filter_reason: "Điểm < 4.0 | Đỏ",
        priority_score: 5.0,
        blocked_courses: ["Lý 2"]
      }
    ];

    render(<TranscriptTable allSubjects={subjects} failedSubjects={[subjects[1]]} sessionId="123" />);
    
    // Switch to all subjects tab
    const allTab = screen.getByText(/Tất cả các môn/i);
    fireEvent.click(allTab);
    
    expect(screen.getByText("Toán")).toBeInTheDocument();
    expect(screen.getByText("Lý")).toBeInTheDocument();
    
    // Switch back to failed subjects
    const failedTab = screen.getByText(/Môn không đạt/i);
    fireEvent.click(failedTab);
    
    // Check if failed status is rendered properly
    expect(screen.getByText(/Điểm < 4.0/i)).toBeInTheDocument();
  });
});

