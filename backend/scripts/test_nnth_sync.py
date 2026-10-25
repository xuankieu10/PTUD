import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.config import settings
from backend.services.nnth_sync import (
    sync_nnth_data,
    get_upcoming_schedules,
    get_upcoming_exams,
    get_last_sync_info
)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("=== CHẠY ĐỒNG BỘ NNTH SYNC LẦN 1 ===")
res1 = sync_nnth_data(db)
print("Kết quả lần 1:", res1)

print("\n=== CHẠY ĐỒNG BỘ NNTH SYNC LẦN 2 (KIỂM TRA CHỐNG TRÙNG IDEMPOTENT) ===")
res2 = sync_nnth_data(db)
print("Kết quả lần 2:", res2)

schedules = get_upcoming_schedules(db)
print(f"\nSố khóa học sắp tới: {len(schedules)}")
for s in schedules:
    print(f" - [{s['loai']}] {s['ten_khoa_hoc']} | Khai giảng: {s['ngay_khai_giang_str']} | Học phí: {s['hoc_phi']}")

exams = get_upcoming_exams(db)
print(f"\nSố kỳ thi sắp tới: {len(exams)}")
for e in exams:
    status_dk = 'Dự kiến' if e['is_du_kien'] else 'Chính thức'
    print(f" - [{e['loai']} - {status_dk}] {e['ten_ky_thi']} | Ngày thi: {e['ngay_thi_str']} | Hạn ĐK: {e['han_dang_ky']} | Lệ phí: {e['le_phi_thi']}")

sync_info = get_last_sync_info(db)
print("\nThông tin lần đồng bộ gần nhất:", sync_info)
db.close()
