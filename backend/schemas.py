from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class SubjectRecord(BaseModel):
    course_code: Optional[str] = Field(None, description="Course code (e.g. MATH101)")
    course_name: str = Field(..., description="Standardized course name")
    credits: Optional[int] = Field(None, description="Number of credits")
    grade: Optional[float] = Field(None, description="Grade (0.0 to 10.0)")
    semester: Optional[str] = Field(None, description="Semester offered")

class FailedSubject(SubjectRecord):
    status: str = Field("failed", description="passed | failed | not_taken")
    filter_reason: Optional[str] = Field(None, description="Reason for filtering (e.g., Grade < 4.0)")
    is_red_marked: bool = Field(False, description="Flag if marked with red circle/line")
    bbox: Optional[Any] = Field(None, description="Bounding box [x, y, w, h] of the grade")

class PrioritySubject(FailedSubject):
    priority_score: Optional[float] = Field(None, description="Priority score from 1.0 to 10.0")
    priority_reason: Optional[str] = Field(None, description="Explanation for the priority score")
    blocked_courses: List[str] = Field(default_factory=list, description="Courses blocked by this prerequisite")

class ProcessSummaryModel(BaseModel):
    total_subjects: int
    passed_count: int
    failed_count: int
    red_regions_count: int
    gpa: Optional[float] = None
    total_credits_earned: Optional[int] = None
    total_credits_failed: Optional[int] = None

class NormalizedCourse(BaseModel):
    code: str
    name: str
    credits: int
    grade: Optional[float]
    status: str
    semester: Optional[str]
    retake_count: int

class NormalizedSummary(BaseModel):
    gpa: Optional[float]
    total_credits_earned: int
    total_credits_failed: int

class NormalizedTranscript(BaseModel):
    student_id: Optional[str]
    semester_current: Optional[str]
    courses: List[NormalizedCourse]
    summary: NormalizedSummary

class UnifiedProcessResponse(BaseModel):
    success: bool = True
    session_id: str
    filename: str
    summary: ProcessSummaryModel
    failed_subjects: List[PrioritySubject]
    all_subjects: List[FailedSubject]
    annotated_image: Optional[str] = None
    normalized: Optional[NormalizedTranscript] = None
