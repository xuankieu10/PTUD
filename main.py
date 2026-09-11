"""
Entrypoint tiện lợi từ thư mục gốc của dự án.
Chuyển tiếp lệnh gọi vào backend/main.py
"""

import os
import sys

# Thêm thư mục hiện tại vào sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import main

if __name__ == "__main__":
    main()
