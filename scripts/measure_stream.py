import json
import time
import sys
import os
import io
import requests

# Đảm bảo in tiếng Việt chuẩn trên Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import tạo JWT token xác thực
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.security import create_access_token

BASE_URL = "http://127.0.0.1:8000"

def get_headers():
    token = create_access_token(subject=1, role="admin")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

QUESTIONS = [
    ("Q01", "Điều kiện để được xét tốt nghiệp đại học gồm những gì?"),
    ("Q11", "dieu kien xet tot nghiep nganh cong nghe thong tin la gi"),
    ("Q04", "Lệ phí nộp hồ sơ xét tốt nghiệp là bao nhiêu và nộp ở đâu?"),
]

def measure_stream_query(code: str, query: str):
    headers = get_headers()
    url = f"{BASE_URL}/chat/stream"
    payload = {"message": query}

    print(f"\n================================================================================")
    print(f"ĐO LƯỜNG STREAM CHO [{code}]: {query}")
    print(f"================================================================================")

    t0 = time.perf_counter()
    res = requests.post(url, json=payload, headers=headers, stream=True, timeout=300)

    if res.status_code != 200:
        print(f"Lỗi: HTTP Status {res.status_code} - {res.text}")
        return None

    token_timestamps = []
    tokens = []
    first_token_time = None
    done_payload = None

    for raw_line in res.iter_lines():
        if not raw_line:
            continue
        line_time = time.perf_counter() - t0
        line = raw_line.decode('utf-8')
        if line.startswith("data: "):
            data_str = line[6:].strip()
            try:
                data_obj = json.loads(data_str)
            except Exception as e:
                continue

            if not data_obj.get("done", False):
                token = data_obj.get("token", "")
                if token:
                    if first_token_time is None:
                        first_token_time = line_time
                    token_timestamps.append(line_time)
                    tokens.append(token)
            else:
                done_payload = data_obj
                break

    t_total = time.perf_counter() - t0
    last_token_time = token_timestamps[-1] if token_timestamps else None
    token_count = len(token_timestamps)

    # Tính khoảng cách trung bình giữa các token
    if token_count > 1:
        diffs = [token_timestamps[i] - token_timestamps[i-1] for i in range(1, token_count)]
        avg_interval = sum(diffs) / len(diffs)
    else:
        avg_interval = 0.0

    print(f"Kết quả đo:")
    print(f"  - Thời gian đến token đầu (TTFT): {first_token_time:.3f}s" if first_token_time else "  - Không nhận được token nào")
    print(f"  - Thời gian đến token cuối:       {last_token_time:.3f}s" if last_token_time else "  - N/A")
    print(f"  - Tổng thời gian stream:          {t_total:.3f}s")
    print(f"  - Tổng số sự kiện token:          {token_count}")
    print(f"  - Khoảng cách trung bình (token): {avg_interval * 1000:.2f} ms")
    
    first_5 = token_timestamps[:5]
    print(f"  - 5 mốc thời gian đầu tiên (s):   {[round(x, 3) for x in first_5]}")
    if len(tokens) >= 5:
        print(f"  - 5 token đầu tiên:               {[repr(t) for t in tokens[:5]]}")
    
    if done_payload:
        ans_preview = done_payload.get("answer", "")[:120].replace("\n", " ")
        print(f"  - Câu trả lời cuối (trích):       {ans_preview}...")
        print(f"  - Số nguồn (sources):             {len(done_payload.get('sources', []))}")

    return {
        "code": code,
        "query": query,
        "first_token": first_token_time,
        "last_token": last_token_time,
        "total_time": t_total,
        "token_count": token_count,
        "avg_interval": avg_interval,
        "first_5_timestamps": first_5
    }

def main():
    results = []
    for code, q in QUESTIONS:
        res = measure_stream_query(code, q)
        if res:
            results.append(res)

    print("\n\n" + "=" * 90)
    print("BẢNG TỔNG HỢP KẾT QUẢ ĐO STREAM")
    print("=" * 90)
    print(f"{'Mã':<6} | {'TTFT (s)':<10} | {'Token cuối (s)':<15} | {'Tổng (s)':<10} | {'Số token':<10} | {'Khoảng cách TB':<15}")
    print("-" * 90)
    for r in results:
        ft = f"{r['first_token']:.2f}s" if r['first_token'] else "N/A"
        lt = f"{r['last_token']:.2f}s" if r['last_token'] else "N/A"
        tot = f"{r['total_time']:.2f}s"
        cnt = str(r['token_count'])
        avg = f"{r['avg_interval']*1000:.1f} ms"
        print(f"{r['code']:<6} | {ft:<10} | {lt:<15} | {tot:<10} | {cnt:<10} | {avg:<15}")
    print("=" * 90)

if __name__ == "__main__":
    main()
