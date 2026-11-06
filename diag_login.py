"""
diag_login.py
Script chẩn đoán trạng thái database và tài khoản người dùng đăng nhập HocVuAI.
Chỉ thực hiện các truy vấn ĐỌC (SELECT), tuyệt đối không sửa đổi dữ liệu.
TUYỆT ĐỐI không in giá trị password_hash ra màn hình.
"""
import sys
from sqlalchemy import create_engine, text
from backend.app.config import settings

def main():
    print("=" * 65)
    print("      CHẨN ĐOÁN HỆ THỐNG ĐĂNG NHẬP HOCVUAI")
    print("=" * 65)
    print(f"[*] DATABASE_URL: {settings.DATABASE_URL}")
    print("[*] Đang kết nối kiểm tra (timeout 10s)...")

    try:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"timeout": 10},
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            print("[+] KẾT NỐI DATABASE THÀNH CÔNG (OK)!\n")

            # 1. Thông tin server & database
            print("--- 1. THÔNG TIN MÔI TRƯỜNG DATABASE ---")
            info_row = conn.execute(text("SELECT @@SERVERNAME AS srv, DB_NAME() AS db")).fetchone()
            if info_row:
                print(f"  - Server Instance đang kết nối : {info_row[0]}")
                print(f"  - Tên Database đang sử dụng   : {info_row[1]}")
            print()

            # 2. Số lượng bản ghi các bảng chính
            print("--- 2. THỐNG KÊ BẢN GHI CÁC BẢNG CHÍNH ---")
            tables = ["users", "students", "document_chunks", "grades", "student_certificates"]
            for tbl in tables:
                try:
                    cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                    print(f"  - Bảng [{tbl:<22}]: {cnt:>5} dòng")
                except Exception as e_tbl:
                    print(f"  - Bảng [{tbl:<22}]: [Lỗi / Không tồn tại: {e_tbl}]")
            print()

            # 3. Danh sách người dùng trong bảng users
            print("--- 3. DANH SÁCH USER HIỆN CÓ TRONG BẢNG USERS ---")
            try:
                users_list = conn.execute(text("SELECT id, username, role FROM users ORDER BY id")).fetchall()
                if not users_list:
                    print("  [!] BẢNG USERS ĐANG TRỐNG HOÀN TOÀN! (Cần nạp dữ liệu seed)")
                else:
                    print(f"  {'ID':<5} | {'Username':<20} | {'Role':<15}")
                    print("  " + "-" * 45)
                    for u in users_list:
                        print(f"  {u.id:<5} | {u.username:<20} | {u.role:<15}")
            except Exception as e_usr:
                print(f"  [!] Lỗi khi đọc danh sách users: {e_usr}")
            print()

            # 4. Kiểm tra cụ thể tài khoản sv01 và sv02
            print("--- 4. KIỂM TRA ĐỊNH DẠNG MẬT KHẨU TÀI KHOẢN (sv01, sv02) ---")
            for target_user in ["sv01", "sv02", "admin"]:
                row = conn.execute(
                    text("SELECT id, username, password_hash, role FROM users WHERE username = :u"),
                    {"u": target_user}
                ).fetchone()

                if not row:
                    print(f"  - Tài khoản '{target_user}': [KHÔNG TỒN TẠI TRONG DATABASE]")
                else:
                    phash = row.password_hash or ""
                    # Kiểm tra định dạng bcrypt chuẩn ($2b$ hoặc $2a$)
                    is_bcrypt = phash.startswith("$2b$") or phash.startswith("$2a$")
                    hash_len = len(phash)
                    status_fmt = "Chuẩn Bcrypt ($2a$/$2b$)" if is_bcrypt else "KHÔNG PHẢI định dạng Bcrypt hợp lệ"
                    print(f"  - Tài khoản '{target_user}': Tồn tại (ID={row.id}, Role={row.role}) | Hash: {status_fmt} (Độ dài: {hash_len})")

            print("\n" + "=" * 65)
            print("[+] Hoàn tất chẩn đoán!")
            return 0

    except Exception as e:
        print("\n[!] KẾT NỐI DATABASE THẤT BẠI!")
        print(f"[-] Chi tiết: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

