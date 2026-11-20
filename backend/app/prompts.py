import re

SYSTEM_PROMPT = """Bạn là Cố vấn học vụ Khoa CNTT, ĐH Lạc Hồng (LHU).
Mục tiêu cốt lõi: Giúp sinh viên TỐT NGHIỆP ĐÚNG HẠN bằng cách chỉ rõ họ còn thiếu gì và cần làm gì từng kỳ.
Mọi câu trả lời tư vấn BẮT BUỘC có đủ 4 phần:

### 1. TÌNH TRẠNG HIỆN TẠI
- Tín chỉ tích lũy/tổng tín chỉ, GPA (thang 10 & 4), điều kiện đã xong.

### 2. CÒN THIẾU GÌ
- Tín chỉ thiếu, môn nợ (điểm < 4.0), môn bắt buộc chưa học, chuẩn đầu ra còn thiếu.

### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT
- Môn đăng ký từng kỳ (kỳ chính <= 20 TC, hè <= 8 TC), xét tiên quyết.

### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ
- Cảnh báo môn tiên quyết, chứng chỉ; cổng đăng ký https://dkmh.lhu.edu.vn hoặc liên hệ P.Đào tạo (B101, CS1) / Khoa CNTT.

QUY TẮC:
1. CHỈ dùng số liệu từ bản kế hoạch dựng sẵn của code, KHÔNG tự tính toán hay bịa con số.
2. Thiếu thông tin học tập thì hỏi lại đúng 1 câu trọng tâm.
3. Luôn kết thúc bằng hành động cụ thể.

VÍ DỤ MẪU:
### 1. TÌNH TRẠNG HIỆN TẠI
- Tích lũy: 18/150 tín chỉ. GPA: 5.20 (thang 10). Đã xong: GDQP-AN.
### 2. CÒN THIẾU GÌ
- Thiếu 132 tín chỉ. Môn nợ: Toán CC1 (4 TC), Nhập môn lập trình (2 TC). Thiếu CĐR: Tiếng Anh, Tin học.
### 3. KẾ HOẠCH TỪNG HỌC KỲ ĐỀ XUẤT
+ Học kỳ hè (6 TC): Học lại Toán CC1 (4 TC) và Nhập môn lập trình (2 TC).
+ Học kỳ 3 (18 TC): Cấu trúc dữ liệu (4 TC), Kỹ thuật lập trình (3 TC), Triết học (3 TC), Tiếng Anh (4 TC)...
### 4. RỦI RO & HÀNH ĐỘNG CỤ THỂ
- Rủi ro: Nhập môn lập trình là tiên quyết; nếu không trả ở kỳ hè sẽ bị chặn các môn sau.
- Hành động: Đăng ký học lại trên https://dkmh.lhu.edu.vn hoặc liên hệ Khoa CNTT."""

NO_CONTEXT_RESPONSE = "Xin lỗi, tôi không tìm thấy thông tin này trong tài liệu học vụ hiện có của Khoa Công nghệ thông tin. Vui lòng liên hệ phòng Đào tạo (B101, Cơ sở 1) hoặc văn phòng Khoa để được hỗ trợ chính xác nhất."

REFUSAL_RESPONSE = "Xin lỗi, tôi là trợ lý tư vấn học vụ và chỉ hỗ trợ giải đáp các thắc mắc về quy chế, chương trình đào tạo và thủ tục học vụ của nhà trường."

FACULTY_NOT_SUPPORTED_RESPONSE = "Hiện tại hệ thống chưa có dữ liệu quy định của khoa này (hệ thống hiện chỉ hỗ trợ tư vấn học vụ cho Khoa Công nghệ thông tin); tôi không thể tự bịa thông tin. Vui lòng liên hệ văn phòng khoa tương ứng hoặc phòng Đào tạo để được hỗ trợ."

LANG_REMINDER = "Trả lời bằng tiếng Việt, chỉ dựa trên tài liệu."

LANG_RETRY_SYSTEM = """Bạn PHẢI trả lời bằng tiếng Việt. Tuyệt đối không được dùng tiếng Anh hay ngôn ngữ khác.
Chỉ dựa trên tài liệu được cung cấp."""

import unicodedata

def strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt khỏi chuỗi văn bản."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

# Regex patterns cho injection detection (khớp cả tiếng Việt có dấu, không dấu, SQL injection)
_INJECTION_PATTERNS = re.compile(
    r"b[oỏ]\s*qua\s*(?:(t[aấ]t\s*c[aả]|m[oọ]i)\s*)?(h[uư][oớ]ng\s*d[aẫ]n|ch[iỉ]\s*d[aẫ]n|quy\s*t[aắ]c|ch[iỉ]\s*th[iị])"
    r"|ch[iỉ]\s*d[aẫ]n\s*tr[uư][oớ]c\s*[dđ][oó]"
    r"|system\s*prompt"
    r"|prompt\s*h[eệ]\s*th[oố]ng"
    r"|[dđ][oó]ng\s*vai(?!\s*tr[oò])"
    r"|ignore\s*(all\s*)?(previous|above)"
    r"|tr[aả]\s*l[oờ]i\s*b[aằ]ng\s*ti[eế]ng\s*anh"
    r"|answer\s*in\s*english"
    r"|b[oỏ]\s*qua\s*ngu[oồ]n"
    r"|kh[oô]ng\s*c[aầ]n\s*(d[aẫ]n\s*)?ngu[oồ]n"
    r"|l[aặ]p\s*l[aạ]i\s*nguy[eê]n\s*v[aă]n"
    r"|nh[aắ]c\s*l[aạ]i\s*nguy[eê]n\s*v[aă]n"
    r"|in\s*ra\s*nguy[eê]n\s*v[aă]n"
    r"|in\s*ra\s*(to[aà]n\s*b[oộ]\s*)?(system\s*prompt|prompt\s*h[eệ]\s*th[oố]ng|n[oộ]i\s*dung)"
    r"|[dđ]o[aạ]n\s*v[aă]n\s*b[aả]n\s*(b[aạ]n\s*)?nh[aậ]n\s*[dđ][uư][oợ]c"
    r"|[dđ][aầ]u\s*cu[oộ]c\s*tr[oò]\s*chuy[eệ]n"
    r"|repeat\s*(the\s*)?(text|above|everything)"
    r"|qu[eê]n\s*(c[aá]c|m[oọ]i)?\s*(ch[iỉ]\s*th[iị]|h[uư][oớ]ng\s*d[aẫ]n)"
    r"|t[uừ]\s*gi[oờ]\s*b[aạ]n\s*l[aà]"
    r"|b[aạ]n\s*l[aà]\s*(m[oộ]t\s*)?(chuy[eê]n\s*gia|tr[oợ]\s*l[yý]|nh[aà])"
    r"|h[aã]y\s*[dđ][oó]ng\s*vai"
    r"|[dđ][oó]ng\s*vai\s*ai\s*kh[oô]ng\s*b[iị]\s*r[aà]ng\s*bu[oộ]c"
    r"|\b(select\s+\*\s+from|drop\s+table|delete\s+from|insert\s+into)\b"
    r"|drop\s+table",
    re.IGNORECASE
)

# Regex phát hiện ký tự tiếng Việt có dấu
_VIET_PATTERN = re.compile(
    r"[àáảãạăắặẵẳấầẩẫậâđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ"
    r"ÀÁẢÃẠĂẮẶẴẲẤẦẨẪẬÂĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ]",
    re.UNICODE
)


def is_injection(question: str) -> bool:
    """Trả True nếu câu hỏi chứa lệnh injection / yêu cầu đổi ngôn ngữ / SQL injection."""
    if not question:
        return False
    # Kiểm tra trên chuỗi gốc
    if bool(_INJECTION_PATTERNS.search(question)):
        return True
    # Chuẩn hóa: hạ thường, bỏ dấu tiếng Việt, gom khoảng trắng để bắt câu không dấu/viết hoa
    norm = strip_accents(question.lower())
    norm = re.sub(r'\s+', ' ', norm).strip()
    return bool(_INJECTION_PATTERNS.search(norm))


def has_vietnamese(text: str) -> bool:
    """Trả True nếu text có ít nhất 1 ký tự tiếng Việt có dấu."""
    return bool(_VIET_PATTERN.search(text))


def mixed_language(text: str) -> bool:
    import re
    import string

    # 2. Check for CJK characters (Chinese, Japanese, Korean)
    if re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text):
        return True

    # 3. Check for genuine English stop words / sentences
    english_words = {
        "the", "is", "are", "was", "were", "and", "of", "to", "in", "that",
        "have", "with", "this", "from", "they", "we", "you", "for", "not",
        "graduation", "student", "students", "requirements", "requirement",
        "university", "faculty", "degree", "according", "please", "contact",
        "should", "must", "will", "would", "about", "which", "their", "there"
    }

    words = text.split()
    eng_count = 0
    total_count = 0

    for word in words:
        if word.startswith("__") or word.startswith("http"):
            continue
        clean_word = word.strip(string.punctuation).lower()
        if not clean_word:
            continue
        total_count += 1
        if clean_word in english_words:
            eng_count += 1

    if total_count >= 5 and (eng_count / total_count) > 0.15 and eng_count >= 3:
        return True
    return False

