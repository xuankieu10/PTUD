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
        # Chunk 0: Mục 1 - Thang điểm, cơ cấu điểm và điểm 0 (VB1)
        {
            "chunk_index": 0,
            "section": "Mục 1 – Thang điểm và điểm 0 [VB1 – Điều 11, Điều 12]",
            "title": "Thang điểm 10, thang chữ, thang 4 và các trường hợp bị điểm 0",
            "source": "VB1 – QĐ 22/QĐ-ĐHLH, Điều 11 Khoản 5, Điều 12 Khoản 2",
            "verified": True,
            "keywords": "thang điểm, thang 10, thang chữ, thang 4, điểm F, điểm D, điểm P, điểm liệt, cơ cấu điểm, điểm 0",
            "content": (
                "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH, Điều 11 Khoản 5, Điều 12 Khoản 2 | Trạng thái: Chính thức]\n"
                "Quy định thang điểm và đánh giá kết quả học tập:\n"
                "1. Thang điểm đánh giá học phần:\n"
                "- Điểm A (8.5 – 10.0, thang 4: 4.0): Đạt (Xuất sắc / Giỏi)\n"
                "- Điểm B+ (8.0 – 8.4, thang 4: 3.5): Đạt (Khá giỏi)\n"
                "- Điểm B (7.0 – 7.9, thang 4: 3.0): Đạt (Khá)\n"
                "- Điểm C+ (6.5 – 6.9, thang 4: 2.5): Đạt (Trung bình khá)\n"
                "- Điểm C (5.5 – 6.4, thang 4: 2.0): Đạt (Trung bình)\n"
                "- Điểm D+ (5.0 – 5.4, thang 4: 1.5): Đạt (Trung bình yếu)\n"
                "- Điểm D (4.0 – 4.9, thang 4: 1.0): Đạt\n"
                "- Điểm F (Dưới 4.0, thang 4: 0.0): Không đạt (phải học lại hoặc thi lại)\n"
                "2. Điểm đặc biệt:\n"
                "- Điểm P: Đạt, không phân mức (từ 5.0 trở lên), dùng cho học phần chỉ yêu cầu đạt (như Giáo dục thể chất), không tính vào điểm trung bình.\n"
                "- Điểm I (chưa hoàn thiện do hoãn thi), X (chưa đủ dữ liệu), R (được miễn học và công nhận tín chỉ).\n"
                "3. Cơ cấu điểm học phần: Quá trình 30%, Giữa kỳ 30%, Cuối kỳ 40%. Điểm liệt của từng điểm thành phần là 0.\n"
                "4. Các trường hợp bị điểm 0: Tự ý bỏ học; rút bớt học phần không đúng thời hạn 2 tuần; vắng thi, vắng đánh giá không có lý do chính đáng; gian lận trong thi cử."
            )
        },
        # Chunk 1: Mục 2 - Điều kiện cấm thi (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 1,
            "section": "Mục 2 – Điều kiện cấm thi [VB2 – Điều 19]",
            "title": "Điều kiện cấm thi kết thúc học phần",
            "source": "[VB2 – chưa kiểm chứng – Điều 19]",
            "verified": False,
            "keywords": "cấm thi, vắng quá 20%, điểm thành phần dưới 2.0, chuyên cần, giữa kỳ, không được dự thi",
            "content": (
                "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
                "Điều kiện cấm thi kết thúc học phần:\n"
                "(Lưu ý: Thông tin này chưa được xác nhận chính thức trong Niên giám chính thức VB1; bạn nên hỏi giáo vụ khoa để được hướng dẫn chính xác nhất):\n"
                "1. Vắng mặt: Sinh viên vắng mặt quá 20% số tiết của học phần (lý thuyết hoặc thực hành) sẽ không được dự thi kết thúc học phần đó và phải nhận điểm 0 ở phần thi kết thúc học phần hoặc bị cấm thi tùy quy định cụ thể.\n"
                "2. Điểm thành phần: Điểm đánh giá bộ phận (điểm chuyên cần, kiểm tra giữa kỳ) đạt điểm dưới 2.0 (thang 10) thì không đủ điều kiện dự thi kết thúc học phần (bị cấm thi)."
            )
        },
        # Chunk 2: Mục 3.1 - Học lại (VB1)
        {
            "chunk_index": 2,
            "section": "Mục 3.1 – Học lại [VB1 – Điều 12]",
            "title": "Quy định học lại học phần và tính điểm học lại",
            "source": "VB1 – QĐ 22, Điều 3 K1, Điều 7 K5, Điều 9 K1, Điều 11 K5đ, Điều 12",
            "verified": True,
            "keywords": "học lại, điểm F, dưới 4.0, học phần bắt buộc, học phần tự chọn, lần học cuối",
            "content": (
                "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH, Điều 3 K1, Điều 7 K5, Điều 9 K1, Điều 11 K5đ | Trạng thái: Chính thức]\n"
                "Quy định học lại học phần:\n"
                "1. Học phần bắt buộc bị điểm F (dưới 4.0): Phải đăng ký học lại, hoặc học phần tương đương/thay thế, ở các học kỳ tiếp theo cho đến khi đạt (từ điểm D / 4.0 trở lên).\n"
                "2. Học phần tự chọn bị điểm F: Sinh viên học lại học phần đó hoặc đổi sang học phần tự chọn tương đương khác theo quy định CTĐT.\n"
                "3. Cách tính điểm: Điểm của lần học cuối là điểm chính thức của học phần (không quy định lấy điểm cao nhất). Không quy định giới hạn số lần học lại tối đa.\n"
                "Lưu ý điểm xung đột (Mục 8): Theo Niên giám chính thức (VB1), điểm F là dưới 4.0 và tính điểm lần học cuối; tuy nhiên có văn bản khác (VB2) ghi dưới 5 phải học lại và tính điểm cao nhất các lần học. Thông tin này cần xác nhận lại với giáo vụ khoa."
            )
        },
        # Chunk 3: Mục 3.2 - Thi lại (Kỳ thi phụ) (VB1 & VB2)
        {
            "chunk_index": 3,
            "section": "Mục 3.2 – Thi lại (kỳ thi phụ) [VB1 – Điều 11]",
            "title": "Quy định thi lại và kỳ thi phụ cuối kỳ",
            "source": "VB1 – QĐ 22 & [VB2 – chưa kiểm chứng]",
            "verified": True,
            "keywords": "thi lại, kỳ thi phụ, thi lần 2, vắng thi, điểm F, 2 tuần sau thi chính, đầu học kỳ mới, điều kiện thi lại, khi nào được thi lại",
            "content": (
                "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH Điều 11 K5đ & [VB2 – chưa kiểm chứng]]\n"
                "Điều kiện và quy định thi lại (kỳ thi phụ):\n"
                "1. Theo VB1 (Chính thức):\n"
                "- Điều kiện dự thi phụ/thi lại: Sinh viên không dự kỳ thi chính hoặc có điểm học phần dưới 4.0 (điểm F) ở kỳ thi chính.\n"
                "- Thời gian tổ chức: Kỳ thi phụ được tổ chức sớm nhất 02 tuần sau kỳ thi chính.\n"
                "- Vắng thi chính có lý do chính đáng: Được dự thi phụ ngay sau đó và điểm thi phụ được tính là điểm thi lần đầu.\n"
                "2. Theo [VB2 – chưa kiểm chứng]:\n"
                "- Kỳ thi lần 2 (thi lại lần 2) tổ chức vào đầu học kỳ mới cho học phần dưới 5; điểm chuyên cần và giữa kỳ KHÔNG có thi lần 2.\n"
                "Lưu ý điểm xung đột (Mục 8): VB1 tổ chức thi phụ sớm nhất 2 tuần sau thi chính cho môn điểm < 4.0; VB2 ghi thi lần 2 (thi lại lần 2) vào đầu học kỳ mới cho môn điểm < 5. Sinh viên nên theo dõi thông báo chính thức của Phòng Đào tạo hoặc hỏi giáo vụ khoa."
            )
        },
        # Chunk 4: Mục 3.3 - Cải thiện điểm (VB1 & VB2)
        {
            "chunk_index": 4,
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
        # Chunk 5: Mục 4 - Cảnh báo học vụ và buộc thôi học (VB1 & VB2)
        {
            "chunk_index": 5,
            "section": "Mục 4 – Cảnh báo học vụ, dừng học và buộc thôi học [VB1 – Điều 13, 19, 21]",
            "title": "Cảnh báo học vụ, tạm ngừng học và buộc thôi học",
            "source": "VB1 – QĐ 22, Điều 13, 19, 21 & [VB2 – chưa kiểm chứng]",
            "verified": True,
            "keywords": "cảnh báo học vụ, dừng học, buộc thôi học, rèn luyện yếu, thi hộ, bằng giả, 1.2, 1.4, 1.6, 1.8",
            "content": (
                "[Nguồn: VB1 – Điều 13, 19, 21; QĐ 840 Điều 13 & [VB2 – chưa kiểm chứng]]\n"
                "Quy định cảnh báo học vụ, tạm ngừng học và buộc thôi học:\n"
                "1. Theo VB1 (Chính thức):\n"
                "- Cảnh báo học vụ thực hiện theo từng học kỳ để sinh viên biết và lập phương án học tập. Ngưỡng cảnh báo cụ thể theo quy định xử lý học vụ riêng của Trường.\n"
                "- Dừng học chương trình thứ hai: Sinh viên học cùng lúc 2 chương trình nếu điểm trung bình tích lũy chương trình 1 dưới 5.0 hoặc thuộc diện cảnh báo thì phải dừng học chương trình 2 ở học kỳ tiếp theo.\n"
                "- Rèn luyện yếu/kém 2 học kỳ liên tiếp: Tạm ngừng học ít nhất 01 năm; lặp lại lần 2 thì buộc thôi học.\n"
                "- Thi hộ / nhờ thi hộ: Đình chỉ học tập 01 năm (lần 1); buộc thôi học (lần 2).\n"
                "- Dùng hồ sơ, văn bằng, chứng chỉ giả: Buộc thôi học, văn bằng đã cấp bị thu hồi.\n"
                "2. Theo [VB2 – chưa kiểm chứng]: Điểm trung bình tích lũy dưới ngưỡng 'thường là' dưới 1.2 (năm 1), 1.4 (năm 2), 1.6 (năm 3), 1.8 (các năm sau); Buộc thôi học nếu cảnh báo liên tiếp 2 học kỳ chính hoặc quá 12–13 học kỳ (thông tin này chưa được xác nhận chính thức trong văn bản gốc)."
            )
        },
        # Chunk 6: Mục 5 - Điều kiện xét tốt nghiệp đại học (VB1)
        {
            "chunk_index": 6,
            "section": "Mục 5 – Điều kiện xét tốt nghiệp [VB1 – Điều 15]",
            "title": "Điều kiện xét tốt nghiệp đại học ngành CNTT",
            "source": "VB1 – QĐ 22, Điều 15 K1đ, K2; Điều 4 K2a; Điều 11 K5b",
            "verified": True,
            "keywords": "xét tốt nghiệp, điều kiện tốt nghiệp, 150 tín chỉ, 8 học kỳ, chuẩn đầu ra, gdqp, gdtc, tin học, ngoại ngữ, kỹ năng mềm",
            "content": (
                "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH, Điều 15 K1đ, Khoản 2; Điều 4 K2a; Điều 11 K5b | Trạng thái: Chính thức]\n"
                "Điều kiện xét tốt nghiệp đại học chính thức (VB1 – Điều 15):\n"
                "1. Tích lũy đủ 150 tín chỉ của chương trình đào tạo (8 học kỳ), không còn học phần không đạt (không còn môn điểm F dưới 4.0).\n"
                "2. Có Chứng chỉ Giáo dục quốc phòng – an ninh và hoàn thành 3 học phần Giáo dục thể chất (đạt điểm P, từ 5.0 trở lên).\n"
                "3. Đạt chuẩn trình độ tin học – ngoại ngữ theo quy định của Trường.\n"
                "4. Hoàn thành chương trình đào tạo Kỹ năng mềm.\n"
                "5. Cấp bằng tốt nghiệp trong vòng 03 tháng kể từ khi sinh viên đủ điều kiện.\n"
                "Theo [VB2 – chưa kiểm chứng]: Không đang bị truy cứu trách nhiệm hình sự; đạt các môn Mác-Lênin, Tư tưởng Hồ Chí Minh; nhà trường xét tốt nghiệp sau mỗi học kỳ theo thông báo của Phòng Đào tạo.\n"
                "Lưu ý điểm xung đột (Mục 8): VB1 không có kỳ thi tốt nghiệp riêng cho các môn Mác-Lênin hay Tư tưởng HCM mà đây là các môn học bình thường trong CTĐT; đồng thời VB1 bắt buộc chuẩn Ngoại ngữ, Tin học, Kỹ năng mềm."
            )
        },
        # Chunk 7: Mục 6.1, 6.2 - Hệ thống đăng ký và cổng thông tin trực tuyến (VB1)
        {
            "chunk_index": 7,
            "section": "Mục 6.1, 6.2 – Cổng thông tin và đăng ký môn học [VB1 – Điều 7]",
            "title": "Hệ thống đăng ký môn học và các cổng thông tin sinh viên LHU",
            "source": "VB1 – Điều 7 K1; Niên giám 2023 tr. 128–138",
            "verified": True,
            "keywords": "dkmh.lhu.edu.vn, app.lhu.edu.vn, me.lhu.edu.vn, hocphi.lhu.edu.vn, mssv, sms, rút học phần, 2 tuần",
            "content": (
                "[Nguồn: VB1 – Điều 7 K1; Niên giám 2023 tr. 128–138 | Trạng thái: Chính thức]\n"
                "Hệ thống trực tuyến và đăng ký môn học:\n"
                "1. Cổng đăng ký môn học trực tuyến chính thức: https://dkmh.lhu.edu.vn (thực hiện theo kế hoạch của Phòng Đào tạo trước/đầu mỗi học kỳ).\n"
                "2. Trang thông tin cá nhân: https://app.lhu.edu.vn hoặc http://me.lhu.edu.vn (Me App).\n"
                "3. Đăng nhập: Tên đăng nhập là Mã số sinh viên (MSSV). Mật khẩu ban đầu gửi qua SMS đến số điện thoại trong hồ sơ nhập học hoặc in trên hóa đơn học phí. Sinh viên phải cập nhật đầy đủ số điện thoại và email trên Me App trước khi sử dụng.\n"
                "4. Tra cứu nợ học phí: https://hocphi.lhu.edu.vn.\n"
                "5. Rút bớt học phần: Thời hạn 2 tuần kể từ khi học phần được triển khai; ngoài thời hạn sinh viên tự ý bỏ học sẽ bị điểm 0.\n"
                "6. Thời gian đăng ký học lại / cải thiện điểm thực hiện theo các học kỳ chính hoặc học kỳ phụ (hè) do Trường ấn định trên cổng thông tin sinh viên."
            )
        },
        # Chunk 8: Mục 6.3 - Đăng ký học lại, học vét qua Google Form (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 8,
            "section": "Mục 6.3 – Hướng dẫn đăng ký học lại, học vét [VB2]",
            "title": "Kênh đăng ký học lại, học vét và chi phí tham khảo",
            "source": "[VB2 – chưa kiểm chứng]",
            "verified": False,
            "keywords": "học lại, học vét, google form, zalo, app me, chi phí học lại, forms.gle",
            "content": (
                "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
                "Kênh đăng ký học lại, học vét và chi phí tham khảo:\n"
                "(Lưu ý: VB1 Niên giám quy định đăng ký hoàn toàn trực tuyến trên dkmh.lhu.edu.vn; kênh Google Form/Zalo dưới đây là kênh phụ trợ từ văn bản tóm tắt chưa được xác nhận chính thức, bạn nên hỏi giáo vụ khoa để được hướng dẫn chính xác):\n"
                "1. Hình thức đăng ký học lại: Đăng ký trực tuyến qua Google Form: https://forms.gle/iBk3hNwG4SCGKMEFA\n"
                "2. Nhóm Zalo hỗ trợ: https://zalo.me/g/ar6b85p9opfxctwhxwpd\n"
                "3. Về lớp học vét: Hiện tại tài liệu hiện có không đề cập riêng về lớp học vét; sinh viên có nhu cầu học lại thực hiện theo quy trình đăng ký học lại thông thường.\n"
                "4. Học phí học lại: Sinh viên xem bảng danh sách môn học lại và chi phí tham khảo tại link: https://docs.google.com/spreadsheets/d/1LBSioDaeoHSclt4R4yXpO0aFR-6kkTk9/edit?usp=sharing&ouid=103838733389649116635&rtpof=true&sd=true (Lưu ý quan trọng: Tài liệu hiện có không nêu mức học phí học lại cụ thể; mức 500.000đ/môn là học phí KỸ NĂNG MỀM, không áp dụng cho học lại môn học thông thường).\n"
                "5. Nếu mẫu đơn đã quá thời hạn đăng ký, sinh viên vui lòng theo dõi trên App ME về đợt học lại tiếp theo."
            )
        },
        # Chunk 9: Mục 6.6 & Bảng 1 - Các thủ tục và mẫu đơn hành chính (VB1)
        {
            "chunk_index": 9,
            "section": "Mục 6.6 – Thủ tục hành chính và mẫu đơn [VB1 – Điều 16]",
            "title": "Thủ tục hành chính, cấp giấy chứng nhận online và Phòng Công tác sinh viên",
            "source": "VB1 – QĐ 22, Điều 16 K3; QĐ 406 tr. 118–120, 135",
            "verified": True,
            "keywords": "giấy chứng nhận online, vay vốn, miễn giảm học phí, phòng ctsv, D201, cơ sở 2, certification.lhu.edu.vn, sinhviendanghoc.lhu.edu.vn",
            "content": (
                "[Nguồn: VB1 – QĐ 22 Điều 16 K3; QĐ 406 tr. 118–120, 135 | Trạng thái: Chính thức]\n"
                "Thủ tục hành chính và dịch vụ sinh viên:\n"
                "1. Cấp giấy chứng nhận online: Đăng ký trực tuyến tại http://certification.lhu.edu.vn theo hướng dẫn trên hệ thống.\n"
                "2. Giấy xác nhận vay vốn sinh viên (Mẫu 01-TDSV theo QĐ 157/2007/QĐ-TTg): Nộp trực tuyến tại https://sinhviendanghoc.lhu.edu.vn hoặc nộp trực tiếp tại Phòng Công tác sinh viên (Phòng D201, Cơ sở 2). Kèm thẻ SV, CCCD, biên lai học phí kỳ gần nhất.\n"
                "3. Miễn giảm học phí, ưu đãi giáo dục (Mẫu 41 / Phụ lục VIII NĐ 81/2021): Nộp tại Phòng Công tác sinh viên (Phòng D201, Cơ sở 2); viết bút xanh, không tẩy xóa. Kèm thẻ SV, CCCD, biên lai học phí.\n"
                "4. Xin trở lại học sau nghỉ tạm thời: Đơn viết gửi Hiệu trưởng, nộp tại Trường trước kỳ học mới ít nhất 1 tuần."
            )
        },
        # Chunk 10: Mục 7.1 - Chương trình đào tạo CNTT 150 tín chỉ (VB1)
        {
            "chunk_index": 10,
            "section": "Mục 7.1 – CTĐT ngành CNTT 150 tín chỉ [VB1]",
            "title": "Khung chương trình đào tạo ngành Công nghệ thông tin (150 tín chỉ, 8 học kỳ)",
            "source": "VB1 – Niên giám 2023 (Khóa 2023–2027)",
            "verified": True,
            "keywords": "chương trình đào tạo, ctđt cntt, 150 tín chỉ, 8 học kỳ, danh mục môn học, mã học phần, tiên quyết, bắt buộc, tự chọn",
            "content": (
                "[Nguồn: VB1 – Niên giám 2023 | Trạng thái: Chính thức]\n"
                "Chương trình đào tạo ngành Công nghệ thông tin (Mã ngành: 7480201) – Niên khóa 2023–2027 (Tổng cộng 150 tín chỉ, 8 học kỳ):\n"
                "- Học kỳ 1 (17 TC): Giáo dục quốc phòng (-), 102002 Giáo dục thể chất 1 (0 TC), 102073 Toán cao cấp 1 (4 TC), 102074 English 1 (3 TC), 111094 Nhập môn lập trình (2 TC), 111001 Cấu trúc và lắp ráp máy tính (3 TC), 111080 Phần mềm mã nguồn mở (2 TC), 111055 Nhập môn Công nghệ thông tin (1 TC), 111053 Nhập môn Phát triển dự án kỹ thuật (2 TC).\n"
                "- Học kỳ 2 (20 TC): 102003 Giáo dục thể chất 2 (0 TC), 102087 Xác suất thống kê (2 TC), 102075 English 2 (4 TC), 102014 Tin học đại cương (3 TC), 111046 Vật lý thực hành (3 TC), 111047 Điện tử cơ bản (2 TC), 111056 Thiết kế UI/UX (2 TC), 111058 Kỹ thuật lập trình (2 TC), 112061 Mạng máy tính (2 TC).\n"
                "- Học kỳ 3 (25 TC): 102004 Giáo dục thể chất 3 (0 TC), 102063 Triết học Mác - Lênin (3 TC), 102064 Kinh tế chính trị Mác - Lênin (2 TC), 102065 Chủ nghĩa xã hội khoa học (2 TC), 102076 English 3 (4 TC), 111010 Toán rời rạc (3 TC), 111062 Cấu trúc dữ liệu và giải thuật (3 TC), 111048 Tín hiệu số cơ bản (2 TC), 111059 Cơ sở dữ liệu (3 TC), 112064 Mạng máy tính nâng cao (3 TC).\n"
                "- Học kỳ 4 (21 TC): 102033 Tư tưởng Hồ Chí Minh (2 TC), 102006 Pháp luật đại cương (2 TC), 102077 English 4 (4 TC), 111036 Dịch vụ mạng (3 TC), 111070 Lập trình hướng đối tượng (3 TC), 111060 Hệ quản trị CSDL (3 TC), 111067 Lập trình Front-End (2 TC), 111081 Kiến tập (2 TC).\n"
                "- Học kỳ 5 (20 TC): 102066 Lịch sử Đảng (2 TC), 102078 English 5 (4 TC), 111057 Nguyên lý thống kê (2 TC), 112065 Thiết kế hệ thống mạng (3 TC), 111066 Lập trình Back-End (3 TC), 111072 Lập trình Windows (3 TC), Tự chọn 3 TC (111043 PT&TK HT HĐT hoặc 111089 PT&TK HT HQR).\n"
                "- Học kỳ 6 (16 TC): 102079 English 6 (4 TC), 112068 Thiết kế HT mạng nâng cao (2 TC), 111069 Lập trình giao tiếp thiết bị (2 TC), 111082 Lập trình ứng dụng di động (3 TC), 111083 Lập trình ứng dụng web (3 TC), Tự chọn 2 TC (111071 Python cho học máy hoặc 111084 Python thị giác MT).\n"
                "- Học kỳ 7 (21 TC): 102080 English 7 (4 TC), 111065 Kiểm thử & ĐBCLPM (3 TC), 111085 Quản trị website trên VPS (2 TC), 111038 Phát triển ứng dụng (9 TC), Tự chọn 3 TC (111088 Trí tuệ nhân tạo hoặc 111061 Công nghệ Blockchain).\n"
                "- Học kỳ 8 (10 TC): 111049 Thực tập (2 TC), 33333 Tốt nghiệp (8 TC).\n"
                "Ghi chú: GDQP không tính tín chỉ; GDTC gồm 3 học phần 0 tín chỉ (điểm P từ 5.0 trở lên); tổng toàn khóa đúng 150 tín chỉ."
            )
        },
        # Chunk 11: Mục 7.3 - Lệ phí và sát hạch Tin học, Ngoại ngữ (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 11,
            "section": "Mục 7.3 – Lệ phí thi chứng chỉ và sát hạch [VB2]",
            "title": "Lệ phí thi chứng chỉ Ngoại ngữ, Tin học và ôn thi sát hạch",
            "source": "[VB2 – chưa kiểm chứng]",
            "verified": False,
            "keywords": "lệ phí thi, vstep, cefr, tin học, sát hạch tin học, 2.000.000, 1.100.000, 600.000, 90.000, forms.gle",
            "content": (
                "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
                "Lệ phí thi chứng chỉ và sát hạch Ngoại ngữ - Tin học:\n"
                "(Lưu ý: VB1 Niên giám chỉ quy định sinh viên phải đạt chuẩn tin học - ngoại ngữ của Trường mà không có bảng lệ phí chi tiết; thông tin này chưa được xác nhận chính thức, bạn nên hỏi giáo vụ khoa hoặc Trung tâm NNTH):\n"
                "1. Lệ phí thi chứng chỉ ngoại ngữ và tin học:\n"
                "- Chứng chỉ Ngoại ngữ 6 bậc (VSTEP): 2.000.000 VNĐ / thí sinh / kỳ thi.\n"
                "- Chứng nhận đánh giá năng lực tiếng Anh (CEFR): 1.100.000 VNĐ / thí sinh / kỳ thi.\n"
                "- Chứng chỉ Ứng dụng công nghệ thông tin: 600.000 VNĐ / thí sinh / kỳ thi.\n"
                "- Thời hạn nộp chứng chỉ tiếng Anh: Nộp trước ngày xét tốt nghiệp tối thiểu 1 tháng.\n"
                "2. Sát hạch tin học:\n"
                "- Phí ôn luyện: 90.000 VNĐ / sinh viên.\n"
                "- Link đăng ký lớp ôn: https://forms.gle/WtUpfZbPiWAq3RqK6\n"
                "- Nhóm Zalo hỗ trợ: https://zalo.me/g/g2elp3xxzxexl5lqjlc0\n"
                "- Nếu quá hạn đăng ký, sinh viên theo dõi trên App ME về đợt tiếp theo."
            )
        },
        # Chunk 12: Mục 7.3 - Đối tượng miễn thi ngoại ngữ (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 12,
            "section": "Mục 7.3 – Miễn thi ngoại ngữ [VB2]",
            "title": "Đối tượng miễn thi chứng chỉ ngoại ngữ chuẩn đầu ra",
            "source": "[VB2 – chưa kiểm chứng]",
            "verified": False,
            "keywords": "miễn thi ngoại ngữ, toefl, ielts, bằng tiếng anh, đại học nước ngoài, 4.5, itp 400, ibt 32",
            "content": (
                "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
                "Đối tượng được miễn thi chứng chỉ ngoại ngữ chuẩn đầu ra:\n"
                "(CẢNH BÁO QUAN TRỌNG: Danh mục miễn thi này dẫn từ thông báo tuyển sinh cao học 2010, chưa được xác nhận chính thức có áp dụng cho chuẩn đầu ra đại học hay không. Sinh viên bắt buộc phải hỏi phòng Đào tạo hoặc Trung tâm NNTH để xác nhận):\n"
                "1. Có bằng tốt nghiệp đại học chính quy ngành tiếng Anh; hoặc có bằng tốt nghiệp đại học tại nước ngoài mà ngôn ngữ dùng trong đào tạo là tiếng Anh.\n"
                "2. Có bằng tốt nghiệp đại học tại các chương trình đào tạo trong nước mà ngôn ngữ dùng trong toàn bộ chương trình là tiếng Anh không qua phiên dịch.\n"
                "3. Có chứng chỉ TOEFL ITP 400, iBT 32 hoặc IELTS 4.5 trở lên trong thời hạn 2 năm kể từ ngày cấp đến ngày nộp hồ sơ.\n"
                "4. Có chứng chỉ do các cơ sở đào tạo ngoại ngữ được Bộ Giáo dục và Đào tạo giao nhiệm vụ và công nhận tương đương các mức trên."
            )
        },
        # Chunk 13: Mục 7.4 - Giáo dục quốc phòng – an ninh và Thể chất (VB1 & VB2)
        {
            "chunk_index": 13,
            "section": "Mục 7.4 – GDQP-AN và Giáo dục thể chất [VB1 – Điều 4, 11, 15]",
            "title": "Quy định hoàn thành Giáo dục quốc phòng - An ninh và Giáo dục thể chất",
            "source": "VB1 – QĐ 22 Điều 4, 11, 15 & [VB2 – chưa kiểm chứng]",
            "verified": True,
            "keywords": "giáo dục quốc phòng, gdqp, giáo dục thể chất, gdtc, 102002, 102003, 102004, điểm P, calen.lhu.edu.vn, 28/7/2025",
            "content": (
                "[Nguồn: VB1 – QĐ 22/QĐ-ĐHLH & [VB2 – chưa kiểm chứng]]\n"
                "Quy định Giáo dục quốc phòng – an ninh và Giáo dục thể chất:\n"
                "1. Theo VB1 (Chính thức):\n"
                "- Giáo dục quốc phòng – an ninh (GDQP-AN): Bắt buộc để xét tốt nghiệp đại học; học tập trung đầu khóa / học kỳ 1 (VB1 không nêu điều kiện miễn).\n"
                "- Giáo dục thể chất (GDTC): Gồm 3 học phần (102002 GDTC 1, 102003 GDTC 2, 102004 GDTC 3), 0 tín chỉ trong CTĐT. Điều kiện đạt là điểm P (từ 5.0 trở lên); không tính vào điểm trung bình nhưng bắt buộc hoàn thành đủ cả 3 học phần để được xét tốt nghiệp.\n"
                "2. Theo [VB2 – chưa kiểm chứng]: Lịch học GDQP-AN bắt đầu dời sang ngày 28/7/2025 (lịch cũ là 14/7/2025), tra cứu tại https://calen.lhu.edu.vn; lịch GDQP chỉ mở 1 năm/lần, quá hạn phải đăng ký vào năm sau (thông tin lịch học cụ thể cần tra cứu lại trên calen.lhu.edu.vn)."
            )
        },
        # Chunk 14: Mục 7.4 - Quy định 4 kỹ năng mềm (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 14,
            "section": "Mục 7.4 – Kỹ năng mềm [VB2]",
            "title": "Quy định 4 kỹ năng mềm bắt buộc chuẩn đầu ra và học phí",
            "source": "[VB2 – chưa kiểm chứng]",
            "verified": False,
            "keywords": "kỹ năng mềm, 4 kỹ năng, giải quyết vấn đề, thuyết trình, viết cv, khởi nghiệp, 500.000, AppMe",
            "content": (
                "[Nguồn: [VB2 – chưa kiểm chứng]]\n"
                "Quy định chuẩn đầu ra Kỹ năng mềm:\n"
                "(Lưu ý: Theo VB1 – Điều 15 K1đ, hoàn thành Kỹ năng mềm là điều kiện bắt buộc xét tốt nghiệp, nhưng VB1 không quy định danh mục môn và mức học phí. Danh mục 4 môn và học phí dưới đây thuộc [VB2 – chưa kiểm chứng], bạn nên hỏi giáo vụ khoa để được hướng dẫn chính xác):\n"
                "1. Danh mục 4 môn kỹ năng mềm:\n"
                "- (1) Kỹ năng giải quyết vấn đề và ra quyết định\n"
                "- (2) Kỹ năng thuyết trình hiệu quả\n"
                "- (3) Kỹ năng viết CV điện tử và trả… (văn bản gốc bị cắt dở chữ 'và trả...', chưa xác nhận tên đầy đủ)\n"
                "- (4) Kỹ năng khởi nghiệp\n"
                "2. Mức học phí Kỹ năng mềm: 500.000 VNĐ / môn là học phí KỸ NĂNG MỀM (áp dụng Khóa 2023, 2024, 2025). Tài liệu hiện có không nêu mức học phí học lại của các môn học thông thường khác.\n"
                "3. Hình thức đóng tiền kỹ năng mềm: Sinh viên đóng tiền trực tiếp trên AppMe theo hướng dẫn đính kèm."
            )
        },
        # Chunk 15: Mục 7.5 - Danh bạ liên hệ Khoa CNTT (VB2 - Chưa kiểm chứng)
        {
            "chunk_index": 15,
            "section": "Mục 7.5 – Danh bạ liên hệ Khoa CNTT [VB2]",
            "title": "Thông tin liên hệ Khoa Công nghệ thông tin LHU",
            "source": "[VB2 – chưa kiểm chứng]",
            "verified": False,
            "keywords": "danh bạ, liên hệ, khoa công nghệ thông tin, cntt@lhu.edu.vn, 02513.952.251, B301, B302, cơ sở 1",
            "content": (
                "[Nguồn: VB2 – Văn bản tóm tắt quy định học vụ | Trạng thái: [VB2 – chưa kiểm chứng]]\n"
                "Thông tin liên hệ Khoa Công nghệ thông tin (Mã ngành: 7480201):\n"
                "- Số điện thoại liên hệ: 02513.952.251\n"
                "- Email: cntt@lhu.edu.vn\n"
                "- Website: http://cs.lhu.edu.vn\n"
                "- Văn phòng Khoa: Phòng B301 - B302, Cơ sở 1, Số 10 Huỳnh Văn Nghệ, Biên Hòa, Đồng Nai (P. Bửu Long, TP. Biên Hòa, Tỉnh Đồng Nai).\n"
                "- Giờ làm việc: Thứ Hai đến Thứ Sáu (Sáng: 7h30 – 11h30 | Chiều: 13h00 – 16h30 / 17h00).\n"
                "Phòng Công tác sinh viên (VB1): Phòng D201, Cơ sở 2 (tiếp nhận xác nhận vay vốn và miễn giảm học phí)."
            )
        },
        # Chunk 16: Mục 8 - Tổng hợp điểm xung đột giữa VB1 và VB2 (Chính thức)
        {
            "chunk_index": 16,
            "section": "Mục 8 – Điểm xung đột giữa VB1 và VB2 [Hợp nhất]",
            "title": "Các điểm xung đột quy định học vụ giữa VB1 và VB2 và nguyên tắc xử lý",
            "source": "Tổng hợp đối chiếu Quy chế đào tạo tín chỉ LHU",
            "verified": True,
            "keywords": "xung đột, so sánh, điểm F, dưới 4.0, dưới 5.0, điểm cao nhất, điểm lần cuối, thi lại, dkmh.lhu.edu.vn, google form, điều 15, điều 27",
            "content": (
                "[Nguồn: Tổng hợp đối chiếu Quy chế đào tạo tín chỉ LHU | Trạng thái: Nguyên tắc xử lý xung đột]\n"
                "Nguyên tắc: Khi hai văn bản có mâu thuẫn thì ưu tiên áp dụng Niên giám chính thức (VB1). Sinh viên cần liên hệ giáo vụ khoa để xác nhận khi gặp các trường hợp sau:\n"
                "1. Ngưỡng đạt / học lại: VB1 quy định F là dưới 4.0, điểm D (4.0–4.9) vẫn đạt; VB2 ghi dưới 5 phải học lại.\n"
                "2. Điểm khi học lại: VB1 tính điểm của lần học cuối là điểm chính thức; VB2 ghi tính điểm cao nhất các lần học.\n"
                "3. Thi lại (kỳ thi phụ): VB1 tổ chức sớm nhất 02 tuần sau kỳ thi chính (cho điểm < 4.0); VB2 ghi thi lần 2 vào đầu học kỳ mới (cho điểm < 5).\n"
                "4. Kênh đăng ký học lại: VB1 quy định trực tuyến trên dkmh.lhu.edu.vn, không có mẫu đơn giấy; VB2 ghi đăng ký qua Google Form, App ME và nhóm Zalo.\n"
                "5. Điều kiện tốt nghiệp: VB1 (Điều 15) yêu cầu chuẩn Tin học – Ngoại ngữ, Kỹ năng mềm, GDQP-AN, 3 môn GDTC (không có kỳ thi riêng Mác-Lênin/TTHCM); VB2 (Điều 27) ghi kỳ thi tốt nghiệp Mác-Lênin/TTHCM nhưng thiếu chuẩn NN-TH và KNM.\n"
                "6. Đăng ký học phần: VB1 thực hiện trước khi bắt đầu mỗi học kỳ; VB2 ghi đầu mỗi học kỳ.\n"
                "7. Rút bớt học phần: VB1 quy định thời hạn 2 tuần kể từ khi triển khai, ngoài thời hạn nhận điểm 0."
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
