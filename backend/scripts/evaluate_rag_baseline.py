"""
backend/scripts/evaluate_rag_baseline.py
Đo lường baseline Hit@4 của RAG trước khi sửa retrieval/metadata:
- 22 câu hỏi chuẩn đối soát (QĐ 22, QĐ 1013, CTĐT, Xung đột VB1/VB2, Ngoài phạm vi).
- Đánh giá top 4 chunk trả về, điểm số, đúng/sai (Hit@4), và kiểm tra xem có chunk VB2 (verified=False) nào lọt vào không.
"""

import os
import sys
from unittest.mock import MagicMock
from collections import namedtuple

# Thêm root vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.services.retrieval import search_chunks
from backend.app.services.embedding import get_embeddings_batch
from backend.scripts.ingest_quy_dinh import parse_docx_chunks, find_docx_file
from backend.scripts.seed_dataset import build_knowledge_base_chunks

ChunkRow = namedtuple("ChunkRow", ["id", "document_id", "title", "chunk_index", "content", "embedding", "section", "so_hieu", "url", "verified"])

# 22 câu hỏi kiểm thử chuẩn
BENCHMARK_QUESTIONS = [
    # Nhóm 1: QĐ 1013 (Điều kiện xét tốt nghiệp)
    {
        "id": "QD01",
        "category": "QĐ 1013",
        "query": "Điểm trung bình tích lũy tối thiểu để được xét tốt nghiệp là bao nhiêu?",
        "expected_sections": ["A.1", "A.1.2", "Mục 5.1", "Điều 15"],
        "expected_doc": "Điều kiện tốt nghiệp / QĐ 1013",
        "note": ">= 5.0 thang 10"
    },
    {
        "id": "QD02",
        "category": "QĐ 1013",
        "query": "Sinh viên chính quy cần chứng chỉ ngoại ngữ trình độ nào để tốt nghiệp?",
        "expected_sections": ["A.5", "A.5.1", "A.5.1-hình"],
        "expected_doc": "QĐ 1013 / Ngoại ngữ Bậc 3 / TOEIC 400",
        "note": "TOEIC 400 / Bậc 3"
    },
    {
        "id": "QD03",
        "category": "QĐ 1013",
        "query": "Điều kiện về tin học để xét tốt nghiệp là gì?",
        "expected_sections": ["A.5", "A.5.2", "A.5.2-hình"],
        "expected_doc": "QĐ 1013 / Sát hạch tin học",
        "note": "Sát hạch tin học hoặc CNTT tương đương"
    },
    {
        "id": "QD04",
        "category": "QĐ 1013",
        "query": "Tôi có cần đạt Giáo dục quốc phòng và Giáo dục thể chất để tốt nghiệp không?",
        "expected_sections": ["A.2", "A.2.1", "A.2.2", "Mục 7.4", "Mục 5.1"],
        "expected_doc": "QĐ 1013 / GDQP-GDTC",
        "note": "Bắt buộc cả 2"
    },
    {
        "id": "QD05",
        "category": "QĐ 1013",
        "query": "Cần có bao nhiêu chứng chỉ kỹ năng mềm để tốt nghiệp?",
        "expected_sections": ["A.3", "Mục 7.4"],
        "expected_doc": "QĐ 1013 / 4 Kỹ năng mềm",
        "note": "4 kỹ năng mềm"
    },
    {
        "id": "QD06",
        "category": "QĐ 1013",
        "query": "Còn nợ học phí thì có được xét tốt nghiệp không?",
        "expected_sections": ["A.4", "A.4.2"],
        "expected_doc": "QĐ 1013 / Không nợ học phí",
        "note": "Không được xét"
    },
    {
        "id": "QD07",
        "category": "QĐ 1013",
        "query": "Chưa trả sách ở thư viện thì có được xét tốt nghiệp không?",
        "expected_sections": ["A.4", "A.4.3"],
        "expected_doc": "QĐ 1013 / Thư viện",
        "note": "Không được xét"
    },
    {
        "id": "QD08",
        "category": "QĐ 1013",
        "query": "Đang bị kỷ luật đình chỉ học tập thì có được xét tốt nghiệp không?",
        "expected_sections": ["A.4", "A.4.1", "Mục 4.2"],
        "expected_doc": "QĐ 1013 / Kỷ luật",
        "note": "Không được xét"
    },
    {
        "id": "QD09",
        "category": "QĐ 1013",
        "query": "Sinh viên hệ liên thông có cần chứng chỉ GDQP, ngoại ngữ, tin học để tốt nghiệp không?",
        "expected_sections": ["B", "B.1", "B.2"],
        "expected_doc": "QĐ 1013 / Hệ liên thông",
        "note": "Không yêu cầu GDQP, KNM"
    },
    {
        "id": "TT01",
        "category": "QĐ 1013 / Thủ tục",
        "query": "Nộp hồ sơ xét tốt nghiệp ở đâu?",
        "expected_sections": ["C", "C-hình 3", "ho_so_nop"],
        "expected_doc": "graduate.lhu.edu.vn",
        "note": "graduate.lhu.edu.vn"
    },
    {
        "id": "TT02",
        "category": "QĐ 1013 / Thủ tục",
        "query": "Lệ phí xét tốt nghiệp là bao nhiêu và đóng ở đâu?",
        "expected_sections": ["C", "ho_so_nop"],
        "expected_doc": "Lệ phí 100.000 VNĐ",
        "note": "100.000đ tại P. Đào tạo"
    },
    {
        "id": "TT04",
        "category": "QĐ 1013 / Thủ tục",
        "query": "Đủ tín chỉ nhưng thiếu các điều kiện khác thì được cấp giấy gì?",
        "expected_sections": ["D", "ho_so_nop"],
        "expected_doc": "Giấy chứng nhận hoàn thành khóa học",
        "note": "Giấy chứng nhận hoàn thành khóa học"
    },

    # Nhóm 2: QĐ 22 (Quy chế đào tạo tín chỉ)
    {
        "id": "QC01",
        "category": "QĐ 22",
        "query": "Thang điểm đánh giá học phần và điểm chữ được quy định như thế nào?",
        "expected_sections": ["Mục 1.1", "Điều 11"],
        "expected_doc": "QĐ 22 Điều 11",
        "note": "Thang điểm A, B, C, D, F"
    },
    {
        "id": "QC02",
        "category": "QĐ 22",
        "query": "Những trường hợp nào sinh viên bị nhận điểm 0 học phần?",
        "expected_sections": ["Mục 1.2", "Điều 11, Điều 12"],
        "expected_doc": "QĐ 22 Điều 11, 12",
        "note": "Bỏ học, vắng thi, gian lận"
    },
    {
        "id": "QC03",
        "category": "QĐ 22",
        "query": "Sinh viên thi hộ hoặc nhờ người khác thi hộ bị xử lý kỷ luật thế nào?",
        "expected_sections": ["Mục 4.2", "Điều 21"],
        "expected_doc": "QĐ 22 Điều 21 / QĐ 840",
        "note": "Đình chỉ 1 năm lần 1, buộc thôi học lần 2"
    },
    {
        "id": "QC04",
        "category": "QĐ 22",
        "query": "Học cùng lúc hai chương trình bị buộc dừng học khi nào?",
        "expected_sections": ["Mục 4.1", "Mục 4.2", "Điều 19"],
        "expected_doc": "QĐ 22 Điều 19",
        "note": "GPA CT1 dưới 5.0 hoặc bị cảnh báo"
    },

    # Nhóm 3: CTĐT (Chương trình đào tạo CNTT)
    {
        "id": "CT01",
        "category": "CTĐT",
        "query": "Chương trình đào tạo ngành CNTT có tổng cộng bao nhiêu tín chỉ?",
        "expected_sections": ["Bảng tổng cộng", "Mục 7.1", "Mục 5.1"],
        "expected_doc": "CTĐT CNTT 150 TC",
        "note": "150 tín chỉ"
    },
    {
        "id": "CT02",
        "category": "CTĐT",
        "query": "Môn Tốt nghiệp bao nhiêu tín chỉ và học ở học kỳ nào?",
        "expected_sections": ["Học kỳ 8", "Mục 7.1"],
        "expected_doc": "CTĐT HK8",
        "note": "8 tín chỉ, HK8"
    },
    {
        "id": "CT03",
        "category": "CTĐT",
        "query": "Học kỳ 7 có những môn nào và tổng bao nhiêu tín chỉ?",
        "expected_sections": ["Học kỳ 7", "Mục 7.1"],
        "expected_doc": "CTĐT HK7",
        "note": "21 tín chỉ"
    },

    # Nhóm 4: Xung đột giữa VB1 và VB2
    {
        "id": "XD01",
        "category": "Xung đột VB1/VB2",
        "query": "Điểm dưới 5.0 có bị coi là điểm F và phải học lại không?",
        "expected_sections": ["Mục 1.1", "Mục 3.1", "Mục 8.1"],
        "expected_doc": "VB1 Điều 11 (F < 4.0; D đạt)",
        "note": "VB1: F < 4.0; VB2 ghi dưới 5"
    },
    {
        "id": "XD02",
        "category": "Xung đột VB1/VB2",
        "query": "Khi học lại thì điểm học phần được tính như thế nào, lấy điểm cao nhất hay điểm lần học cuối?",
        "expected_sections": ["Mục 3.1", "Mục 8.1"],
        "expected_doc": "VB1 Điều 11 K5đ (lần học cuối)",
        "note": "VB1: lần học cuối; VB2: điểm cao nhất"
    },

    # Nhóm 5: Ngoài phạm vi
    {
        "id": "NP01",
        "category": "Ngoài phạm vi",
        "query": "Cho tôi công thức nấu phở bò truyền thống Hà Nội.",
        "expected_sections": [],
        "expected_doc": "None (Không khớp)",
        "note": "Phải từ chối / điểm thấp"
    }
]


def load_all_chunks():
    """Tải toàn bộ chunks từ cơ sở dữ liệu nếu DB online; fallback về in-memory nếu DB offline."""
    # 1. Thử tải trực tiếp từ DB
    try:
        from backend.app.db import SessionLocal
        from sqlalchemy import text
        with SessionLocal() as db:
            rows = db.execute(text("""
                SELECT c.id, c.document_id, d.title, c.chunk_index, c.content, c.embedding, c.section, d.so_hieu, d.url, c.verified
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.document_id, c.chunk_index
            """)).fetchall()
            if rows and len(rows) >= 50:
                print(f"--> [DB Online] Đã nạp thành công {len(rows)} chunks trực tiếp từ SQL Server production.")
                chunk_rows = []
                for r in rows:
                    chunk_rows.append(ChunkRow(
                        id=r.id,
                        document_id=r.document_id,
                        title=r.title,
                        chunk_index=r.chunk_index,
                        content=r.content,
                        embedding=r.embedding,
                        section=r.section,
                        so_hieu=r.so_hieu,
                        url=r.url,
                        verified=bool(r.verified)
                    ))
                return chunk_rows
    except Exception as e:
        print(f"--> [DB Offline/Không kết nối được]: {e}, chuyển sang nạp chunks giả lập in-memory...")

    chunks_list = []
    
    # 1. Doc 9001 (Quy chế hợp nhất)
    docx_file = find_docx_file()
    c_doc9001 = parse_docx_chunks(docx_file)
    for c in c_doc9001:
        chunks_list.append({
            "document_id": 9001,
            "title": "Tổng hợp quy chế đào tạo và quy định học vụ LHU",
            "chunk_index": c["chunk_index"],
            "section": c["section"],
            "content": c["content"],
            "so_hieu": "QĐ 22/QĐ-ĐHLH & Quy định học vụ",
            "url": "http://cs.lhu.edu.vn",
            "verified": c.get("verified", True)
        })

    # 2. Doc 1 & Doc 2 từ seed_dataset
    c_doc1, c_doc2 = build_knowledge_base_chunks()
    for idx, c in enumerate(c_doc1):
        chunks_list.append({
            "document_id": 1,
            "title": "Điều kiện & Thủ tục quy trình xét cấp bằng Tốt nghiệp Đại học",
            "chunk_index": idx,
            "section": c["section"],
            "content": c["content"],
            "so_hieu": "1013/QĐ-ĐHLH",
            "url": "https://cs.lhu.edu.vn/724/44104/Dieu-kien-Thu-tuc-quy-trinh-xet-cap-bang-Tot-nghiep-Dai-hoc.html",
            "verified": True
        })

    for idx, c in enumerate(c_doc2):
        chunks_list.append({
            "document_id": 2,
            "title": "Chương trình đào tạo ngành Công nghệ thông tin",
            "chunk_index": idx,
            "section": c["section"],
            "content": c["content"],
            "so_hieu": "Niên giám 2023",
            "url": "https://lhu.edu.vn/106/45268/Cong-nghe-thong-tin.html",
            "verified": True
        })

    print(f"--> Đã nạp tổng cộng {len(chunks_list)} chunks vào bộ nhớ giả lập.")
    
    # Sinh embedding cho toàn bộ chunks
    texts = [c["content"] for c in chunks_list]
    print(f"--> Đang sinh embeddings cho {len(texts)} chunks bằng bge-m3...")
    embs = get_embeddings_batch(texts)
    
    chunk_rows = []
    for idx, c in enumerate(chunks_list):
        chunk_rows.append(ChunkRow(
            id=idx + 1,
            document_id=c["document_id"],
            title=c["title"],
            chunk_index=c["chunk_index"],
            content=c["content"],
            embedding=embs[idx],
            section=c["section"],
            so_hieu=c["so_hieu"],
            url=c["url"],
            verified=c["verified"]
        ))
    return chunk_rows


def run_evaluation():
    chunk_rows = load_all_chunks()
    
    # Kết nối DB thật nếu có, ngược lại dùng Mock DB Session
    active_db = None
    try:
        from backend.app.db import SessionLocal
        from sqlalchemy import text
        s = SessionLocal()
        s.execute(text("SELECT 1"))
        active_db = s
        print("--> Sử dụng Session kết nối SQL Server production cho retrieval.search_chunks.")
    except Exception:
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchall.return_value = chunk_rows
        active_db = mock_db
        print("--> Sử dụng Mock Session với chunk_rows in-memory cho retrieval.search_chunks.")

    results_table = []
    total_valid_q = 0
    hit_count = 0
    vb2_leak_count = 0

    print("\n" + "=" * 135)
    print(f"{'Mã':<6} | {'Nhóm':<15} | {'Câu hỏi':<40} | {'Hit@4':<6} | {'Chunk kỳ vọng':<25} | {'VB2?':<5} | {'Top 1 (Section & Điểm)':<30}")
    print("=" * 135)

    for q in BENCHMARK_QUESTIONS:
        qid = q["id"]
        cat = q["category"]
        query = q["query"]
        expected_sec = q["expected_sections"]

        top_chunks = search_chunks(active_db, query)
        
        # Kiểm tra Hit@4
        is_hit = False
        has_vb2 = False
        top1_info = "Không có chunk nào"

        if top_chunks:
            top1 = top_chunks[0]
            top1_info = f"{top1.get('section', '')[:18]} ({top1.get('score', 0.0):.3f})"
            
            # Kiểm tra xem có chunk nào khớp expected_sections
            for c in top_chunks:
                sec = c.get("section", "")
                if any(exp.lower() in sec.lower() for exp in expected_sec):
                    is_hit = True
                if c.get("verified") is False:
                    has_vb2 = True
        
        if cat == "Ngoài phạm vi":
            # Với ngoài phạm vi: kỳ vọng hoặc không có chunk nào >= 0.6, hoặc điểm rất thấp
            max_s = top_chunks[0].get("score", 0.0) if top_chunks else 0.0
            is_hit = (max_s < 0.6)  # Thành công nếu không bị nhận nhầm
            hit_str = "PASS" if is_hit else "FAIL"
            if is_hit:
                hit_count += 1
            total_valid_q += 1
        else:
            hit_str = "HIT" if is_hit else "MISS"
            if is_hit:
                hit_count += 1
            total_valid_q += 1

        if has_vb2:
            vb2_leak_count += 1

        vb2_str = "CÓ" if has_vb2 else "Không"
        exp_display = ", ".join(expected_sec[:2]) if expected_sec else "(Ngoài phạm vi)"
        print(f"{qid:<6} | {cat:<15} | {query[:38]:<40} | {hit_str:<6} | {exp_display[:23]:<25} | {vb2_str:<5} | {top1_info:<30}")

        results_table.append({
            "id": qid,
            "category": cat,
            "query": query,
            "hit": is_hit,
            "has_vb2": has_vb2,
            "top_chunks": [(c.get("section"), c.get("score"), c.get("verified")) for c in top_chunks]
        })

    print("=" * 110)
    hit_rate = (hit_count / total_valid_q) * 100
    print(f"\n--> TỔNG KẾT BASELINE RAG TRƯỚC KHI SỬA:")
    print(f"    - Hit@4 toàn diện: {hit_count}/{total_valid_q} ({hit_rate:.1f}%)")
    print(f"    - Số câu có chunk VB2 (chưa kiểm chứng) lọt vào top 4: {vb2_leak_count}/{total_valid_q}")

    return results_table


if __name__ == "__main__":
    run_evaluation()
