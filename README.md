# Nghiên cứu và phát triển trợ lý AI hỗ trợ tư vấn học vụ cho sinh viên chuẩn bị tốt nghiệp

---

## 1. Giới thiệu

- **Tên đề tài:** Nghiên cứu và phát triển trợ lý AI hỗ trợ tư vấn học vụ cho sinh viên chuẩn bị tốt nghiệp
- **Mô tả ngắn gọn:** Hệ thống Web/Mobile ứng dụng mô hình ngôn ngữ lớn (LLM) kết hợp kỹ thuật truy xuất tăng cường sinh nội dung (RAG - Retrieval-Augmented Generation), giúp sinh viên dễ dàng tra cứu quy chế đào tạo, đối soát chuẩn đầu ra tốt nghiệp và nhận tư vấn lộ trình cá nhân hóa nhằm hoàn thành các điều kiện tốt nghiệp đúng hạn.
- **Đơn vị thực hiện:** Trường Đại học Lạc Hồng (LHU) — Khoa Công nghệ Thông tin.

---

## 2. Công nghệ sử dụng

Dự án được xây dựng trên nền tảng công nghệ Frontend hiện đại với các thư viện và công cụ thực tế:

| Công nghệ / Thư viện | Phiên bản | Vai trò & Mục đích |
| :--- | :--- | :--- |
| **React** | `^18.3.1` | Thư viện nền tảng xây dựng giao diện người dùng (UI) dạng Single Page Application (SPA). |
| **React DOM** | `^18.3.1` | Render các component React lên DOM trình duyệt. |
| **TypeScript** | `^5.6.3` | Ngôn ngữ lập trình tĩnh, đảm bảo tính chặt chẽ về kiểu dữ liệu (Types/Interfaces). |
| **Vite** | `^6.0.1` | Build tool và Development Server tốc độ cao, hỗ trợ Hot Module Replacement (HMR). |
| **TailwindCSS** | `^3.4.17` | Framework Utility-First CSS hỗ trợ thiết kế giao diện hiện đại, responsive và tối ưu hiệu năng. |
| **React Router DOM** | `^6.28.0` | Thư viện điều hướng và định tuyến đa trang (Routing) trong ứng dụng React. |
| **Lucide React** | `^1.16.0` | Bộ icon vector hiện đại, tối giản và đồng bộ. |
| **PostCSS & Autoprefixer** | `^8.4.49` / `^10.4.20` | Tiền xử lý và tự động tối ưu tương thích CSS cho nhiều trình duyệt. |

---

## 3. Cấu trúc thư mục

```
PTUD/
├── index.html                   # HTML template chính, cấu hình phông chữ và Favicon
├── package.json                 # Danh sách dependencies, scripts và thông tin dự án
├── postcss.config.js            # Cấu hình PostCSS và Autoprefixer
├── tailwind.config.js           # Cấu hình theme màu LHU và định nghĩa lớp tiện ích Tailwind
├── tsconfig.json                # Cấu hình TypeScript compiler cho mã nguồn
├── tsconfig.node.json           # Cấu hình TypeScript cho môi trường Node/Vite
├── vite.config.ts               # Cấu hình Vite bundler và dev server
└── src/
    ├── main.tsx                 # Điểm khởi chạy (entry point) của ứng dụng
    ├── App.tsx                  # Thiết lập hệ thống định tuyến (React Router DOM)
    ├── index.css                # Tệp định kiểu toàn cục, nạp Tailwind và tùy biến giao diện
    │
    ├── types/                   # Khai báo các interface và type definitions
    │   └── index.ts             # Định nghĩa cấu trúc StudentProfile, CreditCategory, Milestone, ChatMessage...
    │
    ├── mock/                    # Dữ liệu giả lập phục vụ giai đoạn phát triển giao diện
    │   └── studentData.ts       # Mock data hồ sơ sinh viên LHU, tiến độ tín chỉ, mốc thời gian và logic AI bot mẫu
    │
    ├── components/              # Các thành phần giao diện dùng chung (reusable components)
    │   ├── Navbar.tsx           # Thanh điều hướng phía trên kèm Logo trường và nút Đăng nhập
    │   ├── Footer.tsx           # Chân trang hiển thị thông tin bản quyền và liên hệ Phòng Đào tạo
    │   ├── FeatureCard.tsx      # Thẻ card hiển thị tính năng nổi bật có hiệu ứng hover
    │   ├── GraduationStatusBadge.tsx # Huy hiệu (badge) biểu diễn 3 trạng thái xét tốt nghiệp (Xanh/Vàng/Đỏ)
    │   ├── CreditProgressBar.tsx# Khối hiển thị tiến độ tín chỉ và phân bổ theo các khối kiến thức
    │   ├── MilestoneList.tsx    # Danh sách các mốc thời gian quan trọng sắp tới kèm đếm ngược ngày
    │   └── AIChatModal.tsx      # Cửa sổ hội thoại tương tác trực tiếp với Trợ lý AI tư vấn học vụ
    │
    └── pages/                   # Các trang màn hình chính của ứng dụng
        ├── HomePage.tsx         # Trang chủ: Giới thiệu hệ thống, Hero section, tính năng và xem trước
        ├── LoginPage.tsx        # Trang đăng nhập: Form xác thực MSSV/Mật khẩu với validation và loading
        └── StudentDashboard.tsx # Trang tài khoản sinh viên: Tổng quan học vụ, tiến độ tín chỉ và nhắc lịch
```

---

## 4. Hướng dẫn cài đặt & chạy dự án

### Yêu cầu môi trường
- **Node.js**: Phiên bản `>= 18.x` (khuyến nghị bản LTS)
- **NPM**: Phiên bản `>= 9.x` hoặc công cụ tương đương (Yarn, PNPM)

### Các bước thực hiện

1. **Clone mã nguồn dự án về máy:**
   ```bash
   git clone https://github.com/xuankieu10/PTUD.git
   cd PTUD
   ```

2. **Cài đặt các gói phụ thuộc (Dependencies):**
   ```bash
   npm install
   ```

3. **Khởi chạy máy chủ phát triển (Development Server):**
   ```bash
   npm run dev
   ```

4. **Truy cập ứng dụng:**
   Mở trình duyệt web và điều hướng tới địa chỉ:
   ```
   http://localhost:3000
   ```

5. **Biên dịch sản phẩm (Build for Production):**
   ```bash
   npm run build
   ```

---

## 5. Danh sách các trang hiện có

| Tên trang | Đường dẫn (Route) | Mô tả chức năng |
| :--- | :--- | :--- |
| **Trang chủ** | `/` | Giới thiệu tổng quan về hệ thống Trợ lý AI Học vụ LHU, trình bày 4 tính năng trọng tâm, hỗ trợ mở nhanh cửa sổ chat thử nghiệm và điều hướng đăng nhập. |
| **Đăng nhập** | `/login` | Màn hình đăng nhập tài khoản sinh viên (MSSV + Mật khẩu), có tính năng ẩn/hiện mật khẩu, kiểm tra dữ liệu đầu vào (validation), ghi nhớ đăng nhập, nút điền nhanh tài khoản mẫu và hướng dẫn liên hệ Phòng Đào tạo khi quên mật khẩu. |
| **Trang tài khoản sinh viên** | `/dashboard` | Bảng điều khiển cá nhân hóa: hiển thị thông tin sinh viên, điểm GPA, huy hiệu trạng thái tốt nghiệp, phân tích tiến độ tín chỉ theo từng khối kiến thức, danh sách mốc thời gian quan trọng đếm ngược và nút mở Trợ lý AI giải đáp học vụ 24/7. |

---

## 6. Trạng thái phát triển

- Hiện tại, dự án đang ở giai đoạn **Hoàn thiện Giao diện Mẫu (UI/UX Prototype)** với dữ liệu tĩnh giả lập (`mock data`).
- **Kế hoạch giai đoạn tiếp theo:**
  - Xây dựng hệ thống Backend API (Node.js/Python FastAPI).
  - Tích hợp kết nối cơ sở dữ liệu học vụ thực tế.
  - Tích hợp mô hình AI (LLM + RAG) với cơ sở tri thức là toàn bộ quy chế đào tạo, chuẩn đầu ra và biểu mẫu chính thức của Trường Đại học Lạc Hồng.

---

## 7. Thành viên thực hiện

| Họ và tên | Vai trò | Trách nhiệm chính |
| :--- | :--- | :--- |
| **Ngô Xuân Kiều** | Developer / Tester | Xây dựng kiến trúc Frontend, phát triển giao diện React + TailwindCSS, tích hợp định tuyến, kiểm thử chức năng và luồng tương tác người dùng. |
| **Nguyễn Bùi Quỳnh Nhi** | Business Analyst | Khảo sát nhu cầu sinh viên tốt nghiệp, phân tích yêu cầu nghiệp vụ quy chế đào tạo LHU, xây dựng luồng tư vấn học vụ và kịch bản tương tác cho Trợ lý AI. |
