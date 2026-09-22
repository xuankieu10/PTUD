"""
Module ưu tiên môn học học lại.
Logic xếp hạng ưu tiên dựa trên các tiêu chí:
1. Môn là tiên quyết của càng nhiều môn khác thì ưu tiên càng cao.
2. Số tín chỉ càng cao thì càng ưu tiên (để mau đạt số tín chỉ).
3. Nằm ở học kỳ sớm trong curriculum thì ưu tiên hơn học kỳ muộn.
"""

from typing import List, Dict, Any

def build_blocked_map(curriculum_data: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Tạo mapping từ mã môn -> danh sách mã môn bị chặn (môn phụ thuộc).
    """
    blocked_map: Dict[str, List[str]] = {}
    
    # Khởi tạo các key
    for course in curriculum_data:
        ma_mon = course.get("ma_mon")
        if ma_mon and ma_mon not in blocked_map:
            blocked_map[ma_mon] = []
            
    # Xây dựng danh sách phụ thuộc
    for course in curriculum_data:
        ma_mon = course.get("ma_mon")
        tien_quyet = course.get("mon_tien_quyet", [])
        for tq in tien_quyet:
            if tq not in blocked_map:
                blocked_map[tq] = []
            if ma_mon:
                blocked_map[tq].append(ma_mon)
                
    return blocked_map

def rank_priority(
    failed_courses: List[Dict[str, Any]], 
    curriculum_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Xếp hạng mức độ ưu tiên học lại cho các môn chưa đạt.
    
    Args:
        failed_courses: Danh sách dict các môn chưa đạt. 
            Mỗi dict gồm {mon_hoc, ma_mon, tin_chi, diem, hoc_ky}.
        curriculum_data: Danh sách dict chương trình đào tạo. 
            Mỗi dict gồm {ma_mon, ten_mon, tin_chi, mon_tien_quyet, hoc_ky_de_xuat}.
            
    Returns:
        List[Dict[str, Any]]: Danh sách các môn đã được xếp hạng, gồm 
            {ma_mon, ten_mon, do_uu_tien, ly_do, mon_bi_chan}.
    """
    blocked_map = build_blocked_map(curriculum_data)
    
    # Tạo lookup từ mã môn ra thông tin curriculum để tra cứu nhanh
    curr_lookup = {
        c.get("ma_mon"): c 
        for c in curriculum_data 
        if c.get("ma_mon")
    }
    
    results = []
    
    for course in failed_courses:
        ma_mon = course.get("ma_mon", "")
        mon_hoc = course.get("mon_hoc", "")
        
        curr_info = curr_lookup.get(ma_mon, {})
        
        # Lấy thông số từ failed_courses trước, nếu không có thì lấy từ curriculum
        tin_chi = course.get("tin_chi")
        if tin_chi is None:
            tin_chi = curr_info.get("tin_chi", 2)
            
        hoc_ky_de_xuat = curr_info.get("hoc_ky_de_xuat") 
        
        mon_bi_chan = blocked_map.get(ma_mon, [])
        num_blocked = len(mon_bi_chan)
        
        # Tính điểm
        score = 1.0
        ly_do_parts = []
        
        # 1. Tiên quyết (Trọng số cao nhất) - Mỗi môn bị chặn +2.5 điểm, tối đa +5.0
        if num_blocked > 0:
            add_score = min(5.0, num_blocked * 2.5)
            score += add_score
            ly_do_parts.append(f"Là tiên quyết của {num_blocked} môn khác")
            
        # 2. Tín chỉ - Môn nhiều tín chỉ ưu tiên hơn. Mỗi tín chỉ +0.5
        score += float(tin_chi) * 0.5
        ly_do_parts.append(f"Số tín chỉ: {tin_chi}")
        
        # 3. Học kỳ đề xuất - Môn học kỳ sớm quan trọng hơn
        if isinstance(hoc_ky_de_xuat, (int, float)):
            early_bonus = max(0.0, (9.0 - float(hoc_ky_de_xuat)) * 0.3)
            score += early_bonus
            if early_bonus > 0:
                ly_do_parts.append(f"Môn học kỳ sớm (HK{int(hoc_ky_de_xuat)})")
        else:
            ly_do_parts.append("Không rõ học kỳ đề xuất")
            
        # 4. Điểm quá thấp cần học lại ngay
        diem = course.get("diem")
        if diem is not None and float(diem) <= 2.0:
            score += 1.0
            ly_do_parts.append("Điểm quá thấp")
            
        # Ràng buộc điểm trong khoảng [1.0, 10.0]
        score = min(10.0, max(1.0, round(score, 1)))
        
        if not ly_do_parts:
            ly_do_parts.append("Môn tự chọn hoặc không có ràng buộc")
            
        ly_do = " | ".join(ly_do_parts)
        
        results.append({
            "ma_mon": ma_mon,
            "ten_mon": mon_hoc,
            "do_uu_tien": score,
            "ly_do": ly_do,
            "mon_bi_chan": mon_bi_chan
        })
        
    # Sắp xếp danh sách giảm dần theo điểm ưu tiên
    results.sort(key=lambda x: x["do_uu_tien"], reverse=True)
    return results
