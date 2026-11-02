import os
import sys
import re
import docx

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def find_docx_file():
    candidates = [
        "văn_bản_quy_định.docx",
        "văn bản quy định.docx",
        os.path.join("database", "seed_data", "văn bản quy định.docx"),
        os.path.join("database", "seed_data", "văn_bản_quy_định.docx"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.abspath(c)
    raise FileNotFoundError("Không tìm thấy file văn_bản_quy_định.docx")

def clean_google_urls(text: str) -> str:
    """Loại bỏ các link google.com/url rác."""
    cleaned = re.sub(r'https?://(?:www\.)?google\.com/url\S+', '', text)
    return cleaned.strip()

def build_chunks(docx_path: str):
    doc = docx.Document(docx_path)
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    # Lọc bỏ các đoạn chỉ chứa google url rác
    valid_paras = []
    for p in paras:
        cleaned = clean_google_urls(p)
        if cleaned:
            valid_paras.append(cleaned)

    # TODO: Mục "Bảng quy đổi Hình 1 và 2" trong file không có nội dung nên không tạo chunk riêng.

    chunks = [
        # 1. Điều kiện xét tốt nghiệp (Điều 27)
        {
            "section": "Chương IV – Điều 27",
            "title": "Điều kiện xét tốt nghiệp đại học",
            "source": "Quy chế đào tạo, Chương IV – Điều 27",
            "keywords": "xét tốt nghiệp, điều kiện tốt nghiệp, chuẩn đầu ra, 150 tín chỉ, 8 học kỳ, Mác Lênin, GDQP, GDTC",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương IV – Điều 27 | Mục: Điều kiện xét tốt nghiệp]\n"
                "Điều kiện xét tốt nghiệp đại học (Chương IV – Điều 27):\n"
                "- Cho đến thời điểm xét tốt nghiệp, sinh viên không đang trong thời gian bị truy cứu trách nhiệm hình sự.\n"
                "- Tích lũy đủ số học phần quy định cho chương trình, không còn học phần bị điểm dưới 5.\n"
                "- Được xếp loại đạt ở kỳ thi tốt nghiệp các môn khoa học Mác-Lênin, Tư tưởng Hồ Chí Minh.\n"
                "- Có các Chứng chỉ Giáo dục quốc phòng và Giáo dục thể chất đối với các ngành đào tạo không chuyên về quân sự và thể dục thể thao.\n"
                "- Đạt chuẩn đầu ra của Trường (bao gồm 8 học kỳ với 150 tín chỉ)."
            )
        },
        # 2. Điều kiện cấm thi (Điều 19)
        {
            "section": "Chương III – Điều 19",
            "title": "Điều kiện cấm thi kết thúc học phần",
            "source": "Quy chế đào tạo, Chương III – Điều 19",
            "keywords": "cấm thi, vắng quá 20%, điểm thành phần dưới 2.0, chuyên cần, giữa kỳ, điểm quá trình",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương III – Điều 19 | Mục: Điều kiện cấm thi]\n"
                "Điều kiện cấm thi kết thúc học phần (Chương III – Điều 19):\n"
                "- Vắng mặt: Sinh viên vắng mặt quá 20% số tiết của học phần (lý thuyết hoặc thực hành) sẽ không được dự thi kết thúc học phần đó và phải nhận điểm 0 ở phần thi kết thúc học phần (hoặc bị cấm thi tùy theo quy định cụ thể về điểm thành phần).\n"
                "- Điểm thành phần (Điểm quá trình/giữa kỳ): Điểm đánh giá bộ phận (điểm chuyên cần, kiểm tra giữa kỳ) đạt điểm dưới 2,0 (theo thang điểm 10) thì không đủ điều kiện dự thi kết thúc học phần (bị cấm thi)."
            )
        },
        # 3. Quy định học lại (Điều 12)
        {
            "section": "Chương II – Điều 12",
            "title": "Quy định học lại",
            "source": "Quy chế đào tạo, Chương II – Điều 12",
            "keywords": "học lại, điểm dưới 5, học phần bắt buộc, học phần tự chọn, thi cải thiện điểm",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương II – Điều 12 | Mục: Quy định học lại]\n"
                "Quy định học lại học phần (Chương II – Điều 12):\n"
                "- Sinh viên có học phần bắt buộc bị điểm < 5 phải đăng ký học lại học phần đó ở một trong các học kỳ tiếp theo cho đến khi đạt điểm ≥ 5.\n"
                "- Sinh viên có học phần tự chọn bị điểm < 5 phải đăng ký học lại học phần đó hoặc học đổi sang học phần tự chọn tương đương khác.\n"
                "- Sinh viên được quyền đăng ký thi cải thiện điểm tại lần thi thứ 2 của học phần, khi đó điểm thi lần thứ nhất sẽ bị hủy."
            )
        },
        # 4. Cải thiện điểm (Điều 20)
        {
            "section": "Chương III – Điều 20",
            "title": "Quy định cải thiện điểm",
            "source": "Quy chế đào tạo, Chương III – Điều 20",
            "keywords": "cải thiện điểm, học lại cải thiện, điểm cao nhất, nâng điểm",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương III – Điều 20 | Mục: Cải thiện điểm]\n"
                "Cải thiện điểm học phần (Chương III – Điều 20):\n"
                "- Sinh viên đã có điểm tổng kết học phần đạt (từ 5,0 điểm trở lên) nhưng muốn cải thiện điểm số có thể đăng ký học lại học phần đó vào các học kỳ tiếp theo khi có lớp.\n"
                "- Điểm lấy để tính vào kết quả học tập chính thức sẽ là điểm cao nhất trong các lần học."
            )
        },
        # 5. Cảnh báo học vụ và buộc thôi học (Điều 24)
        {
            "section": "Chương IV – Điều 24",
            "title": "Cảnh báo học vụ và buộc thôi học",
            "source": "Quy chế đào tạo, Chương IV – Điều 24",
            "keywords": "cảnh báo học vụ, buộc thôi học, điểm trung bình chung tích lũy, quá thời hạn, kỷ luật",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương IV – Điều 24 | Mục: Cảnh báo học vụ và buộc thôi học]\n"
                "Quy định cảnh báo học vụ và buộc thôi học (Chương IV – Điều 24):\n"
                "1. Mức cảnh báo học vụ:\n"
                "- Điểm trung bình chung tích lũy đạt dưới ngưỡng quy định: dưới 1,2 đối với năm thứ nhất; dưới 1,4 đối với năm thứ hai; dưới 1,6 đối với năm thứ ba; dưới 1,8 đối với các năm tiếp theo; hoặc tổng số tín chỉ không đạt quá giới hạn cho phép của trường trong học kỳ.\n"
                "2. Buộc thôi học:\n"
                "- Sinh viên bị buộc thôi học nếu rơi vào các trường hợp:\n"
                "  + Bị cảnh báo học vụ liên tiếp trong 2 học kỳ chính (hoặc quá số lần cảnh báo tối đa theo quy định của trường).\n"
                "  + Quá thời hạn tối đa hoàn thành chương trình học toàn khóa (quá 12 đến 13 học kỳ tùy theo ngành).\n"
                "  + Vi phạm kỷ luật ở mức độ bị kỷ luật buộc thôi học."
            )
        },
        # 6. Hướng dẫn đăng ký học lại, thi lại, học vét
        {
            "section": "Hướng dẫn đăng ký học vụ",
            "title": "Hướng dẫn đăng ký học lại, học vét và chi phí",
            "source": "Văn bản quy định học vụ, Khoa Công nghệ thông tin",
            "keywords": "học lại, học vét, đăng ký trực tuyến, mẫu đơn học lại, app ME, group Zalo, chi phí học lại",
            "content": (
                "[Văn bản: Hướng dẫn đăng ký học vụ | Nguồn: Khoa Công nghệ thông tin | Mục: Đăng ký học lại, học vét]\n"
                "Hướng dẫn đăng ký học lại, học vét:\n"
                "- Hình thức đăng ký học lại: Đăng ký trực tuyến.\n"
                "- Mẫu đơn đăng ký học lại: https://forms.gle/iBk3hNwG4SCGKMEFA\n"
                "- Lưu ý về thời hạn: Nếu mẫu đơn đã quá thời hạn đăng ký, vui lòng theo dõi trên app ME về đợt học lại tiếp theo.\n"
                "- Sinh viên tham gia Group Zalo để biết thêm chi tiết: https://zalo.me/g/ar6b85p9opfxctwhxwpd\n"
                "- Danh sách môn học lại tham khảo và chi phí học lại: https://docs.google.com/spreadsheets/d/1LBSioDaeoHSclt4R4yXpO0aFR-6kkTk9/edit?usp=sharing&ouid=103838733389649116635&rtpof=true&sd=true"
            )
        },
        # 7. Hình thức thi lại lần 2
        {
            "section": "Chương III – Điều 13 đến 23",
            "title": "Hình thức thi lại lần 2 cuối kỳ",
            "source": "Quy chế đào tạo, Chương III – Điều 13 đến 23",
            "keywords": "thi lại lần 2, thi lần 2, thi cuối kỳ, điểm dưới 5, chuyên cần, giữa kỳ không thi lại",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương III – Điều 13 đến 23 | Mục: Hình thức thi lại lần 2]\n"
                "Hình thức thi lại lần 2 cuối kỳ:\n"
                "- Cuối mỗi học kỳ, trường tổ chức thi lần 1 cuối kỳ của các học phần.\n"
                "- Đầu học kỳ mới, trường tổ chức thi lần 2 cuối kỳ của các học phần dành cho những sinh viên không tham dự lần 1 hoặc có học phần bị điểm < 5 ở kỳ thi lần 1.\n"
                "- LƯU Ý QUAN TRỌNG: Điểm chuyên cần và kiểm tra giữa kỳ KHÔNG có thi lần 2."
            )
        },
        # 8. Các đợt đăng ký học phần
        {
            "section": "Chương II – Điều 10",
            "title": "Các đợt đăng ký học phần",
            "source": "Quy chế đào tạo, Chương II – Điều 10",
            "keywords": "đăng ký học phần, đợt đăng ký, khối lượng học tập, kế hoạch năm học, phòng đào tạo",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương II – Điều 10 | Mục: Đăng ký học phần]\n"
                "Các đợt đăng ký học phần:\n"
                "- Việc đăng ký khối lượng học tập (đăng ký học phần) cho từng học kỳ được thực hiện vào đầu mỗi học kỳ theo kế hoạch chung và thông báo cụ thể của Phòng Đào tạo.\n"
                "- Thời gian đăng ký học lại / học cải thiện điểm được thực hiện theo các học kỳ chính hoặc học kỳ phụ (hè) do nhà trường ấn định thời hạn cụ thể trên cổng thông tin sinh viên và phòng đào tạo từng năm học."
            )
        },
        # 9. Xét tốt nghiệp và hạn nộp hồ sơ
        {
            "section": "Chương V",
            "title": "Xét tốt nghiệp và thời hạn nộp hồ sơ",
            "source": "Quy chế đào tạo, Chương V",
            "keywords": "xét tốt nghiệp, hạn nộp hồ sơ, đợt xét tốt nghiệp, nộp đơn xét tốt nghiệp",
            "content": (
                "[Văn bản: Quy chế đào tạo tín chỉ | Nguồn: Quy chế đào tạo, Chương V | Mục: Xét tốt nghiệp và hạn nộp hồ sơ]\n"
                "Xét tốt nghiệp và hạn nộp hồ sơ:\n"
                "- Xét tốt nghiệp: Nhà trường tổ chức xét và công nhận tốt nghiệp cho sinh viên sau mỗi học kỳ (thường có nhiều đợt xét tốt nghiệp trong năm học).\n"
                "- Hạn nộp hồ sơ: Sinh viên đủ điều kiện tốt nghiệp phải nộp đơn và hồ sơ xét tốt nghiệp theo thời hạn cụ thể do Phòng Đào tạo thông báo trước mỗi đợt xét tốt nghiệp của trường."
            )
        },
        # 10. Lệ phí chứng chỉ ngoại ngữ và tin học
        {
            "section": "Lệ phí thi chứng chỉ",
            "title": "Lệ phí thi chứng chỉ ngoại ngữ và tin học",
            "source": "Quy định chứng chỉ chuẩn đầu ra, Trung tâm Ngoại ngữ - Tin học Lạc Hồng",
            "keywords": "lệ phí thi, vstep, cefr, tin học, ứng dụng công nghệ thông tin, lệ phí ngoại ngữ",
            "content": (
                "[Văn bản: Quy định chứng chỉ chuẩn đầu ra | Nguồn: Trung tâm Ngoại ngữ - Tin học Lạc Hồng | Mục: Lệ phí thi chứng chỉ]\n"
                "Lệ phí thi các chứng chỉ ngoại ngữ và tin học tại trường:\n"
                "1. Chứng chỉ ngoại ngữ:\n"
                "- Chứng chỉ Ngoại ngữ 6 bậc (Vstep): 2.000.000 VNĐ / thí sinh / kỳ thi.\n"
                "- Chứng nhận đánh giá năng lực tiếng Anh (CEFR): 1.100.000 VNĐ / thí sinh / kỳ thi.\n"
                "2. Chứng chỉ tin học:\n"
                "- Chứng chỉ Ứng dụng công nghệ thông tin: 600.000 VNĐ / thí sinh / kỳ thi."
            )
        },
        # 11. Đối tượng miễn thi ngoại ngữ
        {
            "section": "Miễn thi ngoại ngữ",
            "title": "Đối tượng được miễn thi chứng chỉ ngoại ngữ",
            "source": "Quy định chuẩn đầu ra ngoại ngữ, Trường Đại học Lạc Hồng",
            "keywords": "miễn thi, miễn ngoại ngữ, toefl, ielts, bằng tiếng anh, đại học nước ngoài",
            "content": (
                "[Văn bản: Quy định chuẩn đầu ra ngoại ngữ | Nguồn: Trường Đại học Lạc Hồng | Mục: Đối tượng miễn thi]\n"
                "Đối tượng được miễn thi chứng chỉ ngoại ngữ:\n"
                "- Có bằng tốt nghiệp đại học chính quy ngành tiếng Anh; hoặc có bằng tốt nghiệp đại học tại nước ngoài mà ngôn ngữ dùng trong đào tạo là tiếng Anh.\n"
                "- Có bằng tốt nghiệp đại học tại các chương trình đào tạo trong nước mà ngôn ngữ dùng trong toàn bộ chương trình đào tạo là tiếng Anh không qua phiên dịch.\n"
                "- Có chứng chỉ TOEFL ITP 400, iBT 32 hoặc IELTS 4.5 trở lên trong thời hạn 2 năm kể từ ngày cấp chứng chỉ đến ngày nộp hồ sơ.\n"
                "- Có chứng chỉ ngoại ngữ do các cơ sở đào tạo ngoại ngữ được Bộ Giáo dục và Đào tạo giao nhiệm vụ và công nhận tương đương trình độ tiếng Anh TOEFL ITP 400, iBT 32 hoặc IELTS 4.5."
            )
        },
        # 12. Sát hạch tin học
        {
            "section": "Sát hạch tin học",
            "title": "Quy định và lớp ôn sát hạch tin học",
            "source": "Quy định sát hạch tin học, Khoa CNTT & Trung tâm NNTH",
            "keywords": "sát hạch tin học, mức phí ôn luyện, lớp ôn tin học, group Zalo, form đăng ký, app ME",
            "content": (
                "[Văn bản: Quy định sát hạch tin học | Nguồn: Khoa CNTT & Trung tâm NNTH | Mục: Sát hạch tin học]\n"
                "Quy định ôn luyện và đăng ký sát hạch tin học:\n"
                "- Mức phí ôn luyện: 90.000 VNĐ / sinh viên.\n"
                "- Đường link đăng ký tham gia lớp ôn: https://forms.gle/WtUpfZbPiWAq3RqK6\n"
                "- Sinh viên tham gia Group Zalo để biết thêm thông tin: https://zalo.me/g/g2elp3xxzxexl5lqjlc0\n"
                "- Lưu ý: Nếu đã quá thời hạn đăng ký, vui lòng theo dõi trên app ME về đợt mở đăng ký tiếp theo."
            )
        },
        # 13. GDQP - Giáo dục quốc phòng
        {
            "section": "Giáo dục quốc phòng",
            "title": "Quy định và lịch học Giáo dục quốc phòng",
            "source": "Quy định học phần Giáo dục quốc phòng - An ninh",
            "keywords": "giáo dục quốc phòng, gdqp, quân sự, lịch học gdqp, calen.lhu.edu.vn, 1 năm 1 lần",
            "content": (
                "[Văn bản: Quy định GDQP-AN | Nguồn: Quy định học phần Giáo dục quốc phòng - An ninh | Mục: Giáo dục quốc phòng]\n"
                "Quy định và lịch học Giáo dục quốc phòng (GDQP):\n"
                "- Lịch học: Dời sang bắt đầu ngày 28/7/2025 (lịch cũ là 14/7/2025).\n"
                "- Tra cứu lịch học chi tiết: Sinh viên tra cứu tại trang thông tin https://calen.lhu.edu.vn\n"
                "- LƯU Ý ĐẶC BIỆT: Lịch Giáo dục quốc phòng chỉ mở 1 năm / 1 lần. Nếu đã quá thời gian đăng ký, xin vui lòng đăng ký lại vào năm sau."
            )
        },
        # 14. GDTC - Giáo dục thể chất
        {
            "section": "Giáo dục thể chất",
            "title": "Quy định chứng chỉ Giáo dục thể chất",
            "source": "Quy định học phần Giáo dục thể chất",
            "keywords": "giáo dục thể chất, gdtc, thể dục, chứng chỉ thể chất, điều kiện tốt nghiệp",
            "content": (
                "[Văn bản: Quy định GDTC | Nguồn: Quy định học phần Giáo dục thể chất | Mục: Giáo dục thể chất]\n"
                "Quy định về Giáo dục thể chất (GDTC):\n"
                "- Sinh viên phải hoàn thành và tích lũy đủ các học phần Giáo dục thể chất theo chương trình đào tạo của trường.\n"
                "- Có Chứng chỉ Giáo dục thể chất là điều kiện bắt buộc để được xét công nhận tốt nghiệp đại học đối với các ngành không chuyên về thể dục thể thao."
            )
        },
        # 15. Kỹ năng mềm
        {
            "section": "Kỹ năng mềm",
            "title": "Quy định 4 kỹ năng mềm và học phí qua AppMe",
            "source": "Quy định chứng chỉ kỹ năng mềm, Trường Đại học Lạc Hồng",
            "keywords": "kỹ năng mềm, 4 kỹ năng, giải quyết vấn đề, thuyết trình, viết cv, khởi nghiệp, 500.000đ, AppMe",
            "content": (
                "[Văn bản: Quy định chuẩn kỹ năng mềm | Nguồn: Trường Đại học Lạc Hồng | Mục: Kỹ năng mềm]\n"
                "Quy định 4 kỹ năng mềm bắt buộc chuẩn đầu ra và học phí:\n"
                "1. Danh mục 4 kỹ năng mềm:\n"
                "- Kỹ năng giải quyết vấn đề và ra quyết định\n"
                "- Kỹ năng thuyết trình hiệu quả\n"
                "- Kỹ năng viết CV điện tử và phỏng vấn tìm việc làm\n"
                "- Kỹ năng khởi nghiệp\n"
                "2. Mức học phí:\n"
                "- Sinh viên Khóa 2023, Khóa 2024 và Khóa 2025: 500.000 đồng / môn.\n"
                "- Hình thức đóng tiền: Sinh viên đóng tiền trực tiếp trên AppMe theo hướng dẫn."
            )
        },
        # 16. Danh bạ Khoa CNTT
        {
            "section": "Danh bạ liên hệ",
            "title": "Danh bạ liên hệ Khoa Công nghệ thông tin",
            "source": "Thông tin liên hệ, Khoa Công nghệ thông tin LHU",
            "keywords": "danh bạ, liên hệ, khoa công nghệ thông tin, cntt@lhu.edu.vn, 02513.952.251, B301, B302, cơ sở 1",
            "content": (
                "[Văn bản: Thông tin liên hệ | Nguồn: Khoa Công nghệ thông tin LHU | Mục: Danh bạ liên hệ Khoa CNTT]\n"
                "Thông tin liên hệ chuyên ngành Công nghệ thông tin (Mã ngành: 7480201):\n"
                "- Số điện thoại liên hệ: 02513.952.251\n"
                "- Email: cntt@lhu.edu.vn\n"
                "- Website: http://cs.lhu.edu.vn\n"
                "- Văn phòng Khoa: Phòng B301 - B302, Cơ sở 1, Số 10 Huỳnh Văn Nghệ, P. Bửu Long, TP. Biên Hòa, Tỉnh Đồng Nai.\n"
                "- Giờ làm việc: Thứ Hai đến Thứ Sáu (Sáng: 7h30 – 11h30 | Chiều: 13h00 – 16h30 / 17h00)."
            )
        }
    ]

    return chunks

if __name__ == "__main__":
    f = find_docx_file()
    print("Found docx at:", f)
    chunks = build_chunks(f)
    print(f"Total chunks created: {len(chunks)}")
    for i, c in enumerate(chunks):
        print(f"--- Chunk {i+1}: {c['title']} ({c['section']}) ---")
        print("Source:", c['source'])
        print("Content preview:", c['content'][:120], "...\n")
