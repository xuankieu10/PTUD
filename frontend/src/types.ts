export interface SubjectRecord {
  course_code: string | null;
  course_name: string;
  credits: number | null;
  grade: number | null;
  semester: string | null;
  
  status: 'passed' | 'failed' | 'not_taken' | string;
  filter_reason: string | null;
  is_red_marked: boolean;
  bbox?: number[] | { [key: string]: number } | null;

  priority_score?: number | null;
  priority_reason?: string | null;
  blocked_courses?: string[];
}

export interface ProcessSummary {
  total_subjects: number;
  passed_count: number;
  failed_count: number;
  red_regions_count: number;
  gpa?: number | null;
  total_credits_earned?: number;
  total_credits_failed?: number;
}

export interface NormalizedCourse {
  code: string;
  name: string;
  credits: number;
  grade: number | null;
  status: 'passed' | 'failed' | 'not_taken' | string;
  semester: string | null;
  retake_count: number;
}

export interface NormalizedTranscript {
  student_id: string | null;
  semester_current: string | null;
  courses: NormalizedCourse[];
  summary: {
    gpa: number | null;
    total_credits_earned: number;
    total_credits_failed: number;
  };
}

export interface ProcessResponse {
  success: boolean;
  session_id: string;
  filename: string;
  summary: ProcessSummary;
  failed_subjects: SubjectRecord[];
  all_subjects: SubjectRecord[];
  annotated_image: string | null;
  normalized?: NormalizedTranscript;
}

export interface ApiErrorResponse {
  success?: boolean;
  detail: string | Array<{ loc?: string[]; msg?: string; type?: string }>;
  status_code?: number;
}

export interface OllamaHealth {
  status: string;
  ollama: {
    online: boolean;
    host: string;
    models: string[];
    recommended_model: string;
    has_recommended: boolean;
    error: string | null;
  };
}

export interface CertificateExtractedData {
  loai_chung_chi: string;
  ten_chung_chi_cu_the: string;
  ten_nguoi_duoc_cap: string | null;
  ngay_cap: string | null;
  do_tin_cay: 'cao' | 'trung binh' | 'thap';
  loi_he_thong?: string;
}

export interface CertificateMatchingResult {
  muc_tot_nghiep_khop: string | null;
  do_tuong_dong: number;
  phuong_thuc_khop: string;
  trang_thai_cap_nhat: 'Đã hoàn tất' | 'Cần xác nhận thủ công';
  tu_dong_cap_nhat: boolean;
  ly_do: string;
  thong_tin_trich_xuat: CertificateExtractedData;
}

export interface CertificateProcessResponse {
  success: boolean;
  session_id: string;
  filename: string;
  extracted_data: CertificateExtractedData;
  matching_result: CertificateMatchingResult;
  preview_image: string | null;
}
