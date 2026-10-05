import json
import os
from backend.priority_engine import rank_priority

def update_api_py():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    api_path = os.path.join(BASE_DIR, "backend", "api.py")

    with open(api_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'from backend.priority_engine import rank_priority' not in content:
        content = content.replace(
            'from backend.normalize import normalize_transcript',
            'from backend.normalize import normalize_transcript\nfrom backend.priority_engine import rank_priority'
        )

    # Insert priority engine call after normalize
    old_code = '''
        # Chuẩn hóa dữ liệu học tập thông qua module normalize.py
        normalized_data = normalize_transcript(result["all_subjects"])

        summary_contract = {'''
        
    new_code = '''
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
            logger.error(f"Priority Engine error: {e}")

        summary_contract = {'''
        
    # Since there are encoding issues with string matching, let's just do a string find and slice
    idx = content.find('normalized_data = normalize_transcript(result["all_subjects"])')
    if idx == -1:
        print("Could not find insertion point!")
        return
        
    idx2 = content.find('summary_contract = {', idx)
    
    content = content[:idx2] + new_code.strip() + '\n\n        summary_contract = {' + content[idx2+20:]
    
    with open(api_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
update_api_py()
