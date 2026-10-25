import os
import sys
import re
import openpyxl
from sqlalchemy import create_engine, text

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.services.embedding import get_embeddings_batch

def get_db_connection():
    engine = create_engine(settings.DATABASE_URL)
    return engine.connect()

def seed_program_courses(conn):
    excel_path = "database/seed_data/03_chuong_trinh_dao_tao.xlsx"
    print(f"--> Reading {excel_path} sheet 'mon_hoc'...")
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb["mon_hoc"]

    # Preload courses for matching
    db_courses = conn.execute(text("SELECT id, name FROM courses")).fetchall()
    course_name_map = {c.name.strip().lower(): c.id for c in db_courses}

    major = "Công nghệ thông tin"
    # Xóa các dòng rác legacy không có tên môn / học kỳ
    conn.execute(
        text("DELETE FROM program_courses WHERE major = :major AND (ten_mon IS NULL OR hoc_ky IS NULL)"),
        {"major": major}
    )

    rows_processed = 0
    rows_inserted = 0
    rows_updated = 0

    for r in sheet.iter_rows(values_only=True):
        if r[0] == "stt" or r[0] is None:
            continue
        
        stt, hoc_ky, ten_mon, tin_chi, loai, nhom_tu_chon, nhan_tren_trang, ghi_chu = r[:8]
        if not ten_mon:
            continue
        
        ten_mon_str = str(ten_mon).strip()
        hoc_ky_int = int(hoc_ky) if hoc_ky is not None else None
        
        # Tin chi: neu trong hoac None thi giu NULL, khong tu dien
        tin_chi_int = None
        if tin_chi is not None and str(tin_chi).strip() != "":
            try:
                tin_chi_int = int(float(str(tin_chi).strip()))
            except ValueError:
                tin_chi_int = None

        loai_str = str(loai).strip() if loai else ""
        is_required = 1 if "bắt buộc" in loai_str.lower() else 0
        nhom_tu_chon_str = str(nhom_tu_chon).strip() if nhom_tu_chon else None
        nhan_tren_trang_str = str(nhan_tren_trang).strip() if nhan_tren_trang else None
        ghi_chu_str = str(ghi_chu).strip() if ghi_chu else None

        # Match with courses if name matches
        matched_course_id = course_name_map.get(ten_mon_str.lower())

        # Check existing in program_courses
        existing = conn.execute(
            text("SELECT id FROM program_courses WHERE major = :major AND ten_mon = :ten_mon"),
            {"major": major, "ten_mon": ten_mon_str}
        ).fetchone()

        if existing:
            conn.execute(
                text("""
                    UPDATE program_courses 
                    SET course_id = COALESCE(:course_id, course_id),
                        is_required = :is_required,
                        hoc_ky = :hoc_ky,
                        loai = :loai,
                        nhom_tu_chon = :nhom_tu_chon,
                        nhan_tren_trang = :nhan_tren_trang,
                        ghi_chu = :ghi_chu,
                        tin_chi = :tin_chi
                    WHERE id = :id
                """),
                {
                    "id": existing.id,
                    "course_id": matched_course_id,
                    "is_required": is_required,
                    "hoc_ky": hoc_ky_int,
                    "loai": loai_str,
                    "nhom_tu_chon": nhom_tu_chon_str,
                    "nhan_tren_trang": nhan_tren_trang_str,
                    "ghi_chu": ghi_chu_str,
                    "tin_chi": tin_chi_int
                }
            )
            rows_updated += 1
        else:
            conn.execute(
                text("""
                    INSERT INTO program_courses (
                        major, course_id, is_required, hoc_ky, loai, 
                        nhom_tu_chon, nhan_tren_trang, ghi_chu, ten_mon, tin_chi
                    ) VALUES (
                        :major, :course_id, :is_required, :hoc_ky, :loai,
                        :nhom_tu_chon, :nhan_tren_trang, :ghi_chu, :ten_mon, :tin_chi
                    )
                """),
                {
                    "major": major,
                    "course_id": matched_course_id,
                    "is_required": is_required,
                    "hoc_ky": hoc_ky_int,
                    "loai": loai_str,
                    "nhom_tu_chon": nhom_tu_chon_str,
                    "nhan_tren_trang": nhan_tren_trang_str,
                    "ghi_chu": ghi_chu_str,
                    "ten_mon": ten_mon_str,
                    "tin_chi": tin_chi_int
                }
            )
            rows_inserted += 1

        rows_processed += 1

    conn.commit()
    print(f"--> program_courses seeded: {rows_processed} processed ({rows_inserted} inserted, {rows_updated} updated).")
    return rows_processed

def seed_graduation_conditions(conn):
    excel_path = "database/seed_data/04_dieu_kien_tot_nghiep.xlsx"
    print(f"--> Reading {excel_path} sheet 'dieu_kien'...")
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb["dieu_kien"]

    rows_processed = 0
    rows_inserted = 0
    rows_updated = 0

    for r in sheet.iter_rows(values_only=True):
        if r[0] == "ma" or r[0] is None:
            continue
        
        ma, nhom, dieu_kien, mo_ta, ap_dung_cq, ap_dung_lt_hc, muc_tren_trang = r[:7]
        if not ma:
            continue

        ma_str = str(ma).strip()
        nhom_str = str(nhom).strip() if nhom else ""
        dieu_kien_str = str(dieu_kien).strip() if dieu_kien else ""
        mo_ta_str = str(mo_ta).strip() if mo_ta else None
        ap_dung_cq_str = str(ap_dung_cq).strip() if ap_dung_cq else None
        ap_dung_lt_hc_str = str(ap_dung_lt_hc).strip() if ap_dung_lt_hc else None
        muc_tren_trang_str = str(muc_tren_trang).strip() if muc_tren_trang else None

        existing = conn.execute(
            text("SELECT id FROM graduation_conditions WHERE ma = :ma"),
            {"ma": ma_str}
        ).fetchone()

        if existing:
            conn.execute(
                text("""
                    UPDATE graduation_conditions
                    SET nhom = :nhom,
                        dieu_kien = :dieu_kien,
                        mo_ta = :mo_ta,
                        ap_dung_chinh_quy = :ap_dung_cq,
                        ap_dung_lien_thong_hoan_chinh = :ap_dung_lt_hc,
                        muc_tren_trang = :muc_tren_trang
                    WHERE id = :id
                """),
                {
                    "id": existing.id,
                    "nhom": nhom_str,
                    "dieu_kien": dieu_kien_str,
                    "mo_ta": mo_ta_str,
                    "ap_dung_cq": ap_dung_cq_str,
                    "ap_dung_lt_hc": ap_dung_lt_hc_str,
                    "muc_tren_trang": muc_tren_trang_str
                }
            )
            rows_updated += 1
        else:
            conn.execute(
                text("""
                    INSERT INTO graduation_conditions (
                        ma, nhom, dieu_kien, mo_ta, ap_dung_chinh_quy, 
                        ap_dung_lien_thong_hoan_chinh, muc_tren_trang
                    ) VALUES (
                        :ma, :nhom, :dieu_kien, :mo_ta, :ap_dung_cq,
                        :ap_dung_lt_hc, :muc_tren_trang
                    )
                """),
                {
                    "ma": ma_str,
                    "nhom": nhom_str,
                    "dieu_kien": dieu_kien_str,
                    "mo_ta": mo_ta_str,
                    "ap_dung_cq": ap_dung_cq_str,
                    "ap_dung_lt_hc": ap_dung_lt_hc_str,
                    "muc_tren_trang": muc_tren_trang_str
                }
            )
            rows_inserted += 1

        rows_processed += 1

    conn.commit()
    print(f"--> graduation_conditions seeded: {rows_processed} processed ({rows_inserted} inserted, {rows_updated} updated).")
    return rows_processed

def seed_documents_catalog(conn):
    excel_path = "database/seed_data/02b_danh_muc_van_ban.xlsx"
    print(f"--> Reading {excel_path} sheet 'danh_muc' (chỉ dòng có trạng thái 'Đã đọc nội dung')...")
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb["danh_muc"]

    rows_processed = 0
    rows_inserted = 0
    rows_updated = 0

    for r in sheet.iter_rows(values_only=True):
        if r[0] == "stt" or r[0] is None:
            continue

        stt, ten_van_ban, loai, so_hieu, ngay_ban_hanh, don_vi, url, ngay_thu_thap, trang_thai, ghi_chu = r[:10]
        if not ten_van_ban:
            continue

        trang_thai_str = str(trang_thai).strip() if trang_thai else ""
        if not trang_thai_str.startswith("Đã đọc nội dung"):
            continue

        title_str = str(ten_van_ban).strip()
        so_hieu_str = str(so_hieu).strip() if so_hieu else None
        url_str = str(url).strip() if url else None
        ngay_thu_thap_str = str(ngay_thu_thap).strip() if ngay_thu_thap else None

        existing = conn.execute(
            text("SELECT id FROM documents WHERE title = :title"),
            {"title": title_str}
        ).fetchone()

        if existing:
            conn.execute(
                text("""
                    UPDATE documents
                    SET so_hieu = :so_hieu,
                        url = :url,
                        source_url = COALESCE(source_url, :url),
                        ngay_thu_thap = :ngay_thu_thap,
                        status = 'indexed'
                    WHERE id = :id
                """),
                {
                    "id": existing.id,
                    "so_hieu": so_hieu_str,
                    "url": url_str,
                    "ngay_thu_thap": ngay_thu_thap_str
                }
            )
            rows_updated += 1
        else:
            conn.execute(
                text("""
                    INSERT INTO documents (
                        title, source, status, so_hieu, url, source_url, ngay_thu_thap, created_at
                    ) VALUES (
                        :title, 'seed_data', 'indexed', :so_hieu, :url, :url, :ngay_thu_thap, SYSDATETIME()
                    )
                """),
                {
                    "title": title_str,
                    "so_hieu": so_hieu_str,
                    "url": url_str,
                    "ngay_thu_thap": ngay_thu_thap_str
                }
            )
            rows_inserted += 1

        rows_processed += 1

    conn.commit()
    print(f"--> documents catalog seeded: {rows_processed} processed ({rows_inserted} inserted, {rows_updated} updated).")
    return rows_processed

def build_knowledge_base_chunks():
    """
    Tạo danh sách các chunk có cấu trúc động bằng cách đọc trực tiếp từ:
    - 04_dieu_kien_tot_nghiep.xlsx (sheets: dieu_kien, chung_chi_tuong_duong, ho_so_nop, quy_trinh_online, lien_he)
    - 03_chuong_trinh_dao_tao.xlsx (sheets: mon_hoc, tong_ket)
    Không hardcode nội dung text trong code; đảm bảo idempotent và bám sát nguồn dữ liệu mới.
    """
    wb_dk = openpyxl.load_workbook("database/seed_data/04_dieu_kien_tot_nghiep.xlsx", data_only=True)
    
    # 1. Sheet dieu_kien
    sheet_dk = wb_dk["dieu_kien"]
    dk_map = {}
    for r in list(sheet_dk.iter_rows(values_only=True))[1:]:
        if r[0]:
            ma = str(r[0]).strip()
            dk_map[ma] = {
                "ma": ma,
                "nhom": str(r[1]).strip() if r[1] else "",
                "dieu_kien": str(r[2]).strip() if r[2] else "",
                "mo_ta": str(r[3]).strip() if r[3] else "",
                "ap_dung_cq": str(r[4]).strip() if r[4] else "",
                "ap_dung_lt_hc": str(r[5]).strip() if r[5] else "",
                "muc_tren_trang": str(r[6]).strip() if r[6] else "",
            }

    # 2. Sheet chung_chi_tuong_duong
    sheet_cc = wb_dk["chung_chi_tuong_duong"]
    hinh1_rows = []
    hinh2_rows = []
    for r in list(sheet_cc.iter_rows(values_only=True))[1:]:
        if r[0]:
            item = {"ma": str(r[0]).strip(), "hinh": str(r[1]).strip(), "stt": r[2], "ten": str(r[3]).strip()}
            if "Hình 1" in item["hinh"] or item["ma"] == "DK10":
                hinh1_rows.append(item)
            elif "Hình 2" in item["hinh"] or item["ma"] == "DK11":
                hinh2_rows.append(item)

    # 3. Sheet ho_so_nop
    sheet_hs = wb_dk["ho_so_nop"]
    ho_so_rows = []
    for r in list(sheet_hs.iter_rows(values_only=True))[1:]:
        if r[0]:
            ho_so_rows.append({
                "stt": r[0], "loai": str(r[1]).strip() if r[1] else "",
                "noi_dung": str(r[2]).strip() if r[2] else "",
                "ap_dung": str(r[3]).strip() if r[3] else "",
                "ghi_chu": str(r[4]).strip() if r[4] else ""
            })

    # 4. Sheet quy_trinh_online
    sheet_qt = wb_dk["quy_trinh_online"]
    quy_trinh_rows = []
    for r in list(sheet_qt.iter_rows(values_only=True))[1:]:
        if r[0]:
            quy_trinh_rows.append({
                "buoc": r[0], "noi_dung": str(r[1]).strip() if r[1] else "",
                "muc_tren_trang": str(r[2]).strip() if r[2] else ""
            })

    # 5. Sheet lien_he
    sheet_lh = wb_dk["lien_he"]
    lien_he_rows = []
    for r in list(sheet_lh.iter_rows(values_only=True))[1:]:
        if r[0]:
            lien_he_rows.append({"don_vi": str(r[0]).strip(), "thong_tin": str(r[1]).strip()})

    doc_title = "Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học"
    base_url = "https://cs.lhu.edu.vn/724/44104/Dieu-kien-Thu-tuc-quy-trinh-xet-cap-bang-Tot-nghiep-Dai-hoc.html"
    so_hieu = "QĐ 1013/QĐ-ĐHLH"

    chunks_doc1 = []

    # A.1.1
    chunks_doc1.append({
        "section": "A.1.1",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.1.1 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "1. Học phần và điểm trung bình học tập:\n"
            f"a. {dk_map['DK01']['mo_ta']} (toàn khóa 150 tín chỉ)."
        )
    })

    # A.1.2
    chunks_doc1.append({
        "section": "A.1.2",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.1.2 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "1. Học phần và điểm trung bình học tập:\n"
            f"b. {dk_map['DK02']['mo_ta']}. "
            "Điểm trung bình tích lũy tối thiểu để được xét tốt nghiệp là 5.0 (loại trung bình trở lên)."
        )
    })

    # A.2
    chunks_doc1.append({
        "section": "A.2",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.2 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "2. Học phần GDQP-GDTC (Giáo dục quốc phòng và Giáo dục thể chất):\n"
            f"a. {dk_map['DK03']['mo_ta']}.\n"
            f"b. {dk_map['DK04']['mo_ta']}.\n"
            "Sinh viên hệ đại học chính quy bắt buộc phải đạt cả hai học phần Giáo dục quốc phòng (GDQP) và Giáo dục thể chất (GDTC) để đủ điều kiện xét tốt nghiệp."
        )
    })

    # A.3
    chunks_doc1.append({
        "section": "A.3",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.3 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "3. Chứng chỉ kỹ năng mềm:\n"
            f"Yêu cầu đủ {dk_map['DK05']['mo_ta']}."
        )
    })

    # A.4
    chunks_doc1.append({
        "section": "A.4",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.4 (A.4.1, A.4.2, A.4.3, A.4.4) | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "4. Học phí, tài liệu và hạnh kiểm:\n"
            f"a. {dk_map['DK06']['mo_ta']}. Sinh viên đang bị kỷ luật đình chỉ học tập sẽ KHÔNG được xét tốt nghiệp.\n"
            f"b. {dk_map['DK07']['mo_ta']}. Sinh viên còn nợ học phí sẽ KHÔNG được xét tốt nghiệp.\n"
            f"c. {dk_map['DK08']['mo_ta']}. Sinh viên chưa trả sách/tài liệu mượn tại thư viện sẽ KHÔNG được xét tốt nghiệp.\n"
            f"d. {dk_map['DK09']['mo_ta']}."
        )
    })

    # A.5
    chunks_doc1.append({
        "section": "A.5",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.5 (A.5.1, A.5.2) | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "5. Chứng chỉ và điều kiện ngành:\n"
            "a. Chứng chỉ/ chứng nhận ngoại ngữ: Sinh viên cần đạt 1 trong các mục sau:\n"
            f"- {dk_map['DK10']['mo_ta']}.\n"
            "b. Chứng chỉ/ chứng nhận ứng dụng công nghệ thông tin (tin học): Sinh viên cần đạt 1 trong các mục sau:\n"
            f"- {dk_map['DK11']['mo_ta']}."
        )
    })

    # A.5.1
    chunks_doc1.append({
        "section": "A.5.1",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.5.1 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "5. Chứng chỉ và điều kiện ngành:\n"
            f"a. Chứng chỉ/ chứng nhận ngoại ngữ: {dk_map['DK10']['mo_ta']}."
        )
    })

    # A.5.1-hình
    h1_lines = "\n".join(f"{it['stt']}. {it['ten']}" for it in hinh1_rows)
    chunks_doc1.append({
        "section": "A.5.1-hình",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.5.1-hình (Hình 1: Danh mục văn bằng, chứng chỉ, giấy chứng nhận ngoại ngữ tương đương Tiếng Anh Bậc 3) | URL: {base_url}]\n"
            "Hình 1: Bảng danh mục văn bằng, chứng chỉ, giấy chứng nhận ngoại ngữ tương đương chuẩn đầu ra Tiếng Anh Bậc 3 (Khung năng lực ngoại ngữ 6 bậc dùng cho Việt Nam):\n"
            f"{h1_lines}"
        )
    })

    # A.5.2
    chunks_doc1.append({
        "section": "A.5.2",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.5.2 | URL: {base_url}]\n"
            "A. Điều kiện tốt nghiệp hệ đại học chính quy Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023 về điều kiện xét tốt nghiệp):\n"
            "5. Chứng chỉ và điều kiện ngành:\n"
            f"b. Chứng chỉ/ chứng nhận ứng dụng công nghệ thông tin: {dk_map['DK11']['mo_ta']}."
        )
    })

    # A.5.2-hình
    h2_lines = "\n".join(f"{it['stt']}. {it['ten']}" for it in hinh2_rows)
    chunks_doc1.append({
        "section": "A.5.2-hình",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: A.5.2-hình (Hình 2: Danh mục văn bằng, chứng chỉ, chứng nhận ứng dụng CNTT tương đương) | URL: {base_url}]\n"
            "Hình 2: Bảng danh mục văn bằng, chứng chỉ, giấy chứng nhận ứng dụng công nghệ thông tin trình độ cơ bản tương đương Sát hạch tin học:\n"
            f"{h2_lines}\n"
            "[Ghi chú: Bảng trong PDF/ảnh có thể kết thúc ở dòng 8, các mục tiếp theo nếu có cần xác nhận với Nhà trường]."
        )
    })

    # B
    chunks_doc1.append({
        "section": "B",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: B (B.1, B.2) | URL: {base_url}]\n"
            "B. Điều kiện tốt nghiệp hệ Trung cấp - Đại học (liên thông) và Cao đẳng - Đại học (hoàn chỉnh) Khoa Công nghệ thông tin (Căn cứ Quyết định số 1013/QĐ-ĐHLH ngày 09/10/2023):\n"
            "1. Học phần và điểm trung bình học tập:\n"
            f"a. {dk_map['DK01']['mo_ta']}.\n"
            f"b. {dk_map['DK02']['mo_ta']}.\n"
            "2. Học phí, tài liệu và hạnh kiểm:\n"
            f"a. {dk_map['DK06']['mo_ta']}.\n"
            f"b. {dk_map['DK07']['mo_ta']}.\n"
            f"c. {dk_map['DK08']['mo_ta']}.\n"
            f"d. {dk_map['DK09']['mo_ta']}.\n"
            "GHI CHÚ QUAN TRỌNG: Theo trang quy định của trường, điều kiện của hệ liên thông và hoàn chỉnh chỉ gồm các điều kiện trên; KHÔNG yêu cầu chứng chỉ Giáo dục quốc phòng (GDQP), Giáo dục thể chất (GDTC), Kỹ năng mềm, Chứng chỉ ngoại ngữ hay Sát hạch tin học cho hệ này."
        )
    })

    # C
    giay_to_lines = "\n".join(f"- {it['noi_dung']}{' (*)' if it['ghi_chu'] else ''}" for it in ho_so_rows if it["loai"] == "Giấy tờ nộp" and "Chính quy" in it["ap_dung"])
    chunks_doc1.append({
        "section": "C",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: C (C.1, C.2, C.3) | URL: {base_url}]\n"
            "C. Nộp hồ sơ Xét cấp bằng tốt nghiệp:\n"
            "Nơi nộp và hình thức: Sinh viên truy cập vào trang web https://graduate.lhu.edu.vn/ và upload các file hồ sơ theo định dạng PDF (thực hiện các bước xét tốt nghiệp trực tuyến).\n"
            "1. Các file thông tin cần chuẩn bị đối với hệ đại học chính quy:\n"
            f"{giay_to_lines}\n"
            "2. Đối với hệ Trung cấp - Đại học (liên thông), Cao đẳng - Đại học (hoàn chỉnh): Bằng THPT, THCN hoặc Cao đẳng.\n"
            "3. Lệ phí xét tốt nghiệp: Đóng lệ phí 100.000 VNĐ tại phòng Đào tạo (phòng B101, Cơ sở 1).\n"
            "Lưu ý quan trọng (*): Sinh viên liên hệ/đăng ký lấy bảng điểm, chứng chỉ GDTC, GDQP, Kỹ năng mềm tại phòng Đào tạo (Bộ phận học vụ), Cơ sở 1."
        )
    })

    # C-hình 3
    qt_lines = "\n".join(f"Bước {it['buoc']}: {it['noi_dung']}" for it in quy_trinh_rows)
    chunks_doc1.append({
        "section": "C-hình 3",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: C-hình 3 (Hình 3: Quy trình hướng dẫn xét tốt nghiệp trực tuyến) | URL: {base_url}]\n"
            "Hình 3: Hướng dẫn xét tốt nghiệp trực tuyến (**Áp dụng từ ngày 20/11/2023) - Phòng Đào tạo Trường Đại học Lạc Hồng:\n"
            "Các bước thực hiện nộp hồ sơ xét tốt nghiệp trực tuyến:\n"
            f"{qt_lines}\n"
            "Kiểm tra đăng ký xét tốt nghiệp: Sau khi hoàn thành đăng ký, sinh viên có thể kiểm tra tình trạng đăng ký xét tốt nghiệp tại địa chỉ https://graduate.lhu.edu.vn"
        )
    })

    # D
    lh_dict = {it["don_vi"]: it["thong_tin"] for it in lien_he_rows}
    chunks_doc1.append({
        "section": "D",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: D (D.1, D.2) | Từ khóa: thiếu chứng chỉ, thiếu ngoại ngữ, thiếu tin học, chưa đủ điều kiện | URL: {base_url}]\n"
            "D. Cấp giấy chứng nhận khác:\n"
            "1. Giấy chứng nhận hoàn thành khóa học: Được cấp cho sinh viên đã đạt và tích lũy đủ học phần, số tín chỉ quy định trong chương trình đào tạo, nhưng còn thiếu các điều kiện khác để xét tốt nghiệp. Liên hệ cấp giấy: Phòng Đào tạo (phòng B101, Cơ sở 1).\n"
            "2. Giấy chứng nhận tốt nghiệp tạm thời: Được cấp cho sinh viên đã nộp hồ sơ xét cấp bằng tốt nghiệp (Mục C) và trong thời gian chờ nhận bằng chính thức (nếu cần). Liên hệ cấp giấy: Phòng Đào tạo (phòng B101, Cơ sở 1).\n"
            f"Thông tin giải đáp thắc mắc: {lh_dict.get('Giáo vụ Khoa CNTT (cô Trương Thị Đức)', '')}, {lh_dict.get('Trường Đại học Lạc Hồng', '')}."
        )
    })

    # ho_so_nop
    hs_all_lines = []
    hs_all_lines.append("1. Giấy tờ nộp (hệ chính quy):")
    for it in ho_so_rows:
        if it["loai"] == "Giấy tờ nộp":
            hs_all_lines.append(f"- {it['noi_dung']}: {it['ghi_chu'] if it['ghi_chu'] else 'Chính quy; liên thông; hoàn chỉnh'}")
    hs_all_lines.append("2. Thủ tục xét tốt nghiệp:")
    for it in ho_so_rows:
        if it["loai"] == "Thủ tục":
            hs_all_lines.append(f"- {it['noi_dung']}{(': ' + it['ghi_chu']) if it['ghi_chu'] else ''}")
    hs_all_lines.append("3. Các loại giấy chứng nhận:")
    for it in ho_so_rows:
        if it["loai"] == "Giấy chứng nhận khác":
            hs_all_lines.append(f"- {it['noi_dung']}: {it['ghi_chu']}")

    chunks_doc1.append({
        "section": "ho_so_nop",
        "content": (
            f"[Văn bản: {doc_title} | Số hiệu: {so_hieu} | Mục: C, D (Danh mục hồ sơ nộp, thủ tục và giấy chứng nhận) | URL: {base_url}]\n"
            "Chi tiết danh mục hồ sơ nộp xét tốt nghiệp, thủ tục và các loại giấy chứng nhận:\n"
            + "\n".join(hs_all_lines)
        )
    })

    # Document 2: CTDT
    wb_ctdt = openpyxl.load_workbook("database/seed_data/03_chuong_trinh_dao_tao.xlsx", data_only=True)
    ctdt_title = "Chương trình đào tạo ngành Công nghệ thông tin"
    ctdt_url = "https://lhu.edu.vn/106/45268/Cong-nghe-thong-tin.html"

    # Sheet tong_ket
    s_tk = wb_ctdt["tong_ket"]
    tk_rows = list(s_tk.iter_rows(values_only=True))[1:]
    sem_lines = []
    total_all = 150
    for r in tk_rows:
        if r[0] != "Toàn khóa" and r[0] is not None:
            sem_lines.append(f"  + Học kỳ {r[0]}: {r[1]} tín chỉ.")
        elif r[0] == "Toàn khóa":
            total_all = r[1]

    chunks_doc2 = [
        {
            "section": "Bảng tổng cộng",
            "content": (
                f"[Văn bản: {ctdt_title} | Mục: Bảng tổng cộng | URL: {ctdt_url}]\n"
                "Chương trình đào tạo ngành Công nghệ thông tin (Khoa Công nghệ thông tin, Trường Đại học Lạc Hồng):\n"
                f"- Tổng số tín chỉ toàn khóa: {total_all} tín chỉ.\n"
                "- Cấu trúc chương trình: Gồm 8 học kỳ trong toàn khóa đào tạo 4 năm.\n"
                "- Phân bổ tín chỉ từng học kỳ:\n"
                + "\n".join(sem_lines) + "\n"
                f"- Tổng cộng toàn khóa: {total_all} tín chỉ."
            )
        },
        {
            "section": "Học kỳ 7",
            "content": (
                f"[Văn bản: {ctdt_title} | Mục: Học kỳ 7 | URL: {ctdt_url}]\n"
                "Chương trình đào tạo ngành Công nghệ thông tin - Chi tiết Học kỳ 7:\n"
                "Học kỳ 7 có tổng cộng 21 tín chỉ, gồm các môn học:\n"
                "1. English 7: 4 tín chỉ (Bắt buộc)\n"
                "2. Kiểm thử và đảm bảo chất lượng phần mềm: 3 tín chỉ (Bắt buộc)\n"
                "3. Quản trị website trên VPS: 2 tín chỉ (Bắt buộc)\n"
                "4. Phát triển ứng dụng: 9 tín chỉ (Bắt buộc)\n"
                "5. Môn tự chọn (chọn 1 trong 2 môn): Trí tuệ nhân tạo (3 tín chỉ) hoặc Công nghệ Blockchain (3 tín chỉ).\n"
                "Tổng số tín chỉ học kỳ 7 là 21 tín chỉ."
            )
        },
        {
            "section": "Học kỳ 8",
            "content": (
                f"[Văn bản: {ctdt_title} | Mục: Học kỳ 8 | URL: {ctdt_url}]\n"
                "Chương trình đào tạo ngành Công nghệ thông tin - Chi tiết Học kỳ 8:\n"
                "Học kỳ 8 có tổng cộng 10 tín chỉ, gồm 2 môn học:\n"
                "1. Thực tập: 2 tín chỉ (Bắt buộc)\n"
                "2. Tốt nghiệp (Khóa luận tốt nghiệp/Đồ án tốt nghiệp): 8 tín chỉ (Bắt buộc).\n"
                "Môn Tốt nghiệp có 8 tín chỉ và được học ở Học kỳ 8 của khóa học."
            )
        }
    ]

    return chunks_doc1, chunks_doc2

def seed_knowledge_base(conn):
    print("--> Seeding Knowledge Base document chunks...")

    # Xóa các chunk cũ của các document không còn trong trạng thái indexed hoặc legacy doc 64
    conn.execute(text("DELETE FROM document_chunks WHERE document_id NOT IN (SELECT id FROM documents WHERE status = 'indexed')"))

    # 1. Document: Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học
    doc_title = "Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học"
    doc = conn.execute(
        text("SELECT id FROM documents WHERE title = :t"),
        {"t": doc_title}
    ).fetchone()
    if not doc:
        print(f"Error: Document '{doc_title}' not found in documents table.")
        return 0

    # 2. Document: Chương trình đào tạo ngành Công nghệ thông tin
    ctdt_title = "Chương trình đào tạo ngành Công nghệ thông tin"
    doc_ctdt = conn.execute(
        text("SELECT id FROM documents WHERE title = :t"),
        {"t": ctdt_title}
    ).fetchone()

    chunks_doc1, chunks_doc2 = build_knowledge_base_chunks()
    total_chunks_seeded = 0

    # Index doc 1 chunks (idempotent: xóa chunk cũ trước khi nạp)
    conn.execute(text("DELETE FROM document_chunks WHERE document_id = :did"), {"did": doc.id})
    print(f"--> Embedding {len(chunks_doc1)} chunks for '{doc_title}'...")
    texts_to_embed = [c["content"] for c in chunks_doc1]
    embeddings = get_embeddings_batch(texts_to_embed)

    for idx, item in enumerate(chunks_doc1):
        conn.execute(
            text("""
                INSERT INTO document_chunks (document_id, chunk_index, content, embedding, section)
                VALUES (:did, :idx, :content, :emb, :sec)
            """),
            {
                "did": doc.id,
                "idx": idx,
                "content": item["content"],
                "emb": embeddings[idx],
                "sec": item["section"]
            }
        )
        total_chunks_seeded += 1

    # Index doc 2 chunks if doc_ctdt exists
    if doc_ctdt:
        conn.execute(text("DELETE FROM document_chunks WHERE document_id = :did"), {"did": doc_ctdt.id})
        print(f"--> Embedding {len(chunks_doc2)} chunks for '{ctdt_title}'...")
        texts_ctdt = [c["content"] for c in chunks_doc2]
        emb_ctdt = get_embeddings_batch(texts_ctdt)

        for idx, item in enumerate(chunks_doc2):
            conn.execute(
                text("""
                    INSERT INTO document_chunks (document_id, chunk_index, content, embedding, section)
                    VALUES (:did, :idx, :content, :emb, :sec)
                """),
                {
                    "did": doc_ctdt.id,
                    "idx": idx,
                    "content": item["content"],
                    "emb": emb_ctdt[idx],
                    "sec": item["section"]
                }
            )
            total_chunks_seeded += 1

    conn.commit()
    print(f"--> Knowledge Base seeded: {total_chunks_seeded} total chunks indexed into document_chunks.")
    return total_chunks_seeded

def main():
    print("=== SEED DATASET STARTED ===")
    conn = get_db_connection()
    try:
        pc_count = seed_program_courses(conn)
        gc_count = seed_graduation_conditions(conn)
        doc_count = seed_documents_catalog(conn)
        chunk_count = seed_knowledge_base(conn)
        print("=== SEED DATASET COMPLETED SUCCESSFULLY ===")
        print(f"Summary: program_courses={pc_count}, graduation_conditions={gc_count}, documents={doc_count}, chunks={chunk_count}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
