"""
Module đồng bộ lịch học và lịch thi của Trung tâm Ngoại ngữ - Tin học (NNTH) ĐH Lạc Hồng.
Nguồn dữ liệu từ 3 API công khai trên tapi.lhu.edu.vn:
1. https://tapi.lhu.edu.vn//NNTH/AUTH/LichKhaiGiang_Select (Lịch khai giảng)
2. https://tapi.lhu.edu.vn//NNTH/AUTH/LichThi_Thang_Nam (Lịch thi)
3. https://tapi.lhu.edu.vn//NNTH/AUTH/LichThiDuKien_Thang_Nam (Lịch thi dự kiến)
"""

import logging
import time
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("NNTHSync")

API_LICH_KHAI_GIANG = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichKhaiGiang_Select"
API_LICH_THI = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichThi_Thang_Nam"
API_LICH_THI_DU_KIEN = "https://tapi.lhu.edu.vn//NNTH/AUTH/LichThiDuKien_Thang_Nam"

DEFAULT_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json",
    "Origin": "https://nnth.lhu.edu.vn",
    "Referer": "https://nnth.lhu.edu.vn/",
}


def _parse_vn_date(date_str: Optional[str]) -> Optional[date]:
    """Chuyển đổi chuỗi ngày định dạng dd/mm/yyyy sang đối tượng date."""
    if not date_str:
        return None
    s = str(date_str).strip()
    try:
        # Xử lý trường hợp có định dạng dd/mm/yyyy
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        pass
    try:
        # Trường hợp yyyy-mm-dd
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _classify_subject(name: str, desc: str = "") -> str:
    """
    Xác định loại: Ngoại ngữ, Tin học hoặc Khác dựa vào tên lớp/môn và mô tả.
    Ưu tiên kiểm tra lập trình trước, regex từ ngắn với ranh giới từ \b.
    Không tự ý đoán là 'Tin học'.
    """
    import re
    combined = f"{name} {desc}".lower()

    # 1. ƯU TIÊN KIỂM TRA LẬP TRÌNH VÀ TIN HỌC TRƯỚC
    # Tránh các trường hợp như "Lập trình Python cho người học tiếng Anh" hay "Ngôn ngữ lập trình" bị gán nhầm sang Ngoại ngữ
    if "lập trình" in combined:
        return "Tin học"

    th_phrases = [
        "tin học", "công nghệ thông tin", "máy tính", "ứng dụng cntt",
        "khoa học dữ liệu", "trí tuệ nhân tạo"
    ]
    if any(p in combined for p in th_phrases):
        return "Tin học"

    # Từ ngắn tin học: word, excel, powerpoint, cntt, mos, ic3 (dùng \b để 'password' không bị dính 'word')
    th_regex = r"\b(cntt|word|excel|powerpoint|ic3|mos)\b"
    if re.search(th_regex, combined):
        return "Tin học"

    # 2. KIỂM TRA NGOẠI NGỮ
    # 2.1. Cụm từ dài ngoại ngữ (đã loại bỏ từ 'ngôn ngữ' đứng riêng và các địa danh quốc gia 'hàn quốc', 'nhật bản')
    nn_phrases = [
        "tiếng anh", "ngôn ngữ anh", "ngoại ngữ",
        "tiếng hàn", "tiếng nhật", "tiếng trung", "tiếng hoa",
        "tiếng pháp", "tiếng đức"
    ]
    if any(p in combined for p in nn_phrases):
        return "Ngoại ngữ"

    # 2.2. Từ ngắn/chứng chỉ ngoại ngữ với ranh giới từ (\b)
    # n1..n5 chỉ được xem là ngoại ngữ khi đi kèm tiền tố jlpt hoặc trong ngữ cảnh tiếng nhật
    if re.search(r"\bjlpt\s*n[1-5]\b", combined) or (("tiếng nhật" in combined or "nhật" in combined) and re.search(r"\bn[1-5]\b", combined)):
        return "Ngoại ngữ"

    nn_regex = r"\b(vstep|toeic|ielts|cefr|english|topik|jlpt|hsk|hskk|chinese|mandarin|delf|dalf|tcf|french|goethe|testdaf|german)\b"
    if re.search(nn_regex, combined):
        return "Ngoại ngữ"

    # 3. KHÔNG KHỚP TỪ KHÓA NÀO -> Gán nhãn 'Khác' và ghi warning để rà soát
    logger.warning("Không thể tự động phân loại môn học/kỳ thi, gán nhãn 'Khác': name='%s', desc='%s'", name, desc)
    return "Khác"


def call_nnth_api(url: str, timeout: int = 15, max_retries: int = 2) -> List[Dict[str, Any]]:
    """
    Gọi API NNTH với timeout và retry tối đa 2 lần.
    Thử gọi không có header Authorization trước; nếu 401/403 mới thử thêm "Authorization: Bearer".
    """
    headers = dict(DEFAULT_HEADERS)
    last_err = None

    for attempt in range(max_retries + 1):
        try:
            res = requests.post(url, json={}, headers=headers, timeout=timeout)
            
            # Nếu 401 hoặc 403 và chưa có Authorization header, thử gắn "Authorization: Bearer"
            if res.status_code in (401, 403) and "Authorization" not in headers:
                logger.warning("API %s trả về %d không Auth, thử lại với 'Authorization: Bearer'", url, res.status_code)
                headers["Authorization"] = "Bearer"
                res = requests.post(url, json={}, headers=headers, timeout=timeout)

            # Nếu vẫn bị 401/403, DỪNG và báo lỗi, không tìm cách vượt qua
            if res.status_code in (401, 403):
                msg = f"API {url} trả về mã lỗi bảo mật {res.status_code}. Dừng đồng bộ theo yêu cầu."
                logger.error(msg)
                raise PermissionError(msg)

            res.raise_for_status()
            data = res.json()
            if isinstance(data, dict):
                return data.get("data", [])
            elif isinstance(data, list):
                return data
            return []
            
        except (requests.exceptions.RequestException, PermissionError) as e:
            last_err = e
            logger.warning("Lần gọi %d/%d API %s thất bại: %s", attempt + 1, max_retries + 1, url, e)
            if isinstance(e, PermissionError):
                raise
            if attempt < max_retries:
                time.sleep(1.5)

    raise RuntimeError(f"Không thể kết nối API {url} sau {max_retries + 1} lần thử: {last_err}")


def sync_nnth_data(db: Session) -> Dict[str, Any]:
    """
    Đồng bộ toàn bộ lịch học và lịch thi từ 3 API vào SQL Server (chạy lặp lại an toàn, không nhân đôi).
    Ghi nhận lịch sử vào center_sync_history.
    """
    now = datetime.now()
    schedules_synced = 0
    exams_synced = 0
    error_msg = None

    try:
        # ── 1. Đồng bộ Lịch Khai Giảng ─────────────────────────────────────────
        logger.info("Bắt đầu lấy dữ liệu Lịch khai giảng từ API NNTH...")
        raw_schedules = call_nnth_api(API_LICH_KHAI_GIANG)
        for s in raw_schedules:
            lop_id = s.get("LopID")
            if not lop_id:
                continue

            ten_lop = s.get("TenLop") or ""
            ten_khoa_hoc = s.get("TenKhoaHoc") or ten_lop
            mo_ta = s.get("MoTa") or ""
            loai = _classify_subject(ten_khoa_hoc or ten_lop, mo_ta)
            
            ngay_bd_str = s.get("NgayBD") or ""
            ngay_kt_str = s.get("NgayKT") or ""
            ngay_kg_date = _parse_vn_date(ngay_bd_str)
            ngay_kt_date = _parse_vn_date(ngay_kt_str)

            lich_hoc = s.get("ThoiGianHoc") or ""
            phong = s.get("Phong") or ""
            hinh_thuc = phong if phong else ("Online" if "online" in lich_hoc.lower() else "Trực tiếp")
            hoc_phi = s.get("HocPhi") or ""
            
            ten_kt = s.get("TenKT") or ""
            ngay_thi_kt = s.get("NgayThi") or ""
            ky_thi_du_kien = f"{ten_kt} - ngày thi {ngay_thi_kt}" if (ten_kt or ngay_thi_kt) else ""
            link_dang_ky = s.get("Link") or "https://nnth.lhu.edu.vn/dangkyhoc"
            so_luong = s.get("SoLuong") or ""

            # Khóa chống trùng: lop_id
            sql_check = text("SELECT id FROM center_schedules WHERE lop_id = :lid")
            existing = db.execute(sql_check, {"lid": lop_id}).fetchone()

            if existing:
                db.execute(
                    text("""
                        UPDATE center_schedules
                        SET ten_khoa_hoc = :tkh,
                            ten_lop = :tl,
                            loai = :loai,
                            ngay_khai_giang = :nkg,
                            ngay_khai_giang_str = :nkgs,
                            ngay_ket_thuc = :nkt,
                            ngay_ket_thuc_str = :nkts,
                            lich_hoc = :lh,
                            hinh_thuc = :ht,
                            hoc_phi = :hp,
                            ky_thi_du_kien = :ktdk,
                            link_dang_ky = :link,
                            so_luong = :sl,
                            phong = :phong,
                            mo_ta = :mota,
                            ngay_lay_du_lieu = SYSDATETIME(),
                            updated_at = SYSDATETIME()
                        WHERE lop_id = :lid
                    """),
                    {
                        "lid": lop_id, "tkh": ten_khoa_hoc, "tl": ten_lop, "loai": loai,
                        "nkg": ngay_kg_date, "nkgs": ngay_bd_str, "nkt": ngay_kt_date, "nkts": ngay_kt_str,
                        "lh": lich_hoc, "ht": hinh_thuc, "hp": hoc_phi, "ktdk": ky_thi_du_kien,
                        "link": link_dang_ky, "sl": so_luong, "phong": phong, "mota": mo_ta
                    }
                )
            else:
                db.execute(
                    text("""
                        INSERT INTO center_schedules (
                            lop_id, ten_khoa_hoc, ten_lop, loai,
                            ngay_khai_giang, ngay_khai_giang_str, ngay_ket_thuc, ngay_ket_thuc_str,
                            lich_hoc, hinh_thuc, hoc_phi, ky_thi_du_kien,
                            link_dang_ky, so_luong, phong, mo_ta, ngay_lay_du_lieu
                        ) VALUES (
                            :lid, :tkh, :tl, :loai,
                            :nkg, :nkgs, :nkt, :nkts,
                            :lh, :ht, :hp, :ktdk,
                            :link, :sl, :phong, :mota, SYSDATETIME()
                        )
                    """),
                    {
                        "lid": lop_id, "tkh": ten_khoa_hoc, "tl": ten_lop, "loai": loai,
                        "nkg": ngay_kg_date, "nkgs": ngay_bd_str, "nkt": ngay_kt_date, "nkts": ngay_kt_str,
                        "lh": lich_hoc, "ht": hinh_thuc, "hp": hoc_phi, "ktdk": ky_thi_du_kien,
                        "link": link_dang_ky, "sl": so_luong, "phong": phong, "mota": mo_ta
                    }
                )
            schedules_synced += 1

        # ── 2. Đồng bộ Lịch Thi (Chính thức & Dự kiến) ────────────────────────
        logger.info("Bắt đầu lấy dữ liệu Lịch thi chính thức và dự kiến từ API NNTH...")
        exam_endpoints = [
            (API_LICH_THI, False),         # is_du_kien = 0
            (API_LICH_THI_DU_KIEN, True),   # is_du_kien = 1
        ]

        for url, is_du_kien in exam_endpoints:
            raw_exams = call_nnth_api(url)
            for ex in raw_exams:
                ky_thi_id = ex.get("KyThiID")
                if not ky_thi_id:
                    continue

                ten_ky_thi = ex.get("TenMH") or "Kỳ thi NNTH"
                mo_ta = ex.get("MoTa") or ""
                loai = _classify_subject(ten_ky_thi, mo_ta)
                
                ngay_thi_str = ex.get("NgayThi") or ""
                ngay_thi_date = _parse_vn_date(ngay_thi_str)

                han_dang_ky = ex.get("NgayHetHanDK") or ""
                hoan_thi = ex.get("HoanThi") or ""
                tinh_trang = ex.get("ChiTiet") or ("Còn nhận đăng ký" if ex.get("Tinhtrang") == 1 else "Chưa nhận đăng ký")
                tinh_trang_code = ex.get("Tinhtrang")

                le_phi_thi = ex.get("LePhiThi") or "0"
                le_phi_cc = ex.get("LePhiCC") or "0"
                le_phi_tong = ex.get("LePhi") or le_phi_thi

                thang = ex.get("Thang")
                nam = ex.get("Nam")

                # Khóa chống trùng: (ky_thi_id, is_du_kien)
                sql_check = text("SELECT id FROM center_exams WHERE ky_thi_id = :kid AND is_du_kien = :dk")
                existing = db.execute(sql_check, {"kid": ky_thi_id, "dk": 1 if is_du_kien else 0}).fetchone()

                if existing:
                    db.execute(
                        text("""
                            UPDATE center_exams
                            SET ten_ky_thi = :tkt,
                                loai = :loai,
                                ngay_thi = :nt,
                                ngay_thi_str = :nts,
                                han_dang_ky = :hdk,
                                hoan_thi = :ht,
                                tinh_trang = :tt,
                                tinh_trang_code = :ttc,
                                le_phi_thi = :lpt,
                                le_phi_chung_chi = :lpcc,
                                le_phi_tong = :lptong,
                                thang = :thang,
                                nam = :nam,
                                ghi_chu = :gc,
                                ngay_lay_du_lieu = SYSDATETIME(),
                                updated_at = SYSDATETIME()
                            WHERE ky_thi_id = :kid AND is_du_kien = :dk
                        """),
                        {
                            "kid": ky_thi_id, "dk": 1 if is_du_kien else 0, "tkt": ten_ky_thi, "loai": loai,
                            "nt": ngay_thi_date, "nts": ngay_thi_str, "hdk": han_dang_ky, "ht": hoan_thi,
                            "tt": tinh_trang, "ttc": tinh_trang_code, "lpt": le_phi_thi, "lpcc": le_phi_cc,
                            "lptong": le_phi_tong, "thang": thang, "nam": nam, "gc": mo_ta
                        }
                    )
                else:
                    db.execute(
                        text("""
                            INSERT INTO center_exams (
                                ky_thi_id, is_du_kien, ten_ky_thi, loai,
                                ngay_thi, ngay_thi_str, han_dang_ky, hoan_thi,
                                tinh_trang, tinh_trang_code, le_phi_thi, le_phi_chung_chi, le_phi_tong,
                                thang, nam, ghi_chu, ngay_lay_du_lieu
                            ) VALUES (
                                :kid, :dk, :tkt, :loai,
                                :nt, :nts, :hdk, :ht,
                                :tt, :ttc, :lpt, :lpcc, :lptong,
                                :thang, :nam, :gc, SYSDATETIME()
                            )
                        """),
                        {
                            "kid": ky_thi_id, "dk": 1 if is_du_kien else 0, "tkt": ten_ky_thi, "loai": loai,
                            "nt": ngay_thi_date, "nts": ngay_thi_str, "hdk": han_dang_ky, "ht": hoan_thi,
                            "tt": tinh_trang, "ttc": tinh_trang_code, "lpt": le_phi_thi, "lpcc": le_phi_cc,
                            "lptong": le_phi_tong, "thang": thang, "nam": nam, "gc": mo_ta
                        }
                    )
                exams_synced += 1

        # Ghi nhận lịch sử thành công
        db.execute(
            text("""
                INSERT INTO center_sync_history (sync_type, status, schedules_count, exams_count, error_message, synced_at)
                VALUES ('NNTH', 'SUCCESS', :sc, :ec, NULL, SYSDATETIME())
            """),
            {"sc": schedules_synced, "ec": exams_synced}
        )
        db.commit()
        status_str = "SUCCESS"
        logger.info("Đồng bộ NNTH thành công: %d khóa học, %d kỳ thi.", schedules_synced, exams_synced)

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        status_str = "ERROR"
        logger.error("Lỗi trong quá trình đồng bộ NNTH: %s", e, exc_info=True)
        try:
            db.execute(
                text("""
                    INSERT INTO center_sync_history (sync_type, status, schedules_count, exams_count, error_message, synced_at)
                    VALUES ('NNTH', 'ERROR', :sc, :ec, :err, SYSDATETIME())
                """),
                {"sc": schedules_synced, "ec": exams_synced, "err": error_msg}
            )
            db.commit()
        except Exception:
            pass

    return {
        "status": status_str,
        "schedules_synced": schedules_synced,
        "exams_synced": exams_synced,
        "error": error_msg,
        "synced_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }


def get_last_sync_info(db: Session) -> Dict[str, Any]:
    """Lấy thông tin lần đồng bộ gần nhất."""
    row = db.execute(
        text("SELECT TOP 1 status, synced_at, error_message FROM center_sync_history ORDER BY id DESC")
    ).fetchone()
    if not row:
        return {
            "has_synced": False,
            "status": "UNKNOWN",
            "synced_at": None,
            "formatted_time": "chưa xác định"
        }
    
    synced_at = row[1]
    formatted = synced_at.strftime("%H:%M ngày %d/%m/%Y") if synced_at else "chưa xác định"
    return {
        "has_synced": True,
        "status": row[0],
        "synced_at": synced_at.isoformat() if synced_at else None,
        "formatted_time": formatted,
        "error_message": row[2]
    }


def get_upcoming_schedules(
    db: Session,
    loai: Optional[str] = None,
    from_today: bool = True
) -> List[Dict[str, Any]]:
    """Truy vấn danh sách lịch khai giảng sắp tới."""
    conditions = []
    params: Dict[str, Any] = {}

    if loai:
        conditions.append("loai = :loai")
        params["loai"] = loai

    if from_today:
        conditions.append("(ngay_khai_giang >= CAST(GETDATE() AS DATE) OR ngay_khai_giang IS NULL)")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"""
        SELECT id, lop_id, ten_khoa_hoc, ten_lop, loai,
               ngay_khai_giang, ngay_khai_giang_str, ngay_ket_thuc_str,
               lich_hoc, hinh_thuc, hoc_phi, ky_thi_du_kien, link_dang_ky,
               so_luong, phong, mo_ta, ngay_lay_du_lieu
        FROM center_schedules
        {where_clause}
        ORDER BY ngay_khai_giang ASC, id ASC
    """)
    rows = db.execute(sql, params).fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "lop_id": r[1],
            "ten_khoa_hoc": r[2],
            "ten_lop": r[3],
            "loai": r[4],
            "ngay_khai_giang": r[5].isoformat() if r[5] else None,
            "ngay_khai_giang_str": r[6],
            "ngay_ket_thuc_str": r[7],
            "lich_hoc": r[8],
            "hinh_thuc": r[9],
            "hoc_phi": r[10],
            "ky_thi_du_kien": r[11],
            "link_dang_ky": r[12],
            "so_luong": r[13],
            "phong": r[14],
            "mo_ta": r[15],
            "ngay_lay_du_lieu": r[16].isoformat() if r[16] else None
        })
    return results


def get_upcoming_exams(
    db: Session,
    loai: Optional[str] = None,
    is_du_kien: Optional[bool] = None,
    from_today: bool = True
) -> List[Dict[str, Any]]:
    """Truy vấn danh sách lịch thi sắp tới."""
    conditions = []
    params: Dict[str, Any] = {}

    if loai:
        conditions.append("loai = :loai")
        params["loai"] = loai

    if is_du_kien is not None:
        conditions.append("is_du_kien = :is_dk")
        params["is_dk"] = 1 if is_du_kien else 0

    if from_today:
        conditions.append("(ngay_thi >= CAST(GETDATE() AS DATE) OR ngay_thi IS NULL)")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"""
        SELECT id, ky_thi_id, is_du_kien, ten_ky_thi, loai,
               ngay_thi, ngay_thi_str, han_dang_ky, hoan_thi,
               tinh_trang, tinh_trang_code, le_phi_thi, le_phi_chung_chi, le_phi_tong,
               thang, nam, ghi_chu, ngay_lay_du_lieu
        FROM center_exams
        {where_clause}
        ORDER BY ngay_thi ASC, id ASC
    """)
    rows = db.execute(sql, params).fetchall()

    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "ky_thi_id": r[1],
            "is_du_kien": bool(r[2]),
            "ten_ky_thi": r[3],
            "loai": r[4],
            "ngay_thi": r[5].isoformat() if r[5] else None,
            "ngay_thi_str": r[6],
            "han_dang_ky": r[7],
            "hoan_thi": r[8],
            "tinh_trang": r[9],
            "tinh_trang_code": r[10],
            "le_phi_thi": r[11],
            "le_phi_chung_chi": r[12],
            "le_phi_tong": r[13],
            "thang": r[14],
            "nam": r[15],
            "ghi_chu": r[16],
            "ngay_lay_du_lieu": r[17].isoformat() if r[17] else None
        })
    return results
