# Danh Mục Lưu Đồ Kiến Trúc & Quy Trình Dự Án (Mermaid Diagrams)

Thư mục này chứa mã nguồn (`.mmd`) cùng các bản render ảnh (`.png` độ phân giải cao scale x3 nền trắng, `.svg` vector sắc nét) của các luồng nghiệp vụ chính trong hệ thống.

---

## Danh sách lưu đồ

| STT | Tên lưu đồ | File mã nguồn | Bản vẽ ảnh (PNG / SVG) | Mô tả tóm tắt (1 dòng) |
| :---: | :--- | :--- | :--- | :--- |
| **01** | **Tổng quan hệ thống** | [`01_tong_quan_he_thong.mmd`](./01_tong_quan_he_thong.mmd) | [`PNG`](./01_tong_quan_he_thong.png) \| [`SVG`](./01_tong_quan_he_thong.svg) | Kiến trúc tổng thể kết nối giữa Frontend React, Backend FastAPI, các module xử lý lõi, Ollama AI và CSDL SQL Server. |
| **02** | **Lọc môn không đạt** | [`02_loc_mon_khong_dat.mmd`](./02_loc_mon_khong_dat.mmd) | [`PNG`](./02_loc_mon_khong_dat.png) \| [`SVG`](./02_loc_mon_khong_dat.svg) | Quy trình tiếp nhận bảng điểm (ảnh/PDF), nhận diện text layer/scan, OCR bằng Ollama Vision, phát hiện khoanh đỏ bằng OpenCV và lọc môn không đạt. |
| **03** | **Chat trợ lý học vụ** | [`03_chat_tro_ly_hoc_vu.mmd`](./03_chat_tro_ly_hoc_vu.mmd) | [`PNG`](./03_chat_tro_ly_hoc_vu.png) \| [`SVG`](./03_chat_tro_ly_hoc_vu.svg) | Luồng hội thoại trợ lý AI từ xác thực JWT, Chat Guard chống injection, phân loại ý định (cá nhân/quy chế/ngoài lề), tìm kiếm RAG và hậu kiểm tiếng Việt. |

---

## Hướng dẫn kết xuất lại ảnh (Re-render)

Nếu cập nhật nội dung file `.mmd`, có thể kết xuất lại bằng lệnh Mermaid CLI:

```bash
# Render PNG (Scale 3, Nền trắng)
npx -y @mermaid-js/mermaid-cli -i docs/diagrams/<file>.mmd -o docs/diagrams/<file>.png -b white -s 3

# Render SVG
npx -y @mermaid-js/mermaid-cli -i docs/diagrams/<file>.mmd -o docs/diagrams/<file>.svg -b white
```
