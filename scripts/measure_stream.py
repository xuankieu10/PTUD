import json
import time
import sys
import os
import io
import statistics
import requests

# Đảm bảo in tiếng Việt chuẩn trên Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import tạo JWT token xác thực
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.security import create_access_token

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

def get_headers():
    token = create_access_token(subject=1, role="admin")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

# 6 câu hỏi đo sạch của Nhiệm vụ A (chưa từng chạy trước đây)
QUESTIONS_A = [
    ("A1", "Sinh viên bị kỷ luật cảnh cáo có được xét tốt nghiệp không?"),
    ("A2", "Hồ sơ xét tốt nghiệp nộp trực tuyến ở đâu?"),
    ("A3", "Chuẩn đầu ra tin học của sinh viên CNTT là gì?"),
    ("A4", "Giáo dục quốc phòng có cần để xét tốt nghiệp không?"),
    ("A5", "Chưa có chứng chỉ ngoại ngữ thì có nhận được giấy chứng nhận hoàn thành không?"),
    ("A6", "Tổng số tín chỉ tích luỹ tối thiểu để tốt nghiệp là bao nhiêu?"),
]

def warmup_model():
    """Khởi động nóng model bằng một câu vô hại, loại bỏ thời gian tải mô hình ban đầu vào RAM/VRAM."""
    headers = get_headers()
    url = f"{BASE_URL}/chat/stream"
    payload = {"message": "xin chào"}
    print("\n[WARMUP] Đang khởi động nóng mô hình với 'xin chào'...")
    t0 = time.perf_counter()
    try:
        res = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
        for _ in res.iter_lines():
            pass
        t_w = time.perf_counter() - t0
        print(f"[WARMUP] Hoàn tất sau {t_w:.2f}s. Model đã sẵn sàng.")
    except Exception as e:
        print(f"[WARMUP] Lỗi warmup: {e}")

def measure_stream_query(code: str, query: str, run_label: str = "Lần 1"):
    headers = get_headers()
    url = f"{BASE_URL}/chat/stream"
    payload = {"message": query}

    print(f"\n================================================================================")
    print(f"ĐO LƯỜNG STREAM [{run_label}] CHO [{code}]: {query}")
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
            except Exception:
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

    # Đọc các thông số hiệu năng từ chunk cuối Ollama
    prompt_eval_count = done_payload.get("prompt_eval_count") if done_payload else None
    prompt_eval_duration_ms = (done_payload.get("prompt_eval_duration", 0) / 1e6) if done_payload and done_payload.get("prompt_eval_duration") else None
    eval_count = done_payload.get("eval_count") if done_payload else None
    eval_duration_ms = (done_payload.get("eval_duration", 0) / 1e6) if done_payload and done_payload.get("eval_duration") else None
    load_duration_ms = (done_payload.get("load_duration", 0) / 1e6) if done_payload and done_payload.get("load_duration") else None

    # Tính khoảng cách trung bình giữa các token
    if token_count > 1:
        diffs = [token_timestamps[i] - token_timestamps[i-1] for i in range(1, token_count)]
        avg_interval = sum(diffs) / len(diffs)
    else:
        avg_interval = 0.0

    print(f"Kết quả đo [{run_label}]:")
    print(f"  - Thời gian đến token đầu (TTFT): {first_token_time:.3f}s" if first_token_time else "  - Không nhận được token nào")
    print(f"  - Thời gian đến token cuối:       {last_token_time:.3f}s" if last_token_time else "  - N/A")
    print(f"  - Tổng thời gian stream:          {t_total:.3f}s")
    print(f"  - Tổng số token sinh ra:          {token_count}")
    print(f"  - Khoảng cách trung bình (token): {avg_interval * 1000:.2f} ms")
    print(f"  - Ollama prompt_eval_count:       {prompt_eval_count}")
    print(f"  - Ollama prompt_eval_duration:    {prompt_eval_duration_ms:.2f} ms" if prompt_eval_duration_ms else "  - Ollama prompt_eval_duration:    N/A")
    print(f"  - Ollama eval_count:              {eval_count}")
    print(f"  - Ollama load_duration:           {load_duration_ms:.2f} ms" if load_duration_ms else "  - Ollama load_duration:           N/A")

    if done_payload:
        ans_preview = done_payload.get("answer", "")[:120].replace("\n", " ")
        print(f"  - Câu trả lời (trích):            {ans_preview}...")
        print(f"  - Số nguồn (sources):             {len(done_payload.get('sources', []))}")
        sid = done_payload.get("session_id")
        if sid:
            try:
                requests.delete(f"{BASE_URL}/chat/sessions/{sid}", headers=headers, timeout=5)
            except Exception:
                pass

    return {
        "code": code,
        "query": query,
        "first_token": first_token_time,
        "last_token": last_token_time,
        "total_time": t_total,
        "token_count": token_count,
        "avg_interval": avg_interval,
        "prompt_eval_count": prompt_eval_count,
        "prompt_eval_duration_ms": prompt_eval_duration_ms,
        "eval_count": eval_count,
        "eval_duration_ms": eval_duration_ms,
        "load_duration_ms": load_duration_ms,
    }

def run_benchmarks(tag: str = "TOP_K=3"):
    print(f"\n================================================================================")
    print(f"BẮT ĐẦU CHU KỲ ĐO CHO CẤU HÌNH: {tag}")
    print(f"================================================================================")

    # 1. Warmup
    warmup_model()

    # 2. Lần 1: Chạy 6 câu chưa từng chạy (sạch, không cache)
    print("\n>>> BẮT ĐẦU LẦN 1: ĐO SẠCH (KHÔNG CACHE)")
    results_run1 = {}
    for code, q in QUESTIONS_A:
        r = measure_stream_query(code, q, run_label="Lần 1 (Không cache)")
        if r:
            results_run1[code] = r

    # 3. Lần 2: Lặp lại đúng 6 câu để xem hiệu ứng bộ nhớ đệm (có cache)
    print("\n>>> BẮT ĐẦU LẦN 2: ĐO CÓ CACHE (LẶP LẠI)")
    results_run2 = {}
    for code, q in QUESTIONS_A:
        r = measure_stream_query(code, q, run_label="Lần 2 (Có cache)")
        if r:
            results_run2[code] = r

    # 4. In bảng so sánh
    print("\n\n" + "=" * 115)
    print(f"BẢNG KẾT QUẢ ĐO LƯỜNG STREAM ({tag})")
    print("=" * 115)
    print(f"{'Mã':<4} | {'TTFT L1 (s)':<12} | {'TTFT L2 (s)':<12} | {'PromptEval L1':<14} | {'PromptEval L2':<14} | {'Tổng T1 (s)':<12} | {'Tổng T2 (s)':<12}")
    print("-" * 115)

    ttfts_r1 = []
    for code, q in QUESTIONS_A:
        r1 = results_run1.get(code, {})
        r2 = results_run2.get(code, {})

        ft1 = f"{r1.get('first_token', 0):.3f}s" if r1.get('first_token') is not None else "N/A"
        ft2 = f"{r2.get('first_token', 0):.3f}s" if r2.get('first_token') is not None else "N/A"
        pe1 = str(r1.get('prompt_eval_count', 'N/A'))
        pe2 = str(r2.get('prompt_eval_count', 'N/A'))
        tot1 = f"{r1.get('total_time', 0):.2f}s" if r1.get('total_time') is not None else "N/A"
        tot2 = f"{r2.get('total_time', 0):.2f}s" if r2.get('total_time') is not None else "N/A"

        if r1.get('first_token') is not None:
            ttfts_r1.append(r1['first_token'])

        print(f"{code:<4} | {ft1:<12} | {ft2:<12} | {pe1:<14} | {pe2:<14} | {tot1:<12} | {tot2:<12}")

    print("=" * 115)
    if ttfts_r1:
        med_ttft_r1 = statistics.median(ttfts_r1)
        mean_ttft_r1 = statistics.mean(ttfts_r1)
        print(f"Trung vị TTFT Lần 1 (chính thức): {med_ttft_r1:.3f}s | Trung bình TTFT Lần 1: {mean_ttft_r1:.3f}s")
    print("=" * 115)

    return {
        "tag": tag,
        "run1": results_run1,
        "run2": results_run2,
        "median_ttft_run1": statistics.median(ttfts_r1) if ttfts_r1 else None
    }

if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "TOP_K=3"
    run_benchmarks(tag)
