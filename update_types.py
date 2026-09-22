import os

def update_types():
    with open('frontend/src/types.ts', 'r', encoding='utf-8') as f:
        content = f.read()
        
    old_interface = '''export interface SubjectGrade {
  // Original extracted fields
  mon: string;
  diem: number;
  trang_thai?: string;
  is_failed?: boolean;
  ly_do?: string;
  is_red_marked?: boolean;
  is_low_grade?: boolean;
  bbox?: number[] | { [key: string]: number };

  // Normalized / English aliases
  name?: string;
  grade?: number;
  status?: 'passed' | 'failed' | 'not_taken' | string;
  reason?: string;
  code?: string;
  credits?: number;
  semester?: string | null;

  // Priority Engine fields
  priority_score?: number | null;
  priority_reason?: string | null;
  blocked_courses?: string[];
}'''

    new_interface = '''export interface SubjectRecord {
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
}'''
    
    if old_interface in content:
        content = content.replace(old_interface, new_interface)
    else:
        print("Could not find SubjectGrade interface!")
        
    # Replace uses of SubjectGrade with SubjectRecord
    content = content.replace('SubjectGrade', 'SubjectRecord')

    with open('frontend/src/types.ts', 'w', encoding='utf-8') as f:
        f.write(content)

update_types()
