"""
Bảng từ đồng nghĩa và khẩu ngữ thường gặp trong tư vấn học vụ.
Được tách riêng để dễ bảo trì, cập nhật và mở rộng theo thực tế sinh viên.
"""

# Danh sách ánh xạ từ đồng nghĩa / khẩu ngữ sang từ ngữ học thuật chuẩn
# Mỗi phần tử: (danh_sach_tu_kich_hoat, chuoi_bo_sung_ngu_nghia)
SYNONYM_MAPPINGS = [
    # 1. Khẩu ngữ ra trường, ra bằng -> tốt nghiệp và điều kiện xét tốt nghiệp
    (
        ["ra trường", "ra truong", "ra bằng", "ra bang", "lấy bằng", "lay bang", "tốt nghiệp", "tot nghiep", "xét tốt nghiệp", "xet tot nghiep", "điều kiện tốt nghiệp", "dieu kien tot nghiep"],
        "điều kiện xét tốt nghiệp đại học chuẩn đầu ra"
    ),
    # 2. Giấy tờ -> hồ sơ, thủ tục nộp
    (
        ["giấy tờ", "giay to", "thủ tục", "thu tuc", "cần nộp", "can nop"],
        "hồ sơ graduate.lhu.edu.vn lệ phí nộp xét tốt nghiệp"
    ),
    # 3. Rớt, trượt, nợ môn -> không đạt
    (
        ["rớt", "rot", "trượt", "truot", "nợ môn", "no mon", "chưa đạt", "chua dat"],
        "không đạt điểm dưới 4.0 cảnh báo học vụ buộc thôi học"
    ),
    # 4. Thi lại
    (
        ["thi lại", "thi lai", "thi lai mon"],
        "thi lại đánh giá lại cải thiện điểm số"
    ),
    # 5. Học lại, học vét
    (
        ["học lại", "hoc lai", "học vét", "hoc vet", "trả nợ môn", "tra no mon"],
        "đăng ký học lại học phần học kỳ phụ trả nợ tín chỉ"
    ),
    # 6. Ngoại ngữ -> tiếng Anh, TOEIC, IELTS, VSTEP
    (
        ["ngoại ngữ", "ngoai ngu", "anh văn", "anh van", "toeic", "ielts", "vstep", "tiếng anh", "tieng anh"],
        "chuẩn đầu ra ngoại ngữ Tiếng Anh Bậc 3 TOEIC IELTS VSTEP"
    ),
    # 7. Tin học -> sát hạch tin học, ứng dụng CNTT
    (
        ["tin học", "tin hoc", "sát hạch", "sat hach", "cntt", "công nghệ thông tin", "cong nghe thong tin"],
        "chuẩn đầu ra sát hạch tin học ứng dụng công nghệ thông tin Khoa CNTT"
    ),
    # 8. GDQP, GDTC, quốc phòng, thể dục
    (
        ["gdqp", "quốc phòng", "quoc phong", "quân sự", "quan su"],
        "chứng chỉ Giáo dục quốc phòng an ninh GDQP"
    ),
    (
        ["gdtc", "thể dục", "the duc", "thể chất", "the chat"],
        "chứng chỉ Giáo dục thể chất GDTC"
    ),
    # 9. Điểm trung bình, GPA, điểm tích lũy
    (
        ["gpa", "điểm trung bình", "diem trung binh", "điểm tích lũy", "diem tich luy"],
        "điểm trung bình tích lũy toàn khóa 5.0 thang điểm 10"
    ),
    # 10. Kỹ năng mềm
    (
        ["kỹ năng mềm", "ky nang mem", "knm"],
        "chứng chỉ 4 kỹ năng mềm"
    ),
    # 11. Giấy chứng nhận hoàn thành khóa học (cho SV thiếu điều kiện)
    (
        ["giấy chứng nhận", "giay chung nhan", "chưa nộp đủ", "chua nop du", "thiếu chứng chỉ", "thieu chung chi", "thiếu ngoại ngữ", "thiếu tin học"],
        "Mục D Giấy chứng nhận hoàn thành khóa học thiếu điều kiện tốt nghiệp phòng Đào tạo B101 Cơ sở 1"
    ),
]
