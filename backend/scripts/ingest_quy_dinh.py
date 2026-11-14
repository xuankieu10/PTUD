"""
backend/scripts/ingest_quy_dinh.py
Script nạp văn bản quy chế đào tạo và quy định học vụ hợp nhất từ file 'Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx' vào hệ thống RAG (bảng documents và document_chunks).
Sử dụng mô hình bge-m3 (1024 chiều) để sinh embedding.
Đảm bảo tính idempotent: xóa chunk cũ của document_id 9001 trước khi chèn mới.
Mỗi chunk mang metadata nguồn (VB1 / VB2) và cờ verified (True cho VB1 chính thức, False cho VB2 chưa kiểm chứng).
"""

import os
import sys
import re
import argparse
import docx
from sqlalchemy import create_engine, text

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.config import settings
from backend.app.services.embedding import get_embeddings_batch


DOCUMENT_ID_QUY_DINH = 9001
DOCUMENT_TITLE = "Tổng hợp quy chế đào tạo và quy định học vụ LHU"
DOCUMENT_SOURCE = "Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx"
DOCUMENT_SO_HIEU = "QĐ 22/QĐ-ĐHLH & Quy định học vụ"
DOCUMENT_URL = "http://cs.lhu.edu.vn"


def find_docx_file() -> str:
    """Tìm đường dẫn tới file docx quy chế hợp nhất trong thư mục dự án."""
    candidates = [
        os.path.join("database", "seed_data", "Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx"),
        "Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx",
        os.path.join("database", "seed_data", "văn_bản_quy_định.docx"),
        "văn_bản_quy_định.docx",
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    raise FileNotFoundError("Không tìm thấy tệp Tong_hop_quy_che_dao_tao_hoc_vu_LHU.docx trong database/seed_data hoặc thư mục gốc.")


def clean_google_urls(text: str) -> str:
    """Loại bỏ các link chuyển hướng google.com/url rác."""
    return re.sub(r'https?://(?:www\.)?google\.com/url\S+', '', text).strip()


def parse_docx_chunks(docx_path: str) -> list[dict]:
    """
    Đọc tệp quy chế đào tạo hợp nhất và tách thành 17 chunk quy chuẩn theo 9 mục của văn bản:
    - Nguồn VB1 (Niên giám 2023, QĐ 22/QĐ-ĐHLH): verified = True.
    - Nguồn VB2 (Bản tóm tắt quy định học vụ có mốc 2025): verified = False (gắn nhãn [VB2 – chưa kiểm chứng]).
    - Các điểm xung đột ở Mục 8: trình bày ưu tiên theo VB1 và ghi rõ điểm khác biệt của VB2 để SV đối chiếu.
    """
    if not os.path.exists(docx_path):
        raise FileNotFoundError(f"Tệp không tồn tại: {docx_path}")

    chunks = [
# 0: Mục 1.1 Thang điểm
    {
        "chunk_index": 0,
        "section": "Mục 1.1 – Thang điểm đánh giá học phần [VB1 – Điều 11]",
        "title": "Thang điểm đánh giá học phần và xếp loại điểm chữ",
        "source": "VB1 – QĐ 22/QĐ-ĐHLH Điều 11",
        "verified": True,
        "keywords": "thang điểm, thang 10, thang điểm chữ, điểm A, B, C, D, F, điểm F, dưới 4.0, điểm P",
        "content": (
            "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 11 | Trạng thái: Chính thức]\n"
            "Thang điểm đánh giá học phần và xếp loại điểm chữ:\n"
            "- Điểm A (8.5 – 10.0, thang 4: 4.0): Giỏi\n"
            "- Điểm B (7.0 – 8.4, thang 4: 3.0): Khá\n"
            "- Điểm C (5.5 – 6.9, thang 4: 2.0): Trung bình\n"
            "- Điểm D (4.0 – 5.4, thang 4: 1.0): Trung bình yếu (Đạt)\n"
            "- Điểm F (Dưới 4.0, thang 4: 0.0): Kém (Không đạt, phải học lại hoặc thi lại)\n"
            "- Điểm P: Đạt từ 5.0 trở lên, dùng cho học phần chỉ yêu cầu đạt (Giáo dục thể chất), không tính GPA."
        )
    },
    # 1: Mục 1.2 Cơ cấu điểm và điểm 0
    {
        "chunk_index": 1,
        "section": "Mục 1.2 – Cơ cấu điểm và quy định xử lý điểm 0 [VB1 – Điều 11, Điều 12]",
        "title": "Cơ cấu điểm học phần và các trường hợp bị điểm 0",
        "source": "VB1 – QĐ 22/QĐ-ĐHLH Điều 11, 12",
        "verified": True,
        "keywords": "cơ cấu điểm, quá trình 30, giữa kỳ 30, cuối kỳ 40, điểm 0, bỏ học, rút học phần, vắng thi, gian lận",
        "content": (
            "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 11, 12 | Trạng thái: Chính thức]\n"
            "Cơ cấu điểm học phần và quy định xử lý điểm 0:\n"
            "1. Cơ cấu điểm học phần: Quá trình 30%, Giữa kỳ 30%, Cuối kỳ 40%. Điểm liệt của từng điểm thành phần là 0.\n"
            "2. Điểm đặc biệt: Điểm I (hoãn thi), X (chưa đủ dữ liệu), R (miễn học và công nhận tín chỉ).\n"
            "3. Các trường hợp nhận điểm 0: Tự ý bỏ học; rút bớt học phần quá thời hạn 2 tuần; vắng thi hoặc vắng đánh giá không phép; gian lận trong thi cử."
        )
    },
    # 2: Mục 2 Điều kiện cấm thi
    {
        "chunk_index": 2,
        "section": "Mục 2 – Điều kiện cấm thi kết thúc học phần [VB2 – Điều 19]",
        "title": "Điều kiện cấm thi kết thúc học phần và xử lý vắng mặt",
        "source": "[VB2 – chưa kiểm chứng – Điều 19]",
        "verified": False,
        "keywords": "cấm thi, vắng quá 20%, điểm thành phần dưới 2.0, chuyên cần, giữa kỳ, không được dự thi",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Điều kiện cấm thi kết thúc học phần:\n"
            "(Lưu ý: Thông tin này từ văn bản tóm tắt chưa được kiểm chứng chính thức trong Niên giám; bạn nên hỏi giáo vụ khoa):\n"
            "1. Vắng mặt: Sinh viên vắng mặt quá 20% số tiết của học phần (lý thuyết hoặc thực hành) sẽ không được dự thi kết thúc học phần và nhận điểm 0 ở phần thi kết thúc học phần.\n"
            "2. Điểm thành phần: Điểm đánh giá bộ phận (chuyên cần, kiểm tra giữa kỳ) dưới 2.0 (thang 10) thì bị cấm thi kết thúc học phần."
        )
    },
    # 3: Mục 3.1 Quy định học lại VB1
    {
        "chunk_index": 3,
        "section": "Mục 3.1 – Quy định học lại học phần [VB1 – Điều 12]",
        "title": "Quy định học lại học phần bắt buộc và tự chọn",
        "source": "VB1 – QĐ 22 Điều 12",
        "verified": True,
        "keywords": "học lại, điểm F, dưới 4.0, học phần bắt buộc, học phần tự chọn, lần học cuối",
        "content": (
            "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 12 | Trạng thái: Chính thức]\n"
            "Quy định học lại học phần theo VB1:\n"
            "1. Học phần bắt buộc bị điểm F (dưới 4.0): Phải đăng ký học lại (hoặc học phần thay thế) ở các kỳ tiếp theo cho đến khi đạt từ điểm D (4.0) trở lên.\n"
            "2. Học phần tự chọn bị điểm F: Học lại học phần đó hoặc đổi sang học phần tự chọn tương đương khác theo CTĐT.\n"
            "3. Cách tính điểm: Điểm của lần học cuối là điểm chính thức của học phần. Không giới hạn số lần học lại."
        )
    },
    # 4: Mục 3.1 Kênh đăng ký học lại và xung đột điểm
    {
        "chunk_index": 4,
        "section": "Mục 3.1 – Đăng ký học lại và xung đột ngưỡng điểm [VB1 & VB2]",
        "title": "Kênh đăng ký học lại chính thức và xung đột ngưỡng điểm học lại",
        "source": "VB1 – Điều 7 & [VB2 – chưa kiểm chứng]",
        "verified": True,
        "keywords": "đăng ký học lại, dkmh.lhu.edu.vn, ngưỡng điểm học lại, điểm F, dưới 5, xung đột mục 8",
        "content": (
            "[Nguồn: VB1 – Điều 7 & [VB2 – chưa kiểm chứng]]\n"
            "Kênh đăng ký học lại và điểm xung đột:\n"
            "1. Cổng đăng ký học lại chính thức: Sinh viên đăng ký trực tuyến tại cổng https://dkmh.lhu.edu.vn theo kế hoạch học kỳ chính hoặc học kỳ hè của Phòng Đào tạo.\n"
            "2. Điểm xung đột (Mục 8): Theo VB1 chính thức, điểm F là dưới 4.0 mới phải học lại; theo VB2 ghi dưới 5 phải học lại và lấy điểm cao nhất. Sinh viên nên hỏi giáo vụ khoa để được xác nhận."
        )
    },
    # 5: Mục 3.2 Quy định kỳ thi phụ VB1
    {
        "chunk_index": 5,
        "section": "Mục 3.2 – Quy định kỳ thi phụ cuối kỳ [VB1 – Điều 11]",
        "title": "Điều kiện dự thi phụ và thời gian tổ chức kỳ thi phụ",
        "source": "VB1 – QĐ 22 Điều 11 K5đ",
        "verified": True,
        "keywords": "thi lại, kỳ thi phụ, điểm F, dưới 4.0, 2 tuần sau thi chính, vắng thi có lý do",
        "content": (
            "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 11 K5đ | Trạng thái: Chính thức]\n"
            "Điều kiện và quy định thi lại (kỳ thi phụ) theo VB1:\n"
            "1. Điều kiện dự thi phụ: Dành cho sinh viên không dự kỳ thi chính hoặc có điểm học phần dưới 4.0 (điểm F) ở kỳ thi chính.\n"
            "2. Thời gian tổ chức: Kỳ thi phụ được tổ chức sớm nhất 02 tuần sau kỳ thi chính.\n"
            "3. Vắng thi chính có lý do chính đáng: Được dự thi phụ ngay sau đó và điểm thi phụ tính là điểm thi lần đầu."
        )
    },
    # 6: Mục 3.2 Thi lại lần 2 và xung đột Mục 8
    {
        "chunk_index": 6,
        "section": "Mục 3.2 – Thi lại lần 2 và xung đột thời gian tổ chức [VB2 & Mục 8]",
        "title": "Quy định thi lại lần 2 và xung đột thời gian tổ chức kỳ thi phụ",
        "source": "[VB2 – chưa kiểm chứng] & VB1",
        "verified": True,
        "keywords": "thi lần 2, thi lại lần 2, đầu học kỳ mới, dưới 5, chuyên cần, giữa kỳ, xung đột mục 8",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng] & VB1]\n"
            "Thi lại lần 2 và lưu ý điểm xung đột:\n"
            "1. Theo [VB2 – chưa kiểm chứng]: Kỳ thi lần 2 (thi lại lần 2) tổ chức vào đầu học kỳ mới cho học phần dưới 5; điểm chuyên cần và giữa kỳ KHÔNG có thi lần 2.\n"
            "2. Điểm xung đột (Mục 8): VB1 tổ chức thi phụ sớm nhất 2 tuần sau thi chính cho môn điểm < 4.0; VB2 ghi thi lần 2 (thi lại lần 2) vào đầu học kỳ mới cho môn điểm < 5. Sinh viên nên theo dõi thông báo Phòng Đào tạo hoặc hỏi giáo vụ khoa."
        )
    },
    # 7: Mục 3.3 Cải thiện điểm
    {
        "chunk_index": 7,
        "section": "Mục 3.3 – Cải thiện điểm [VB1]",
        "title": "Quy định cải thiện điểm học phần",
        "source": "VB1 & [VB2 – chưa kiểm chứng]",
        "verified": True,
        "keywords": "cải thiện điểm, nâng điểm, học lại cải thiện, thi cải thiện, điểm cao nhất",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 & [VB2 – chưa kiểm chứng]]\n"
            "Quy định cải thiện điểm học phần:\n"
            "1. Theo VB1 (Chính thức): Sinh viên đã có điểm học phần đạt được đăng ký học hoặc thi để cải thiện theo quy định thi cải thiện điểm hiện hành của Trường (quy chế riêng của trường).\n"
            "2. Theo [VB2 – chưa kiểm chứng]: Sinh viên học lại để cải thiện khi có lớp ở các học kỳ tiếp theo; cách tính điểm ghi là lấy điểm cao nhất các lần học (mâu thuẫn với VB1 quy định lấy điểm lần cuối). Thông tin cách tính điểm cao nhất này chưa được xác nhận chính thức, bạn nên hỏi giáo vụ khoa."
        )
    },
    # 8: Mục 4.1 Cảnh báo học vụ và dừng học CT2
    {
        "chunk_index": 8,
        "section": "Mục 4.1 – Cảnh báo học vụ và dừng học CT2 [VB1 – Điều 13, 19]",
        "title": "Cảnh báo học vụ và quy định dừng học chương trình thứ hai",
        "source": "VB1 – QĐ 22 Điều 13, 19",
        "verified": True,
        "keywords": "cảnh báo học vụ, chương trình thứ hai, ct2, đtbtl dưới 5.0, phương án học tập",
        "content": (
            "[Nguồn: VB1 – QĐ 22 Điều 13, 19 | Trạng thái: Chính thức]\n"
            "Cảnh báo học vụ và dừng học chương trình 2:\n"
            "1. Cảnh báo học vụ: Thực hiện theo từng học kỳ để sinh viên biết và lập phương án học tập. Ngưỡng cảnh báo cụ thể theo quy định xử lý học vụ của Trường.\n"
            "2. Dừng học chương trình thứ hai: Sinh viên học cùng lúc 2 chương trình nếu điểm trung bình tích lũy chương trình 1 dưới 5.0 hoặc thuộc diện cảnh báo học vụ thì phải dừng học chương trình 2 ở học kỳ tiếp theo."
        )
    },
    # 9: Mục 4.2 Kỷ luật tạm ngừng học, thi hộ và buộc thôi học
    {
        "chunk_index": 9,
        "section": "Mục 4.2 – Kỷ luật tạm ngừng học, thi hộ và buộc thôi học [VB1 – Điều 21]",
        "title": "Xử lý kỷ luật tạm ngừng học, thi hộ và buộc thôi học",
        "source": "VB1 – Điều 21; QĐ 840 & [VB2 – chưa kiểm chứng]",
        "verified": True,
        "keywords": "buộc thôi học, tạm ngừng học, thi hộ, bằng giả, rèn luyện yếu, 1.2, 1.4, 1.6, 1.8",
        "content": (
            "[Nguồn: VB1 – Điều 21; QĐ 840 Điều 13 & [VB2 – chưa kiểm chứng]]\n"
            "Quy định tạm ngừng học và buộc thôi học:\n"
            "1. Theo VB1: Rèn luyện yếu/kém 2 kỳ liên tiếp: tạm ngừng học 01 năm; lặp lại lần 2 thì buộc thôi học. Thi hộ / nhờ thi hộ: đình chỉ học 01 năm (lần 1); buộc thôi học (lần 2). Làm giả hồ sơ, bằng cấp: buộc thôi học.\n"
            "2. Theo [VB2 – chưa kiểm chứng]: ĐTBTL dưới 1.2 (năm 1), 1.4 (năm 2), 1.6 (năm 3), 1.8 (năm sau); cảnh báo 2 kỳ chính liên tiếp hoặc quá 12-13 kỳ thì buộc thôi học (chưa xác nhận chính thức)."
        )
    },
    # 10: Mục 5.1 Điều kiện xét tốt nghiệp chính thức VB1
    {
        "chunk_index": 10,
        "section": "Mục 5.1 – Điều kiện xét tốt nghiệp đại học chính thức [VB1 – Điều 15]",
        "title": "Điều kiện xét tốt nghiệp đại học ngành CNTT theo Điều 15",
        "source": "VB1 – QĐ 22 Điều 15 K1đ, K2; Điều 4 K2a; Điều 11 K5b",
        "verified": True,
        "keywords": "xét tốt nghiệp, điều kiện tốt nghiệp, 150 tín chỉ, 8 học kỳ, không còn môn F, chuẩn đầu ra, tin học, ngoại ngữ, kỹ năng mềm",
        "content": (
            "[Nguồn: VB1 – Điều 15 K1đ, K2; Điều 4 K2a; Điều 11 K5b | Trạng thái: Chính thức]\n"
            "Điều kiện xét tốt nghiệp đại học chính thức (VB1 – Điều 15):\n"
            "1. Tích lũy đủ 150 tín chỉ của CTĐT (8 học kỳ), không còn học phần không đạt (không còn môn điểm F dưới 4.0).\n"
            "2. Có Chứng chỉ Giáo dục quốc phòng – an ninh và hoàn thành 3 học phần Giáo dục thể chất (đạt điểm P từ 5.0 trở lên).\n"
            "3. Đạt chuẩn trình độ tin học và ngoại ngữ theo quy định của Trường.\n"
            "4. Hoàn thành chương trình đào tạo Kỹ năng mềm.\n"
            "5. Cấp bằng tốt nghiệp trong vòng 03 tháng kể từ khi đủ điều kiện."
        )
    },
    # 11: Mục 5.2 Thủ tục xét tốt nghiệp và môn học chính trị VB2
    {
        "chunk_index": 11,
        "section": "Mục 5.2 – Thủ tục xét tốt nghiệp và môn học tốt nghiệp [VB1 & VB2]",
        "title": "Thủ tục xét tốt nghiệp định kỳ và lưu ý các môn chính trị",
        "source": "[VB2 – chưa kiểm chứng] & VB1",
        "verified": True,
        "keywords": "xét tốt nghiệp, mác lênin, tư tưởng hồ chí minh, truy cứu trách nhiệm hình sự, đợt xét tốt nghiệp, xung đột mục 8",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng] & VB1]\n"
            "Thủ tục xét tốt nghiệp và lưu ý môn học:\n"
            "1. Theo [VB2 – chưa kiểm chứng]: Sinh viên không đang bị truy cứu trách nhiệm hình sự; hoàn thành các môn Mác-Lênin, Tư tưởng HCM; nhà trường xét tốt nghiệp sau mỗi học kỳ theo thông báo của Phòng Đào tạo.\n"
            "2. Lưu ý xung đột (Mục 8): VB1 không có kỳ thi tốt nghiệp riêng cho các môn Mác-Lênin hay Tư tưởng HCM mà đây là môn học bình thường trong CTĐT; đồng thời VB1 bắt buộc chuẩn Ngoại ngữ, Tin học, Kỹ năng mềm."
        )
    },
    # 12: Mục 6.1 Cổng đăng ký môn học và App Me
    {
        "chunk_index": 12,
        "section": "Mục 6.1 – Cổng đăng ký môn học và App Me [VB1 – Điều 7]",
        "title": "Cổng đăng ký môn học trực tuyến và ứng dụng Me App",
        "source": "VB1 – Điều 7 K1; Niên giám 2023 tr. 128–138",
        "verified": True,
        "keywords": "dkmh.lhu.edu.vn, app.lhu.edu.vn, me.lhu.edu.vn, mssv, sms, mật khẩu",
        "content": (
            "[Nguồn: VB1 – Điều 7 K1; Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Hệ thống đăng ký môn học và ứng dụng sinh viên:\n"
            "1. Cổng đăng ký môn học trực tuyến chính thức: https://dkmh.lhu.edu.vn (thực hiện theo kế hoạch của Phòng Đào tạo trước/đầu mỗi học kỳ).\n"
            "2. Trang thông tin cá nhân: https://app.lhu.edu.vn hoặc http://me.lhu.edu.vn (Me App).\n"
            "3. Đăng nhập: Tên đăng nhập là MSSV. Mật khẩu ban đầu gửi qua SMS hoặc trên hóa đơn học phí. Sinh viên phải cập nhật số điện thoại và email trên Me App."
        )
    },
    # 13: Mục 6.2 Tra cứu học phí, rút học phần và thời gian đăng ký
    {
        "chunk_index": 13,
        "section": "Mục 6.2 – Tra cứu học phí, rút học phần và thời gian đăng ký [VB1]",
        "title": "Tra cứu nợ học phí, thời hạn rút bớt học phần và đăng ký hè",
        "source": "VB1 – Điều 7 K1, K5",
        "verified": True,
        "keywords": "hocphi.lhu.edu.vn, nợ học phí, rút học phần, 2 tuần, điểm 0, học kỳ hè, học kỳ phụ",
        "content": (
            "[Nguồn: VB1 – Điều 7 K1, K5 | Trạng thái: Chính thức]\n"
            "Tra cứu học phí và thời hạn rút học phần:\n"
            "1. Tra cứu nợ học phí: https://hocphi.lhu.edu.vn\n"
            "2. Rút bớt học phần: Thời hạn 2 tuần kể từ khi học phần được triển khai; ngoài thời hạn tự ý bỏ học sẽ bị điểm 0.\n"
            "3. Thời gian đăng ký học lại / cải thiện điểm thực hiện theo các học kỳ chính hoặc học kỳ phụ (hè) do Trường ấn định trên cổng thông tin sinh viên https://dkmh.lhu.edu.vn."
        )
    },
    # 14: Mục 6.3 Kênh đăng ký học lại và lưu ý lớp học vét
    {
        "chunk_index": 14,
        "section": "Mục 6.3 – Hướng dẫn đăng ký học lại và lưu ý lớp học vét [VB2]",
        "title": "Kênh đăng ký học lại trực tuyến và giải thích về lớp học vét",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "học lại, học vét, google form, zalo, forms.gle, lớp học vét đăng ký ở đâu",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Kênh hỗ trợ đăng ký học lại và lưu ý lớp học vét:\n"
            "1. Về lớp học vét: Hiện tại tài liệu hiện có không đề cập riêng về lớp học vét; sinh viên có nhu cầu học lại thực hiện theo quy trình đăng ký học lại thông thường.\n"
            "2. Kênh hỗ trợ đăng ký HỌC LẠI trực tuyến (VB2): Google Form: https://forms.gle/iBk3hNwG4SCGKMEFA; Nhóm Zalo hỗ trợ: https://zalo.me/g/ar6b85p9opfxctwhxwpd (Lưu ý: Đây là kênh hỗ trợ đăng ký học lại của VB2 chưa kiểm chứng, không phải kênh riêng của lớp học vét; kênh chính thức là https://dkmh.lhu.edu.vn)."
        )
    },
    # 15: Mục 6.3 Bảng chi phí học lại tham khảo và App Me
    {
        "chunk_index": 15,
        "section": "Mục 6.3 – Bảng chi phí học lại tham khảo và App Me [VB2]",
        "title": "Bảng tra cứu chi phí học lại tham khảo và theo dõi trên App Me",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "chi phí học lại, học phí học lại, app me, bảng chi phí tham khảo, google sheets",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Chi phí học lại tham khảo và theo dõi đợt học:\n"
            "1. Bảng danh sách môn học lại và chi phí tham khảo: https://docs.google.com/spreadsheets/d/1LBSioDaeoHSclt4R4yXpO0aFR-6kkTk9/edit?usp=sharing&ouid=103838733389649116635&rtpof=true&sd=true\n"
            "2. Lưu ý về học phí: Tài liệu hiện có không nêu mức học phí học lại cụ thể (mức 500.000đ/môn chỉ áp dụng cho Kỹ năng mềm, không áp dụng cho học lại môn học thông thường).\n"
            "3. Nếu quá hạn đăng ký, sinh viên theo dõi trên App ME về đợt tiếp theo."
        )
    },
    # 16: Mục 6.6 Giấy chứng nhận online và vay vốn sinh viên
    {
        "chunk_index": 16,
        "section": "Mục 6.6 – Giấy chứng nhận online và vay vốn sinh viên [VB1 – Điều 16]",
        "title": "Cấp giấy chứng nhận online và xác nhận vay vốn sinh viên",
        "source": "VB1 – QĐ 22 Điều 16 K3; QĐ 406",
        "verified": True,
        "keywords": "giấy chứng nhận online, certification.lhu.edu.vn, vay vốn sinh viên, sinhviendanghoc.lhu.edu.vn, phòng ctsv, D201",
        "content": (
            "[Nguồn: VB1 – QĐ 22 Điều 16 K3; QĐ 406 | Trạng thái: Chính thức]\n"
            "Dịch vụ chứng nhận online và vay vốn sinh viên:\n"
            "1. Cấp giấy chứng nhận online: Đăng ký trực tuyến tại http://certification.lhu.edu.vn theo hướng dẫn trên hệ thống.\n"
            "2. Giấy xác nhận vay vốn sinh viên (Mẫu 01-TDSV theo QĐ 157/2007/QĐ-TTg): Nộp trực tuyến tại https://sinhviendanghoc.lhu.edu.vn hoặc nộp trực tiếp tại Phòng Công tác sinh viên (Phòng D201, Cơ sở 2). Kèm thẻ SV, CCCD, biên lai học phí kỳ gần nhất."
        )
    },
    # 17: Mục 6.6 Miễn giảm học phí và thủ tục xin trở lại học
    {
        "chunk_index": 17,
        "section": "Mục 6.6 – Miễn giảm học phí và thủ tục xin trở lại học [VB1]",
        "title": "Thủ tục miễn giảm học phí và đơn xin trở lại học sau nghỉ tạm thời",
        "source": "VB1 – QĐ 406 tr. 118–120, 135",
        "verified": True,
        "keywords": "miễn giảm học phí, phụ lục VIII NĐ 81/2021, phòng ctsv, D201, trở lại học, đơn viết, nghỉ tạm thời",
        "content": (
            "[Nguồn: VB1 – QĐ 406 tr. 118–120, 135 | Trạng thái: Chính thức]\n"
            "Miễn giảm học phí và trở lại học:\n"
            "1. Miễn giảm học phí, ưu đãi giáo dục (Mẫu 41 / Phụ lục VIII NĐ 81/2021): Nộp tại Phòng Công tác sinh viên (Phòng D201, Cơ sở 2); viết bút xanh, không tẩy xóa. Kèm thẻ SV, CCCD, biên lai học phí.\n"
            "2. Xin trở lại học sau nghỉ tạm thời: Đơn viết gửi Hiệu trưởng, nộp tại Trường trước kỳ học mới ít nhất 1 tuần."
        )
    },
    # 18: Mục 7.1 CTĐT ngành CNTT: Học kỳ 1 (17 TC)
    {
        "chunk_index": 18,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 1 (17 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 1 (17 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 1, 17 tc, toán cao cấp 1, english 1, nhập môn lập trình, cấu trúc và lắp ráp máy tính, mã nguồn mở, nhập môn cntt, dự án kỹ thuật",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT (Mã ngành: 7480201, Khóa 2023–2027) – Học kỳ 1 (Tổng cộng 17 TC):\n"
            "- Giáo dục quốc phòng (-): Bắt buộc, học đầu khóa, không tính tín chỉ\n"
            "- 102002 Giáo dục thể chất 1 (0 TC, BB)\n"
            "- 102073 Toán cao cấp 1 (4 TC, BB)\n"
            "- 102074 English 1 (3 TC, BB)\n"
            "- 111094 Nhập môn lập trình (2 TC, BB)\n"
            "- 111001 Cấu trúc và lắp ráp máy tính (3 TC, BB)\n"
            "- 111080 Phần mềm mã nguồn mở (2 TC, BB)\n"
            "- 111055 Nhập môn Công nghệ thông tin (1 TC, BB)\n"
            "- 111053 Nhập môn Phát triển dự án kỹ thuật (2 TC, BB)."
        )
    },
    # 19: Mục 7.1 CTĐT ngành CNTT: Học kỳ 2 (20 TC)
    {
        "chunk_index": 19,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 2 (20 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 2 (20 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 2, 20 tc, xác suất thống kê, english 2, tin học đại cương, vật lý thực hành, điện tử cơ bản, ui/ux, kỹ thuật lập trình, mạng máy tính",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 2 (Tổng cộng 20 TC):\n"
            "- 102003 Giáo dục thể chất 2 (0 TC, BB)\n"
            "- 102087 Xác suất thống kê (2 TC, BB)\n"
            "- 102075 English 2 (4 TC, BB; Học trước: 102074)\n"
            "- 102014 Tin học đại cương (Word, Excel, PowerPoint, Internet) (3 TC, BB)\n"
            "- 111046 Vật lý thực hành (3 TC, BB)\n"
            "- 111047 Điện tử cơ bản (2 TC, BB)\n"
            "- 111056 Thiết kế UI/UX (2 TC, BB)\n"
            "- 111058 Kỹ thuật lập trình (2 TC, BB; Học trước: 111094)\n"
            "- 112061 Mạng máy tính (2 TC, BB)."
        )
    },
    # 20: Mục 7.1 CTĐT ngành CNTT: Học kỳ 3 (25 TC)
    {
        "chunk_index": 20,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 3 (25 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 3 (25 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 3, 25 tc, triết học mác lênin, kinh tế chính trị, cnxh khoa học, english 3, toán rời rạc, cấu trúc dữ liệu và giải thuật, tín hiệu số, cơ sở dữ liệu, mạng máy tính nâng cao",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 3 (Tổng cộng 25 TC):\n"
            "- 102004 Giáo dục thể chất 3 (0 TC, BB)\n"
            "- 102063 Triết học Mác - Lênin (3 TC, BB)\n"
            "- 102064 Kinh tế chính trị Mác - Lênin (2 TC, BB)\n"
            "- 102065 Chủ nghĩa xã hội khoa học (2 TC, BB)\n"
            "- 102076 English 3 (4 TC, BB; Học trước: 102075)\n"
            "- 111010 Toán rời rạc (3 TC, BB)\n"
            "- 111062 Cấu trúc dữ liệu và giải thuật (3 TC, BB; Học trước: 111058)\n"
            "- 111048 Tín hiệu số cơ bản (2 TC, BB)\n"
            "- 111059 Cơ sở dữ liệu (3 TC, BB)\n"
            "- 112064 Mạng máy tính nâng cao (3 TC, BB; Học trước: 112061)."
        )
    },
    # 21: Mục 7.1 CTĐT ngành CNTT: Học kỳ 4 (21 TC)
    {
        "chunk_index": 21,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 4 (21 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 4 (21 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 4, 21 tc, tư tưởng hồ chí minh, pháp luật đại cương, english 4, dịch vụ mạng, lập trình hướng đối tượng, hệ quản trị csdl, front-end, kiến tập",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 4 (Tổng cộng 21 TC):\n"
            "- 102033 Tư tưởng Hồ Chí Minh (2 TC, BB)\n"
            "- 102006 Pháp luật đại cương (2 TC, BB)\n"
            "- 102077 English 4 (4 TC, BB; Học trước: 102076)\n"
            "- 111036 Dịch vụ mạng (3 TC, BB)\n"
            "- 111070 Lập trình hướng đối tượng (3 TC, BB; Học trước: 111062)\n"
            "- 111060 Hệ quản trị CSDL (3 TC, BB; Học trước: 111059)\n"
            "- 111067 Lập trình Front-End (2 TC, BB; Học trước: 111056)\n"
            "- 111081 Kiến tập (2 TC, BB)."
        )
    },
    # 22: Mục 7.1 CTĐT ngành CNTT: Học kỳ 5 (20 TC)
    {
        "chunk_index": 22,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 5 (20 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 5 (20 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 5, 20 tc, lịch sử đảng, english 5, nguyên lý thống kê, thiết kế hệ thống mạng, lập trình back-end, lập trình windows, tự chọn",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 5 (Tổng cộng 20 TC):\n"
            "- 102066 Lịch sử Đảng Cộng sản Việt Nam (2 TC, BB)\n"
            "- 102078 English 5 (4 TC, BB; Học trước: 102077)\n"
            "- 111057 Nguyên lý thống kê (2 TC, BB; Học trước: 102087)\n"
            "- 112065 Thiết kế hệ thống mạng (3 TC, BB)\n"
            "- 111066 Lập trình Back-End (3 TC, BB)\n"
            "- 111072 Lập trình trên môi trường Windows (3 TC, BB; Học trước: 111060, 111070)\n"
            "- Tự chọn 3 TC (chọn 1/2): 111043 Phân tích thiết kế HT hướng đối tượng (3 TC; Học trước: 111059, 111060) hoặc 111089 Phân tích thiết kế HT hướng quan hệ (3 TC)."
        )
    },
    # 23: Mục 7.1 CTĐT ngành CNTT: Học kỳ 6 (16 TC)
    {
        "chunk_index": 23,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 6 (16 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 6 (16 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 6, 16 tc, english 6, thiết kế hệ thống mạng nâng cao, giao tiếp thiết bị, di động, web, python học máy, python thị giác máy tính",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 6 (Tổng cộng 16 TC):\n"
            "- 102079 English 6 (4 TC, BB; Học trước: 102078)\n"
            "- 112068 Thiết kế hệ thống mạng nâng cao (2 TC, BB; Học trước: 112065)\n"
            "- 111069 Lập trình giao tiếp thiết bị (2 TC, BB)\n"
            "- 111082 Lập trình ứng dụng di động (3 TC, BB; Học trước: 111066)\n"
            "- 111083 Lập trình ứng dụng web (3 TC, BB; Học trước: 111066, 111067)\n"
            "- Tự chọn 2 TC (chọn 1/2): 111071 Lập trình Python cho học máy (2 TC) hoặc 111084 Lập trình Python trong thị giác máy tính (2 TC)."
        )
    },
    # 24: Mục 7.1 CTĐT ngành CNTT: Học kỳ 7 (21 TC)
    {
        "chunk_index": 24,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 7 (21 TC) [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 7 (21 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 7, 21 tc, english 7, kiểm thử và đảm bảo chất lượng phần mềm, quản trị website trên vps, phát triển ứng dụng, trí tuệ nhân tạo, công nghệ blockchain",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 7 (Tổng cộng 21 TC):\n"
            "- 102080 English 7 (4 TC, BB; Học trước: 102079)\n"
            "- 111065 Kiểm thử và đảm bảo chất lượng phần mềm (3 TC, BB)\n"
            "- 111085 Quản trị website trên VPS (2 TC, BB)\n"
            "- 111038 Phát triển ứng dụng (9 TC, BB; Học trước: 111069, 111082, 111083)\n"
            "- Tự chọn 3 TC (chọn 1/2): 111088 Trí tuệ nhân tạo (3 TC; Học trước: 111071) hoặc 111061 Công nghệ Blockchain (3 TC)."
        )
    },
    # 25: Mục 7.1 CTĐT ngành CNTT: Học kỳ 8 (10 TC) & Tổng kết khóa
    {
        "chunk_index": 25,
        "section": "Mục 7.1 – CTĐT ngành CNTT: Học kỳ 8 (10 TC) & Tổng kết khóa [VB1]",
        "title": "Chương trình đào tạo ngành CNTT – Học kỳ 8 (10 TC) và Tổng kết toàn khóa (150 TC)",
        "source": "VB1 – Niên giám 2023",
        "verified": True,
        "keywords": "ctđt cntt, học kỳ 8, 10 tc, thực tập, tốt nghiệp, 150 tín chỉ, toàn khóa, 8 học kỳ",
        "content": (
            "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
            "Mục 7.1 – CTĐT ngành CNTT – Học kỳ 8 (10 TC) & Tổng kết toàn khóa:\n"
            "- 111049 Thực tập (2 TC, BB; Học trước: 111081)\n"
            "- 33333 Tốt nghiệp (8 TC, BB; Song hành: 111049).\n"
            "- Tổng tín chỉ HK8: 10 TC.\n"
            "- Toàn khóa: Đúng 150 tín chỉ (8 học kỳ). GDQP không tính tín chỉ; GDTC gồm 3 học phần 0 tín chỉ (yêu cầu điểm P từ 5.0 trở lên). BB = bắt buộc, TC = tự chọn."
        )
    },
    # 26: Mục 7.3 Lệ phí thi chứng chỉ Ngoại ngữ - Tin học
    {
        "chunk_index": 26,
        "section": "Mục 7.3 – Lệ phí thi chứng chỉ Ngoại ngữ - Tin học [VB2]",
        "title": "Lệ phí thi chứng chỉ VSTEP, CEFR, Tin học và thời hạn nộp",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "lệ phí thi, vstep, cefr, tin học, 2.000.000, 1.100.000, 600.000, hạn nộp chứng chỉ tiếng anh, 1 tháng",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Lệ phí thi chứng chỉ Ngoại ngữ và Tin học:\n"
            "(Lưu ý: VB1 Niên giám không có bảng lệ phí chi tiết; thông tin này chưa được xác nhận chính thức, bạn nên hỏi giáo vụ khoa hoặc Trung tâm NNTH):\n"
            "1. Lệ phí thi:\n"
            "- Chứng chỉ Ngoại ngữ 6 bậc (VSTEP): 2.000.000 VNĐ / thí sinh / kỳ thi.\n"
            "- Đánh giá năng lực tiếng Anh (CEFR): 1.100.000 VNĐ / thí sinh / kỳ thi.\n"
            "- Chứng chỉ Ứng dụng CNTT: 600.000 VNĐ / thí sinh / kỳ thi.\n"
            "2. Thời hạn nộp: Nộp trước ngày xét tốt nghiệp tối thiểu 1 tháng."
        )
    },
    # 27: Mục 7.3 Đăng ký sát hạch tin học chuẩn đầu ra
    {
        "chunk_index": 27,
        "section": "Mục 7.3 – Đăng ký sát hạch tin học chuẩn đầu ra [VB2]",
        "title": "Phí ôn luyện sát hạch tin học và link đăng ký",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "sát hạch tin học, 90.000, forms.gle, zalo, app me",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Đăng ký sát hạch tin học chuẩn đầu ra:\n"
            "1. Phí ôn luyện: 90.000 VNĐ / sinh viên.\n"
            "2. Link đăng ký lớp ôn: https://forms.gle/WtUpfZbPiWAq3RqK6\n"
            "3. Nhóm Zalo hỗ trợ: https://zalo.me/g/g2elp3xxzxexl5lqjlc0\n"
            "4. Nếu quá hạn đăng ký, sinh viên theo dõi trên App ME về đợt tiếp theo."
        )
    },
    # 28: Mục 7.3 Miễn thi ngoại ngữ: Bằng đại học tiếng Anh
    {
        "chunk_index": 28,
        "section": "Mục 7.3 – Miễn thi ngoại ngữ: Bằng đại học tiếng Anh [VB2]",
        "title": "Đối tượng miễn thi ngoại ngữ chuẩn đầu ra có bằng đại học",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "miễn thi ngoại ngữ, bằng đại học tiếng anh, đại học nước ngoài",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Đối tượng miễn thi ngoại ngữ chuẩn đầu ra có bằng đại học:\n"
            "(Lưu ý: Dẫn từ thông báo tuyển sinh cao học 2010, chưa được xác nhận chính thức cho chuẩn đầu ra ĐH, cần hỏi Phòng Đào tạo hoặc Trung tâm NNTH):\n"
            "1. Có bằng tốt nghiệp đại học chính quy ngành tiếng Anh; hoặc có bằng tốt nghiệp đại học tại nước ngoài mà ngôn ngữ dùng trong đào tạo là tiếng Anh.\n"
            "2. Có bằng tốt nghiệp đại học tại các CTĐT trong nước mà ngôn ngữ dùng trong toàn bộ chương trình là tiếng Anh không qua phiên dịch."
        )
    },
    # 29: Mục 7.3 Miễn thi ngoại ngữ: Chứng chỉ quốc tế
    {
        "chunk_index": 29,
        "section": "Mục 7.3 – Miễn thi ngoại ngữ: Chứng chỉ quốc tế TOEFL/IELTS [VB2]",
        "title": "Đối tượng miễn thi ngoại ngữ có chứng chỉ quốc tế TOEFL, IELTS",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "miễn thi ngoại ngữ, toefl itp 400, ibt 32, ielts 4.5, thời hạn 2 năm",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Miễn thi ngoại ngữ với chứng chỉ quốc tế:\n"
            "(Lưu ý: Chưa được xác nhận chính thức cho ĐH, cần hỏi Phòng Đào tạo):\n"
            "1. Có chứng chỉ TOEFL ITP 400, iBT 32 hoặc IELTS 4.5 trở lên trong thời hạn 2 năm kể từ ngày cấp đến ngày nộp hồ sơ.\n"
            "2. Có chứng chỉ do các cơ sở đào tạo ngoại ngữ được Bộ Giáo dục và Đào tạo giao nhiệm vụ và công nhận tương đương các mức trên."
        )
    },
    # 30: Mục 7.4 Quy định GDQP-AN và Giáo dục thể chất
    {
        "chunk_index": 30,
        "section": "Mục 7.4 – Quy định GDQP-AN và Giáo dục thể chất [VB1]",
        "title": "Quy định hoàn thành GDQP-AN và 3 học phần GDTC",
        "source": "VB1 – QĐ 22 Điều 4, 11, 15",
        "verified": True,
        "keywords": "giáo dục quốc phòng, gdqp, giáo dục thể chất, gdtc, 102002, 102003, 102004, điểm P",
        "content": (
            "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 4, 11, 15 | Trạng thái: Chính thức]\n"
            "Quy định Giáo dục quốc phòng – an ninh và Thể chất:\n"
            "1. Giáo dục quốc phòng – an ninh (GDQP-AN): Bắt buộc để xét tốt nghiệp đại học; học tập trung đầu khóa / học kỳ 1 (VB1 không nêu điều kiện miễn).\n"
            "2. Giáo dục thể chất (GDTC): Gồm 3 học phần (102002 GDTC 1, 102003 GDTC 2, 102004 GDTC 3), 0 tín chỉ trong CTĐT. Điều kiện đạt là điểm P (từ 5.0 trở lên); không tính vào GPA nhưng bắt buộc hoàn thành đủ cả 3 học phần để được xét tốt nghiệp."
        )
    },
    # 31: Mục 7.4 Lịch học GDQP-AN và tra cứu lịch
    {
        "chunk_index": 31,
        "section": "Mục 7.4 – Lịch học GDQP-AN và tra cứu lịch [VB2]",
        "title": "Lịch học GDQP-AN và trang tra cứu lịch calen.lhu.edu.vn",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "lịch học gdqp, calen.lhu.edu.vn, 28/7/2025, 1 năm 1 lần",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Lịch học GDQP-AN:\n"
            "(Lưu ý: Thông tin lịch học cần tra cứu lại trên cổng chính thức của trường):\n"
            "1. Lịch học GDQP-AN bắt đầu dời sang ngày 28/7/2025 (lịch cũ là 14/7/2025), tra cứu tại https://calen.lhu.edu.vn\n"
            "2. Lịch GDQP chỉ mở 1 năm/lần, quá hạn phải đăng ký vào năm sau."
        )
    },
    # 32: Mục 7.4 Danh mục 4 môn Kỹ năng mềm chuẩn đầu ra
    {
        "chunk_index": 32,
        "section": "Mục 7.4 – Danh mục 4 môn Kỹ năng mềm chuẩn đầu ra [VB2]",
        "title": "Danh mục 4 môn Kỹ năng mềm bắt buộc chuẩn đầu ra",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "kỹ năng mềm, 4 kỹ năng, giải quyết vấn đề, thuyết trình, viết cv, khởi nghiệp",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Danh mục 4 môn Kỹ năng mềm chuẩn đầu ra:\n"
            "(Lưu ý: VB1 chỉ quy định hoàn thành KNM là điều kiện tốt nghiệp, không có danh mục môn cụ thể; danh mục dưới đây từ văn bản tóm tắt chưa kiểm chứng, bạn nên hỏi giáo vụ khoa):\n"
            "1. Kỹ năng giải quyết vấn đề và ra quyết định\n"
            "2. Kỹ năng thuyết trình hiệu quả\n"
            "3. Kỹ năng viết CV điện tử và trả… (văn bản gốc bị cắt dở chữ 'và trả...', chưa xác nhận tên đầy đủ)\n"
            "4. Kỹ năng khởi nghiệp"
        )
    },
    # 33: Mục 7.4 Học phí Kỹ năng mềm 500.000đ và đóng qua AppMe
    {
        "chunk_index": 33,
        "section": "Mục 7.4 – Học phí Kỹ năng mềm 500.000đ và đóng qua AppMe [VB2]",
        "title": "Mức học phí Kỹ năng mềm 500.000đ và hình thức đóng tiền qua AppMe",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "học phí kỹ năng mềm, 500.000, AppMe, đóng tiền",
        "content": (
            "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
            "Học phí Kỹ năng mềm:\n"
            "1. Mức học phí: 500.000 VNĐ / môn là học phí KỸ NĂNG MỀM (áp dụng Khóa 2023, 2024, 2025). Tài liệu hiện có không nêu mức học phí học lại của các môn học khác.\n"
            "2. Hình thức đóng tiền: Sinh viên đóng tiền trực tiếp trên AppMe theo hướng dẫn đính kèm."
        )
    },
    # 34: Mục 7.5 Danh bạ liên hệ Khoa CNTT
    {
        "chunk_index": 34,
        "section": "Mục 7.5 – Danh bạ liên hệ Khoa CNTT [VB2]",
        "title": "Thông tin liên hệ Khoa Công nghệ thông tin LHU",
        "source": "[VB2 – chưa kiểm chứng]",
        "verified": False,
        "keywords": "danh bạ, liên hệ, khoa công nghệ thông tin, cntt@lhu.edu.vn, 02513.952.251, B301, B302, cơ sở 1",
        "content": (
            "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
            "Thông tin liên hệ Khoa Công nghệ thông tin (Mã ngành: 7480201):\n"
            "- Số điện thoại liên hệ: 02513.952.251\n"
            "- Email tiếp nhận: cntt@lhu.edu.vn\n"
            "- Địa chỉ văn phòng: Phòng B301, B302, Tầng 3, Dãy nhà B, Cơ sở 1, Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai.\n"
            "- Khi cần liên hệ hỗ trợ: Ghi rõ Họ tên, MSSV, Khóa, Lớp, Ngành và mô tả chi tiết vấn đề cần giải quyết."
        )
    },
    # 35: Mục 8.1 Điểm xung đột về điểm F, thi lại và cải thiện điểm
    {
        "chunk_index": 35,
        "section": "Mục 8.1 – Điểm xung đột về điểm F, thi lại và cải thiện điểm [Hợp nhất]",
        "title": "Đối chiếu xung đột về ngưỡng điểm F, kỳ thi phụ và tính điểm",
        "source": "VB1 (Niên giám 2023) & VB2 (Tóm tắt quy định)",
        "verified": True,
        "keywords": "điểm xung đột, mục 8, ngưỡng f dưới 4.0 hay dưới 5, thi phụ 2 tuần hay thi lần 2 đầu kỳ mới, tính điểm lần cuối hay cao nhất",
        "content": (
            "[Nguồn: Đối chiếu giữa VB1 – Niên giám 2023 và VB2 – Tóm tắt quy định | Trạng thái: Hợp nhất]\n"
            "Đối chiếu điểm xung đột về đào tạo:\n"
            "1. Ngưỡng F: VB1 quy định F là dưới 4.0; VB2 ghi dưới 5 phải học lại.\n"
            "2. Thi lại / kỳ thi phụ: VB1 tổ chức sớm nhất 2 tuần sau thi chính cho môn điểm < 4.0; VB2 ghi thi lần 2 vào đầu học kỳ mới cho môn điểm < 5.\n"
            "3. Tính điểm học lại / cải thiện: VB1 lấy điểm lần học cuối; VB2 ghi lấy điểm cao nhất các lần học.\n"
            "=> Sinh viên thực hiện theo VB1 và xác nhận với giáo vụ khoa."
        )
    },
    # 36: Mục 8.2 Điểm xung đột về kênh đăng ký và môn tốt nghiệp
    {
        "chunk_index": 36,
        "section": "Mục 8.2 – Điểm xung đột về kênh đăng ký và môn tốt nghiệp [Hợp nhất]",
        "title": "Đối chiếu xung đột về kênh đăng ký và môn tốt nghiệp",
        "source": "VB1 (Niên giám 2023) & VB2 (Tóm tắt quy định)",
        "verified": True,
        "keywords": "điểm xung đột, dkmh.lhu.edu.vn, google form, mác lênin, tư tưởng hồ chí minh, kỹ năng mềm",
        "content": (
            "[Nguồn: Đối chiếu giữa VB1 – Niên giám 2023 và VB2 – Tóm tắt quy định | Trạng thái: Hợp nhất]\n"
            "Đối chiếu điểm xung đột về kênh và môn tốt nghiệp:\n"
            "1. Kênh đăng ký học lại: VB1 quy định trên dkmh.lhu.edu.vn; VB2 dùng Google Form và nhóm Zalo (chưa kiểm chứng).\n"
            "2. Môn tốt nghiệp: VB1 không có kỳ thi riêng môn Mác-Lênin, Tư tưởng HCM (là môn trong CTĐT), bắt buộc Tin học, Ngoại ngữ, Kỹ năng mềm; VB2 yêu cầu đạt Mác-Lênin, Tư tưởng HCM và không nêu cụ thể chuẩn KNM.\n"
            "=> Sinh viên ưu tiên theo VB1 và liên hệ khoa."
        )
    }
    ]
    return chunks


def ingest_quy_dinh(docx_path: str = None, dry_run: bool = False) -> int:
    """Nạp các chunk quy định vào cơ sở dữ liệu (idempotent, chỉ xóa và nạp lại document_id 9001)."""
    if docx_path is None:
        docx_path = find_docx_file()

    print(f"--> Đang đọc file docx: {docx_path}")
    chunks = parse_docx_chunks(docx_path)
    print(f"--> Đã phân tách thành công {len(chunks)} chunks quy định.")

    print(f"--> Đang tạo vector embedding (bge-m3, 1024-dim) cho {len(chunks)} chunks...")
    texts_to_embed = [c["content"] for c in chunks]
    embeddings = get_embeddings_batch(texts_to_embed)
    print(f"--> Đã tạo xong {len(embeddings)} embeddings.")

    if dry_run:
        print("--> Chế độ DRY-RUN: Không ghi vào database.")
        return len(chunks)

    engine = create_engine(settings.DATABASE_URL)
    with engine.begin() as conn:
        # 1. Đảm bảo bảng documents có record với id = DOCUMENT_ID_QUY_DINH
        doc_exists = conn.execute(
            text("SELECT id FROM documents WHERE id = :did"),
            {"did": DOCUMENT_ID_QUY_DINH}
        ).fetchone()

        if not doc_exists:
            target_doc_id = DOCUMENT_ID_QUY_DINH
            try:
                conn.execute(text("SET IDENTITY_INSERT documents ON"))
                conn.execute(
                    text("""
                        INSERT INTO documents (id, title, source, status, so_hieu, url)
                        VALUES (:id, :title, :source, 'indexed', :so_hieu, :url)
                    """),
                    {
                        "id": target_doc_id,
                        "title": DOCUMENT_TITLE,
                        "source": DOCUMENT_SOURCE,
                        "so_hieu": DOCUMENT_SO_HIEU,
                        "url": DOCUMENT_URL
                    }
                )
                conn.execute(text("SET IDENTITY_INSERT documents OFF"))
            except Exception:
                res_ins = conn.execute(
                    text("""
                        INSERT INTO documents (title, source, status, so_hieu, url)
                        OUTPUT INSERTED.id
                        VALUES (:title, :source, 'indexed', :so_hieu, :url)
                    """),
                    {
                        "title": DOCUMENT_TITLE,
                        "source": DOCUMENT_SOURCE,
                        "so_hieu": DOCUMENT_SO_HIEU,
                        "url": DOCUMENT_URL
                    }
                )
                target_doc_id = res_ins.scalar()
        else:
            target_doc_id = DOCUMENT_ID_QUY_DINH
            conn.execute(
                text("UPDATE documents SET status = 'indexed', title = :title, source = :source, so_hieu = :so_hieu, url = :url WHERE id = :id"),
                {
                    "id": target_doc_id,
                    "title": DOCUMENT_TITLE,
                    "source": DOCUMENT_SOURCE,
                    "so_hieu": DOCUMENT_SO_HIEU,
                    "url": DOCUMENT_URL
                }
            )

        # Đảm bảo cột verified tồn tại trong document_chunks (tương ứng migration_add_verified_to_document_chunks.sql)
        col_verified_exists = conn.execute(
            text("SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'document_chunks' AND COLUMN_NAME = 'verified'")
        ).fetchone()
        if not col_verified_exists:
            conn.execute(text("ALTER TABLE document_chunks ADD verified BIT NOT NULL CONSTRAINT DF_document_chunks_verified DEFAULT 1"))

        # 2. Xóa CHỈ các chunk cũ của document 9001 để đảm bảo idempotent
        conn.execute(
            text("DELETE FROM document_chunks WHERE document_id = :did"),
            {"did": target_doc_id}
        )

        # 3. Chèn các chunk mới kèm embedding và cờ verified
        for idx, c in enumerate(chunks):
            conn.execute(
                text("""
                    INSERT INTO document_chunks (document_id, chunk_index, content, embedding, section, verified)
                    VALUES (:did, :idx, :content, :emb, :sec, :ver)
                """),
                {
                    "did": target_doc_id,
                    "idx": idx,
                    "content": c["content"],
                    "emb": embeddings[idx],
                    "sec": c["section"],
                    "ver": 1 if c.get("verified", True) else 0
                }
            )

        print(f"--> Đã nạp thành công {len(chunks)} chunks vào bảng document_chunks (document_id = {target_doc_id}).")
        return len(chunks)


def main():
    parser = argparse.ArgumentParser(description="Nạp văn bản quy chế đào tạo hợp nhất vào RAG")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ phân tích và tạo embedding, không ghi vào database")
    args = parser.parse_args()

    try:
        cnt = ingest_quy_dinh(dry_run=args.dry_run)
        print(f"=== HOÀN TẤT NẠP DỮ LIỆU: {cnt} CHUNKS ===")
    except Exception as e:
        print(f"Lỗi khi nạp quy định: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
