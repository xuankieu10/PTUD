"""
scripts/migrate_auth_provider.py
Script migration idempotent bổ sung cột auth_provider cho bảng users.
Chạy an toàn trên cả DB local và DB môi trường production/VPS.
Tự động kiểm tra cột đã tồn tại chưa trước khi ALTER, mặc định 'local' cho dòng cũ.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import text
from backend.app.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MigrateAuthProvider")


def migrate():
    logger.info("Bắt đầu kiểm tra và thực hiện migration cột auth_provider...")
    with engine.connect() as conn:
        # Kiểm tra xem cột auth_provider đã tồn tại trong bảng users chưa
        check_sql = text("""
            SELECT 1 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'auth_provider'
        """)
        exists = conn.execute(check_sql).fetchone() is not None

        if not exists:
            logger.info("Cột auth_provider chưa tồn tại. Đang tiến hành ALTER TABLE...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD auth_provider NVARCHAR(50) NULL CONSTRAINT DF_users_auth_provider DEFAULT 'local';
            """))
            conn.commit()
            logger.info("Đã thêm cột auth_provider vào bảng users.")
        else:
            logger.info("Cột auth_provider đã tồn tại trong bảng users. Bỏ qua bước ALTER.")

        # Đảm bảo toàn bộ dòng cũ không bị NULL
        update_sql = text("UPDATE users SET auth_provider = 'local' WHERE auth_provider IS NULL;")
        result = conn.execute(update_sql)
        conn.commit()
        logger.info(f"Đã cập nhật các dòng có auth_provider IS NULL về 'local' (Số dòng ảnh hưởng: {result.rowcount}).")

        # Kiểm tra lại cấu trúc cột
        col_info = conn.execute(text("""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_DEFAULT, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'users' AND COLUMN_NAME = 'auth_provider'
        """)).fetchone()
        logger.info(f"Cấu trúc hiện tại: {col_info}")
        logger.info("Migration hoàn tất thành công và an toàn.")


if __name__ == "__main__":
    migrate()
