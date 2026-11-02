import re

class StreamingLabelFilter:
    """
    Bộ lọc tăng dần token với bộ đệm ngắn (Incremental Short-Buffer Filter).
    Mục tiêu:
    - Loại bỏ nhãn kỹ thuật (<ngu_canh>, </ngu_canh>, [ĐÂY LÀ TÀI LIỆU...], [/TÀI LIỆU])
      và phần nguồn thừa do LLM tự sinh ở cuối câu ("Nguồn: ...").
    - KHÔNG làm trễ token đầu (TTFT): các token thông thường được phát ra ngay lập tức.
    - Không nuốt nhầm từ "Nguồn" hợp lệ trong nội dung câu (ví dụ "Nguồn kinh phí", "nguồn gốc").
    """
    def __init__(self):
        self.buffer = ""
        self.is_suppressed = False
        self.dangerous_labels = [
            "<ngu_canh>",
            "</ngu_canh>",
            "[ĐÂY LÀ TÀI LIỆU, KHÔNG PHẢI LỜI NGƯỜI DÙNG]",
            "[/TÀI LIỆU]"
        ]
        self.max_label_len = max(len(l) for l in self.dangerous_labels)

    def is_prefix_of_dangerous_label(self, s: str) -> bool:
        """Kiểm tra chuỗi s có phải là tiền tố của bất kỳ nhãn kỹ thuật nguy hiểm nào không."""
        for label in self.dangerous_labels:
            if label.startswith(s):
                return True
        return False

    def is_exact_dangerous_label(self, s: str) -> bool:
        """Kiểm tra chuỗi s có khớp chính xác nhãn kỹ thuật nào không."""
        return s in self.dangerous_labels

    def feed(self, token: str) -> list[str]:
        """
        Nhận 1 token từ stream Ollama và trả về danh sách các token an toàn để yield ngay.
        """
        if self.is_suppressed:
            return []

        self.buffer += token
        out = []

        while self.buffer:
            # 1. Kiểm tra nếu phát hiện bắt đầu dòng nguồn bịa do LLM tự sinh ở cuối
            # Dòng nguồn bịa thường bắt đầu sau \n hoặc ở đầu dòng mới dạng:
            # "\nNguồn:", "\n- Nguồn:", "\n* Nguồn:", "\nTham khảo:"
            if "\n" in self.buffer:
                parts = self.buffer.split("\n")
                # Xử lý các phần trước dấu xuống dòng cuối cùng
                for p in parts[:-1]:
                    p_clean = p.strip()
                    if re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo|Tài liệu tham khảo)\s*:", p_clean, re.IGNORECASE) or ("cs.lhu.edu.vn" in p_clean and "http" in p_clean):
                        self.is_suppressed = True
                        self.buffer = ""
                        return out
                    out.append(p + "\n")
                self.buffer = parts[-1]

            # 2. Kiểm tra nếu buffer bắt đầu bằng tiền tố nhãn kỹ thuật (< hoặc [)
            if self.buffer.startswith("<") or self.buffer.startswith("["):
                # Kiểm tra nếu khớp trọn vẹn nhãn kỹ thuật
                matched_label = None
                for label in self.dangerous_labels:
                    if self.buffer.startswith(label):
                        matched_label = label
                        break
                if matched_label:
                    # Nuốt trọn nhãn này, xóa khỏi buffer
                    self.buffer = self.buffer[len(matched_label):]
                    continue

                # Nếu là tiền tố tiềm năng và chưa vượt quá độ dài tối đa của nhãn
                if self.is_prefix_of_dangerous_label(self.buffer):
                    if len(self.buffer) < self.max_label_len:
                        # Tạm giữ lại trong buffer ngắn để nhận token tiếp theo
                        break
                    else:
                        # Vượt quá độ dài nhãn -> không phải nhãn, xả ký tự đầu tiên
                        out.append(self.buffer[0])
                        self.buffer = self.buffer[1:]
                        continue
                else:
                    # Không phải tiền tố nhãn nguy hiểm -> xả ký tự đầu tiên
                    out.append(self.buffer[0])
                    self.buffer = self.buffer[1:]
                    continue

            # 3. Kiểm tra nhãn xuất hiện ở giữa buffer (sau một đoạn văn bản bình thường)
            # Tìm vị trí xuất hiện sớm nhất của '<' hoặc '['
            idx_tag1 = self.buffer.find("<")
            idx_tag2 = self.buffer.find("[")
            tag_indices = [i for i in [idx_tag1, idx_tag2] if i > 0]

            if tag_indices:
                first_tag_idx = min(tag_indices)
                # Phát đoạn văn bản an toàn trước tag ra ngay
                out.append(self.buffer[:first_tag_idx])
                self.buffer = self.buffer[first_tag_idx:]
                continue

            # 4. Kiểm tra chữ "Nguồn:" ở đầu câu / đầu buffer (nếu có dấu 2 chấm đi kèm)
            stripped_buf = self.buffer.strip()
            if re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo)\s*:", stripped_buf, re.IGNORECASE):
                # Khớp nhãn nguồn -> nuốt và dừng stream
                self.is_suppressed = True
                self.buffer = ""
                return out

            # Nếu chuỗi chỉ là "Nguồn" nhưng chưa có dấu ":" và từ tiếp theo là từ bình thường
            # Ví dụ: "Nguồn kinh phí...", "nguồn lực..."
            if len(self.buffer) >= 8 and not re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo)", stripped_buf, re.IGNORECASE):
                out.append(self.buffer)
                self.buffer = ""
                break
            elif len(self.buffer) < 8 and re.match(r"^\s*([-*•]|\d+\.)?\s*(N|Ng|Ngu|Nguồ|Nguồn)$", stripped_buf, re.IGNORECASE):
                # Tạm giữ vài ký tự để xem có dấu ":" không
                break
            else:
                out.append(self.buffer)
                self.buffer = ""
                break

        return out

    def flush(self) -> list[str]:
        """Xả toàn bộ buffer còn lại khi stream kết thúc."""
        if self.is_suppressed:
            return []
        res = []
        if self.buffer:
            # Kiểm tra lần cuối không phải nhãn
            if not (self.is_exact_dangerous_label(self.buffer.strip()) or re.match(r"^\s*([-*•]|\d+\.)?\s*(Nguồn|Tham khảo)\s*:", self.buffer.strip(), re.IGNORECASE)):
                res.append(self.buffer)
            self.buffer = ""
        return res

