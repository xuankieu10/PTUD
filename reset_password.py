"""
reset_password.py
Script đặt lại mật khẩu cho một user trong hệ thống HocVuAI.
Sử dụng trực tiếp hàm get_password_hash (bcrypt) chuẩn của dự án.
Chỉ thực thi khi người dùng chủ động chạy và yêu cầu xác nhận trước khi cập nhật.
"""
import argparse
import sys
from sqlalchemy import create_engine, text
from backend.app.config import settings
from backend.app.security import get_password_hash

def main():
    parser = argparse.ArgumentParser(description="Đặt lại mật khẩu cho người dùng HocVuAI.")
    parser.add_argument("--username", "-u", required=True, help="Tên đăng nhập (username) cần đặt lại mật khẩu")
    parser.add_argument("--password", "-p", required=True, help="Mật khẩu mới cần gán")
    args = parser.parse_args()

    target_user = args.username.strip()
    new_password = args.password

    if not target_user or not new_password:
        print("[!] Lỗi: Username và mật khẩu mới không được để trống.")
        return 1

    print("=" * 60)
    print("         ĐẶT LẠI MẬT KHẨU TÀI KHOẢN HOCVUAI")
    print("=" * 60)
    print(f"[*] Tài khoản cần đổi : {target_user}")
    print(f"[*] DATABASE_URL     : {settings.DATABASE_URL}")

    # Tạo hash bcrypt bằng hàm chuẩn của dự án
    hashed_pw = get_password_hash(new_password)

    # Kết nối kiểm tra user tồn tại
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"timeout": 10},
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            user_check = conn.execute(
                text("SELECT id, username, role FROM users WHERE username = :u"),
                {"u": target_user}
            ).fetchone()

            if not user_check:
                print(f"\n[!] Không tìm thấy tài khoản '{target_user}' trong bảng users!")
                return 1

            print(f"[+] Tìm thấy tài khoản: ID={user_check.id}, Username={user_check.username}, Role={user_check.role}")
            print("-" * 60)
            
            # Hỏi xác nhận (y/n) trước khi ghi dữ liệu
            confirm = input(f"[?] Bạn có chắc chắn muốn cập nhật mật khẩu cho '{target_user}'? (y/N): ").strip().lower()
            if confirm != 'y':
                print("[*] Đã hủy thao tác. Không có thay đổi nào được ghi.")
                return 0

            # Thực thi UPDATE đúng 1 user
            result = conn.execute(
                text("UPDATE users SET password_hash = :pw WHERE username = :u"),
                {"pw": hashed_pw, "u": target_user}
            )
            conn.commit()

            print(f"[+] CẬP NHẬT THÀNH CÔNG! Số dòng bị ảnh hưởng: {result.rowcount}")
            print(f"[*] Bây giờ bạn có thể đăng nhập bằng username '{target_user}' và mật khẩu mới.")
            return 0

    except Exception as e:
        print(f"\n[!] Thao tác thất bại: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

