export interface SubjectGrade {
  mon: string;
  diem: number;
  trang_thai?: string;
  is_failed?: boolean;
  ly_do?: string;
  is_red_marked?: boolean;
  is_low_grade?: boolean;
  bbox?: number[] | { [key: string]: number };
}

export interface ProcessSummary {
  total_subjects: number;
  passed_count: number;
  failed_count: number;
  red_regions_count: number;
}

export interface ProcessResponse {
  success: boolean;
  session_id: string;
  filename: string;
  summary: ProcessSummary;
  failed_subjects: SubjectGrade[];
  all_subjects: SubjectGrade[];
  annotated_image: string | null;
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
