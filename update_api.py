def update_api():
    with open('backend/api.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    if 'from backend.schemas import' not in content:
        content = content.replace(
            'from pydantic import BaseModel, Field',
            'from pydantic import BaseModel, Field\nfrom backend.schemas import UnifiedProcessResponse, ProcessSummaryModel, FailedSubject, PrioritySubject'
        )

    # Remove old schemas
    old_schemas = '''class SubjectItemModel(BaseModel):
    mon: str = Field(..., description="TAn mA'n h?c (Ting Vit)")
    diem: float = Field(..., description="?im s mA'n h?c (0.0 - 10.0)")
    trang_thai: Optional[str] = Field("?t", description="Trng thAi: ?t / KhA'ng 	")
    is_failed: Optional[bool] = Field(False, description="C? Anh du khA'ng 	")
    ly_do: Optional[str] = Field(None, description="LA do khA'ng 	")
    is_red_marked: Optional[bool] = Field(False, description="CA3 phAt hin du ? khA'ng")
    is_low_grade: Optional[bool] = Field(False, description="?im < 4.0")
    bbox: Optional[Any] = Field(None, description="T?a T bounding box [x, y, w, h]")
    # CAc tr?ng chucn hA3a mY rTng (dual-mapping  tng thA-ch camelCase / English schema)
    name: Optional[str] = Field(None, description="Alias cho 'mon'")
    grade: Optional[float] = Field(None, description="Alias cho 'diem'")
    status: Optional[str] = Field(None, description="Trng thAi ting Anh: 'passed' | 'failed'")
    reason: Optional[str] = Field(None, description="Alias cho 'ly_do'")
    code: Optional[str] = Field(None, description="MA mA'n h?c (nu cA3)")
    credits: Optional[int] = Field(None, description="S tA-n ch% (nu cA3)")
    semester: Optional[str] = Field(None, description="H?c k3")
    
    # Priority Engine fields
    priority_score: Optional[float] = Field(None, description="?im u tiAn h?c li")
    priority_reason: Optional[str] = Field(None, description="LA do u tiAn")
    blocked_courses: Optional[List[str]] = Field(default_factory=list, description="CAc mA'n b< chn")


class ProcessSummaryModel(BaseModel):
    total_subjects: int
    passed_count: int
    failed_count: int
    red_regions_count: int
    gpa: Optional[float] = None
    total_credits_earned: Optional[int] = None
    total_credits_failed: Optional[int] = None


class ProcessResponseModel(BaseModel):
    success: bool = True
    session_id: str
    filename: str
    summary: ProcessSummaryModel
    failed_subjects: List[SubjectItemModel]
    all_subjects: List[SubjectItemModel]
    annotated_image: Optional[str] = None
    normalized: Optional[Dict[str, Any]] = None'''

    # It's safer to just slice out the old Pydantic schemas section
    idx1 = content.find('class SubjectItemModel(BaseModel):')
    idx2 = content.find('class ErrorResponseModel(BaseModel):')
    
    if idx1 != -1 and idx2 != -1:
        content = content[:idx1] + content[idx2:]

    # Now rewrite the map_subject_contract in /api/process
    map_code_old = '''        def map_subject_contract(sub: Dict[str, Any]) -> Dict[str, Any]:
            mapped = dict(sub)
            mon = sub.get("mon", "")
            diem = sub.get("diem", 0.0)
            is_failed = sub.get("is_failed", diem < 4.0)
            mapped.setdefault("name", mon)
            mapped.setdefault("grade", diem)
            mapped.setdefault("status", "failed" if is_failed else "passed")
            mapped.setdefault("reason", sub.get("ly_do", ""))
            return mapped

        contract_failed_subjects = [map_subject_contract(s) for s in result["failed_subjects"]]
        contract_all_subjects = [map_subject_contract(s) for s in result["all_subjects"]]

        # Chuẩn hóa dữ liệu học tập thông qua module normalize.py
        normalized_data = normalize_transcript(result["all_subjects"])
        
        # Đồng bộ dữ liệu normalized (code, credits, semester) vào all_subjects và failed_subjects
        norm_map = { c["name"]: c for c in normalized_data.get("courses", []) }
        for sub in contract_all_subjects:
            nm = norm_map.get(sub["name"])
            if nm:
                sub["code"] = nm.get("code")
                sub["credits"] = nm.get("credits")
                sub["semester"] = nm.get("semester")
                
        for sub in contract_failed_subjects:
            nm = norm_map.get(sub["name"])
            if nm:
                sub["code"] = nm.get("code")
                sub["credits"] = nm.get("credits")
                sub["semester"] = nm.get("semester")

        # Gọi priority engine để tính mức độ ưu tiên học lại
        dummy_curriculum = [] # TODO: Load from real DB/file
        try:
            # Map failed_courses to the format expected by priority_engine
            pe_input = []
            for f_sub in contract_failed_subjects:
                pe_input.append({
                    "ma_mon": f_sub.get("code"),
                    "mon_hoc": f_sub.get("name"),
                    "tin_chi": f_sub.get("credits"),
                    "diem": f_sub.get("grade"),
                    "hoc_ky": f_sub.get("semester")
                })
            ranked = rank_priority(pe_input, dummy_curriculum)
            rank_map = { r["ma_mon"]: r for r in ranked if r.get("ma_mon") }
            
            for f_sub in contract_failed_subjects:
                code = f_sub.get("code")
                if code and code in rank_map:
                    f_sub["priority_score"] = rank_map[code].get("do_uu_tien")
                    f_sub["priority_reason"] = rank_map[code].get("ly_do")
                    f_sub["blocked_courses"] = rank_map[code].get("mon_bi_chan", [])
        except Exception as e:
            logger.error(f"Priority Engine error: {e}")'''

    map_code_new = '''        # Chuẩn hóa dữ liệu trước để lấy tên tiếng Anh (name, code, credits)
        normalized_data = normalize_transcript(result["all_subjects"])
        norm_map = { c["name"]: c for c in normalized_data.get("courses", []) }
        
        def map_failed_subject(sub: Dict[str, Any]) -> dict:
            mon = sub.get("mon", "")
            diem = sub.get("diem", 0.0)
            nm = norm_map.get(mon, {})
            return {
                "course_code": nm.get("code"),
                "course_name": nm.get("name", mon),
                "credits": nm.get("credits"),
                "grade": diem,
                "semester": nm.get("semester"),
                "status": "failed",
                "filter_reason": sub.get("ly_do"),
                "is_red_marked": sub.get("is_red_marked", False),
                "bbox": sub.get("bbox")
            }
            
        def map_passed_subject(sub: Dict[str, Any]) -> dict:
            mon = sub.get("mon", "")
            diem = sub.get("diem", 0.0)
            nm = norm_map.get(mon, {})
            return {
                "course_code": nm.get("code"),
                "course_name": nm.get("name", mon),
                "credits": nm.get("credits"),
                "grade": diem,
                "semester": nm.get("semester"),
                "status": "passed",
                "filter_reason": sub.get("ly_do"),
                "is_red_marked": sub.get("is_red_marked", False),
                "bbox": sub.get("bbox")
            }

        contract_failed_subjects = [map_failed_subject(s) for s in result["failed_subjects"]]
        contract_all_subjects = [map_passed_subject(s) if not s.get("is_failed") else map_failed_subject(s) for s in result["all_subjects"]]

        # 3. Gọi Priority Engine
        dummy_curriculum = []
        try:
            pe_input = []
            for f_sub in contract_failed_subjects:
                pe_input.append({
                    "ma_mon": f_sub.get("course_code"),
                    "mon_hoc": f_sub.get("course_name"),
                    "tin_chi": f_sub.get("credits"),
                    "diem": f_sub.get("grade"),
                    "hoc_ky": f_sub.get("semester")
                })
            ranked = rank_priority(pe_input, dummy_curriculum)
            rank_map = { r["ma_mon"]: r for r in ranked if r.get("ma_mon") }
            
            for f_sub in contract_failed_subjects:
                code = f_sub.get("course_code")
                if code and code in rank_map:
                    f_sub["priority_score"] = rank_map[code].get("do_uu_tien")
                    f_sub["priority_reason"] = rank_map[code].get("ly_do")
                    f_sub["blocked_courses"] = rank_map[code].get("mon_bi_chan", [])
                else:
                    f_sub["priority_score"] = None
                    f_sub["priority_reason"] = None
                    f_sub["blocked_courses"] = []
                    
            # Phải đồng bộ lại vào contract_all_subjects cho các môn failed
            for a_sub in contract_all_subjects:
                if a_sub["status"] == "failed":
                    code = a_sub.get("course_code")
                    if code and code in rank_map:
                        a_sub["priority_score"] = rank_map[code].get("do_uu_tien")
                        a_sub["priority_reason"] = rank_map[code].get("ly_do")
                        a_sub["blocked_courses"] = rank_map[code].get("mon_bi_chan", [])
                    else:
                        a_sub["priority_score"] = None
                        a_sub["priority_reason"] = None
                        a_sub["blocked_courses"] = []
        except Exception as e:
            logger.error(f"Priority Engine error: {e}")'''

    # String replace
    idx1 = content.find('def map_subject_contract')
    idx2 = content.find('summary_contract = {')
    
    if idx1 != -1 and idx2 != -1:
        content = content[:idx1] + map_code_new + '\n\n        ' + content[idx2:]

    with open('backend/api.py', 'w', encoding='utf-8') as f:
        f.write(content)

update_api()
