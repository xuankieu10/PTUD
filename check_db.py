"""
check_db.py
Kiểm tra kết nối SQL Server và đếm số lượng bản ghi các bảng chính trong DB HocVuAI.
Sử dụng cấu hình DATABASE_URL từ backend.app.config.
"""
import sys
from sqlalchemy import create_engine, text
from backend.app.config import settings

def main():
    print("=" * 60)
    print("KIỂM TRA KẾT NỐI DATABASE HOCVUAI")
    print("=" * 60)
    print(f"[*] DATABASE_URL: {settings.DATABASE_URL}")
    print("[*] Đang thử kết nối (timeout 10s)...")

    # Tạo engine với timeout kết nối 10 giây
    connect_args = {"timeout": 10}
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        with engine.connect() as conn:
            print("[+] KẾT NỐI DATABASE THÀNH CÔNG (OK)!")
            print("-" * 60)
            
            # Danh sách các bảng chính cần kiểm tra
            tables = [
                "users",
                "students",
                "grades",
                "document_chunks",
                "chat_sessions",
                "chat_messages",
                "student_certificates",
                "student_ocr_transcripts"
            ]

            for table in tables:
                try:
                    query = text(f"SELECT COUNT(*) FROM {table}")
                    result = conn.execute(query).scalar()
                    print(f"  - Bảng [{table:<25}]: {result:>6} bản ghi")
                except Exception as e_tbl:
                    print(f"  - Bảng [{table:<25}]: [Không tìm thấy hoặc lỗi: {e_tbl}]")

            print("-" * 60)
            print("[+] Kiểm tra hoàn tất!")
            return 0

    except Exception as e:
        print("\n[!] KẾT NỐI THẤT BẠI!")
        print(f"[-] Chi tiết lỗi: {e}")
        print("\n[*] GỢI Ý KHẮC PHỤC:")
        print("  1. Mở SQL Server Management Studio (SSMS) xem tên Server thực tế lúc Connect.")
        print("  2. Nếu SSMS dùng DESKTOP-SE6T8ME\\SQLEXPRESS hoặc .\\SQLEXPRESS01:")
        print("     Hãy sửa biến DATABASE_URL trong .env cho tương ứng.")
        print("  3. Đảm bảo SQL Server Service (SQLEXPRESS hoặc SQLEXPRESS01) đang ở trạng thái RUNNING.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

