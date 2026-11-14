# -*- coding: utf-8 -*-
"""
Script Benchmark so sánh hiệu năng các LLM Inference Servers (Ollama vs LM Studio).
Đo đạc qua giao thức OpenAI API tương thích:
- TTFT (Time To First Token - thời gian sinh token đầu tiên)
- Tốc độ sinh (Token/giây)
- Tổng thời gian hoàn thành (giây)
- Mức tiêu thụ RAM của tiến trình server (MB)
- Ghi rõ Model, Quantization, Processor, Context Length, Backend
"""

import os
import sys
import time
import argparse
import requests
import psutil
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI

# -------------------------------------------------------------
# CẤU HÌNH MÁY CHỦ VÀ MODEL (ĐỐI SÁNH CÔNG BẰNG)
# Cả 2 đều dùng model Qwen2.5-VL 3B - Lượng tử hóa Q4_K_M - Context 2048 - 100% GPU
# -------------------------------------------------------------
SERVERS_CONFIG = {
    "Ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "qwen2.5vl:3b",
        "quantization": "Q4_K_M",
        "processor": "100% GPU",
        "context": 2048,
        "backend": "Vulkan",
        "extra_body": {
            "options": {
                "num_gpu": 99,
                "num_ctx": 2048
            }
        },
        "process_keywords": ["ollama.exe", "ollama_llama_server.exe", "ollama"],
    },
    "LM Studio": {
        "base_url": "http://localhost:1234/v1",
        "api_key": "lm-studio",
        "model": "qwen2.5-vl-3b-instruct",
        "quantization": "Q4_K_M",
        "processor": "100% GPU",
        "context": 2048,
        "backend": "CUDA",
        "extra_body": {},
        "process_keywords": ["LM Studio.exe", "lms.exe", "lmstudio"],
    },
}

QUESTIONS_FILE = "questions.txt"
RESULTS_CSV = "results.csv"
ANSWERS_CSV = "answers.csv"
CHART_IMAGE = "benchmark_comparison.png"
NUM_RUNS = 3  # Số lần chạy đo mỗi câu hỏi (lấy trung bình)
MAX_TOKENS = 200  # Giới hạn số token tối đa cho câu trả lời súc tích, tối ưu thời gian đo
WARMUP_PROMPT = "Chào bạn, hãy giới thiệu ngắn gọn trong 1 câu."


def get_server_ram_mb(process_keywords):
    """
    Tính tổng dung lượng RAM (RSS) của tất cả các tiến trình liên quan đến server (đơn vị MB).
    """
    total_rss = 0
    keywords = [kw.lower() for kw in process_keywords]
    for p in psutil.process_iter(['name', 'memory_info', 'cmdline']):
        try:
            p_name = (p.info.get('name') or '').lower()
            cmdline = " ".join(p.info.get('cmdline') or []).lower()
            for kw in keywords:
                if kw in p_name or kw in cmdline:
                    total_rss += p.info['memory_info'].rss
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return round(total_rss / (1024 * 1024), 2)


def check_server_connection(server_name, config):
    """
    Kiểm tra server có đang hoạt động hay không.
    Trả về: (is_online, client, actual_model_name)
    """
    base_url = config["base_url"]
    models_url = f"{base_url.rstrip('/')}/models"
    print(f"\n[Kiểm tra kết nối] Đang kiểm tra {server_name} tại {models_url} ...")
    try:
        resp = requests.get(models_url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            available_models = [m.get("id") for m in data.get("data", [])]
            print(f" -> {server_name} ONLINE. Các model khả dụng: {available_models}")

            target_model = config["model"]
            if target_model not in available_models and available_models:
                qwen_models = [m for m in available_models if "qwen" in m.lower()]
                if qwen_models:
                    target_model = qwen_models[0]
                else:
                    target_model = available_models[0]
                print(f" -> Lưu ý: Dùng model: '{target_model}'")

            client = OpenAI(
                base_url=base_url,
                api_key=config.get("api_key", "none")
            )
            return True, client, target_model
        else:
            print(f" -> {server_name} phản hồi HTTP {resp.status_code}. Bỏ qua server này.")
            return False, None, None
    except Exception as e:
        print(f" -> {server_name} không kết nối được ({e}). Bỏ qua server này.")
        return False, None, None


def warmup_server(client, model, server_name, extra_body=None):
    """
    Chạy warm-up trước khi tiến hành đo đạc chính thức.
    """
    print(f"[{server_name}] Đang chạy warm-up với prompt: '{WARMUP_PROMPT}' ...", end="", flush=True)
    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": WARMUP_PROMPT}],
            "stream": True,
            "temperature": 0.7,
            "max_tokens": 100
        }
        if extra_body:
            kwargs["extra_body"] = extra_body

        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            pass
        print(" Hoàn tất warm-up.")
    except Exception as e:
        print(f" Lỗi warm-up: {e}")


def run_benchmark_for_question(client, model, server_name, question, run_idx, process_keywords, extra_body=None):
    """
    Gửi câu hỏi ở chế độ streaming và đo đạc các chỉ số.
    """
    t_start = time.perf_counter()
    t_first_token = None
    chunks_count = 0
    answer_parts = []

    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0.7,
            "max_tokens": MAX_TOKENS
        }
        if extra_body:
            kwargs["extra_body"] = extra_body

        stream = client.chat.completions.create(**kwargs)

        for chunk in stream:
            if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    if t_first_token is None:
                        t_first_token = time.perf_counter()
                    answer_parts.append(content)
                    chunks_count += 1

        t_end = time.perf_counter()

        if t_first_token is None:
            t_first_token = t_end
            ttft = t_end - t_start
        else:
            ttft = t_first_token - t_start

        total_time = t_end - t_start
        gen_time = max(t_end - t_first_token, 0.001)
        speed = chunks_count / gen_time if chunks_count > 0 else 0.0
        ram_mb = get_server_ram_mb(process_keywords)
        full_answer = "".join(answer_parts).strip()

        return {
            "success": True,
            "ttft": round(ttft, 4),
            "speed": round(speed, 2),
            "total_time": round(total_time, 4),
            "tokens": chunks_count,
            "ram_mb": ram_mb,
            "answer": full_answer,
            "error": None
        }
    except Exception as e:
        t_end = time.perf_counter()
        return {
            "success": False,
            "ttft": None,
            "speed": None,
            "total_time": round(t_end - t_start, 4),
            "tokens": 0,
            "ram_mb": get_server_ram_mb(process_keywords),
            "answer": "",
            "error": str(e)
        }


def generate_charts(summary_df, output_path=CHART_IMAGE):
    """
    Vẽ biểu đồ so sánh các chỉ số giữa các Server bằng matplotlib.
    """
    if summary_df.empty:
        print("Không có dữ liệu để vẽ biểu đồ.")
        return

    summary_df = summary_df.sort_values(by="Server").reset_index(drop=True)
    servers_label = [
        f"{row['Server']}\n({row['Processor']} | Ctx: {row['Context']} | {row['Backend']})"
        for _, row in summary_df.iterrows()
    ]
    ttft_vals = summary_df["Avg_TTFT_sec"].tolist()
    speed_vals = summary_df["Avg_Speed_tok_per_sec"].tolist()
    total_time_vals = summary_df["Avg_Total_Time_sec"].tolist()
    ram_vals = summary_df["Avg_RAM_MB"].tolist()

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        "So sánh hiệu năng LLM Inference Servers (Ollama vs LM Studio)\nCùng quy mô 3B (Q4_K_M) - 100% GPU - Context 2048",
        fontsize=15,
        fontweight='bold'
    )

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'][:len(servers_label)]

    # 1. Thời gian ra token đầu tiên (TTFT)
    ax1 = axes[0, 0]
    bars1 = ax1.bar(servers_label, ttft_vals, color=colors, width=0.45)
    ax1.set_title("1. Thời gian ra token đầu (TTFT) - Giây (Thấp hơn tốt hơn)", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Giây")
    ax1.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.3f}s", ha='center', va='bottom', fontweight='bold')

    # 2. Tốc độ sinh token (Tokens / giây)
    ax2 = axes[0, 1]
    bars2 = ax2.bar(servers_label, speed_vals, color=colors, width=0.45)
    ax2.set_title("2. Tốc độ sinh token - Tokens/s (Cao hơn tốt hơn)", fontsize=11, fontweight='bold')
    ax2.set_ylabel("Tokens / giây")
    ax2.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.2f} t/s", ha='center', va='bottom', fontweight='bold')

    # 3. Tổng thời gian hoàn thành câu trả lời
    ax3 = axes[1, 0]
    bars3 = ax3.bar(servers_label, total_time_vals, color=colors, width=0.45)
    ax3.set_title("3. Tổng thời gian trả lời - Giây (Thấp hơn tốt hơn)", fontsize=11, fontweight='bold')
    ax3.set_ylabel("Giây")
    ax3.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.2f}s", ha='center', va='bottom', fontweight='bold')

    # 4. Mức tiêu thụ RAM của tiến trình
    ax4 = axes[1, 1]
    bars4 = ax4.bar(servers_label, ram_vals, color=colors, width=0.45)
    ax4.set_title("4. Tiêu thụ RAM của Server - MB", fontsize=11, fontweight='bold')
    ax4.set_ylabel("RAM (MB)")
    ax4.grid(axis='y', linestyle='--', alpha=0.7)
    for bar in bars4:
        yval = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2.0, yval, f"{yval:.0f} MB", ha='center', va='bottom', fontweight='bold')

    plt.tight_layout(rect=[0, 0.03, 1, 0.94])
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"\n[Biểu đồ] Đã lưu biểu đồ so sánh tại: {output_path}")


def summarize_and_report():
    """
    Đọc results.csv, tính toán trung bình, in bảng Markdown và xuất biểu đồ.
    """
    if not os.path.exists(RESULTS_CSV):
        print(f"Chưa có tệp {RESULTS_CSV} để tổng hợp.")
        return

    df_results = pd.read_csv(RESULTS_CSV)
    success_df = df_results[df_results["Success"] == True]
    if success_df.empty:
        print("Không có lượt chạy thành công nào.")
        return

    group_cols = ["Server", "Model"]
    for col in ["Quantization", "Processor", "Context", "Backend"]:
        if col in success_df.columns:
            group_cols.append(col)

    summary = success_df.groupby(group_cols).agg(
        Total_Questions=("Question_ID", "nunique"),
        Total_Runs=("Run", "count"),
        Avg_TTFT_sec=("TTFT_sec", "mean"),
        Avg_Speed_tok_per_sec=("Speed_tok_per_sec", "mean"),
        Avg_Total_Time_sec=("Total_Time_sec", "mean"),
        Avg_RAM_MB=("RAM_MB", "mean")
    ).reset_index()

    summary["Avg_TTFT_sec"] = summary["Avg_TTFT_sec"].round(4)
    summary["Avg_Speed_tok_per_sec"] = summary["Avg_Speed_tok_per_sec"].round(2)
    summary["Avg_Total_Time_sec"] = summary["Avg_Total_Time_sec"].round(2)
    summary["Avg_RAM_MB"] = summary["Avg_RAM_MB"].round(1)

    print("\n" + "=" * 70)
    print("BẢNG SO SÁNH TỔNG HỢP HIỆU NĂNG CÁC LLM SERVERS (TRUNG BÌNH)")
    print("=" * 70)
    try:
        print(summary.to_markdown(index=False))
    except Exception:
        headers = list(summary.columns)
        print("| " + " | ".join(headers) + " |")
        print("| " + " | ".join(["---"] * len(headers)) + " |")
        for _, row in summary.iterrows():
            print("| " + " | ".join(str(val) for val in row.values) + " |")

    generate_charts(summary, CHART_IMAGE)


def main():
    parser = argparse.ArgumentParser(description="LLM Benchmark Runner")
    parser.add_argument("--server", type=str, default=None, help="Chỉ đo server cụ thể (Ollama, LM Studio)")
    parser.add_argument("--summary-only", action="store_true", help="Chỉ tổng hợp từ results.csv đã có")
    args = parser.parse_args()

    if args.summary_only:
        summarize_and_report()
        return

    print("=" * 70)
    print("   BẮT ĐẦU CHƯƠNG TRÌNH BENCHMARK LLM INFERENCE SERVERS")
    print("=" * 70)

    if not os.path.exists(QUESTIONS_FILE):
        print(f"Lỗi: Không tìm thấy file {QUESTIONS_FILE}!")
        sys.exit(1)

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

    print(f"-> Đã đọc {len(questions)} câu hỏi từ {QUESTIONS_FILE}.")

    targets = SERVERS_CONFIG
    if args.server:
        matched = {k: v for k, v in SERVERS_CONFIG.items() if k.lower() == args.server.lower()}
        if not matched:
            print(f"Lỗi: Không tìm thấy cấu hình cho server '{args.server}'")
            sys.exit(1)
        targets = matched

    active_servers = {}
    for s_name, s_cfg in targets.items():
        is_online, client, actual_model = check_server_connection(s_name, s_cfg)
        if is_online:
            active_servers[s_name] = {
                "client": client,
                "model": actual_model,
                "quantization": s_cfg.get("quantization", "Unknown"),
                "processor": s_cfg.get("processor", "Unknown"),
                "context": s_cfg.get("context", 2048),
                "backend": s_cfg.get("backend", "Unknown"),
                "extra_body": s_cfg.get("extra_body", {}),
                "process_keywords": s_cfg["process_keywords"],
                "base_url": s_cfg["base_url"]
            }

    if not active_servers:
        print("\nKhông có server nào khả dụng để benchmark. Vui lòng bật server!")
        sys.exit(1)

    print(f"\n-> Server thực hiện đo ({len(active_servers)}): {list(active_servers.keys())}")

    for s_name, s_info in active_servers.items():
        warmup_server(s_info["client"], s_info["model"], s_name, s_info["extra_body"])

    existing_results = []
    existing_answers = []
    if os.path.exists(RESULTS_CSV):
        try:
            df_old_res = pd.read_csv(RESULTS_CSV)
            df_old_res = df_old_res[~df_old_res["Server"].isin(active_servers.keys())]
            existing_results = df_old_res.to_dict("records")
        except Exception:
            existing_results = []

    if os.path.exists(ANSWERS_CSV):
        try:
            df_old_ans = pd.read_csv(ANSWERS_CSV)
            df_old_ans = df_old_ans[~df_old_ans["Server"].isin(active_servers.keys())]
            existing_answers = df_old_ans.to_dict("records")
        except Exception:
            existing_answers = []

    new_results = []
    new_answers = []

    total_steps = len(active_servers) * len(questions) * NUM_RUNS
    step = 0

    print("\n" + "=" * 70)
    print(f"TIẾN HÀNH ĐO ĐẠC: Mỗi câu chạy {NUM_RUNS} lần, lấy số liệu trung bình")
    print("=" * 70)

    for s_name, s_info in active_servers.items():
        client = s_info["client"]
        model = s_info["model"]
        quant = s_info["quantization"]
        proc = s_info["processor"]
        ctx = s_info["context"]
        backend = s_info["backend"]
        extra = s_info["extra_body"]
        keywords = s_info["process_keywords"]

        print(f"\n>>> Đang benchmark server: {s_name} (Model: {model} | Quant: {quant} | Proc: {proc} | Ctx: {ctx} | Backend: {backend}) <<<")

        for q_idx, q_text in enumerate(questions, start=1):
            for run_num in range(1, NUM_RUNS + 1):
                step += 1
                prefix = f"[{step}/{total_steps}] [{s_name} - Q{q_idx:02d} - Run {run_num}/{NUM_RUNS}]"
                print(f"{prefix} '{q_text[:35]}...' ", end="", flush=True)

                res = run_benchmark_for_question(client, model, s_name, q_text, run_num, keywords, extra)

                if res["success"]:
                    print(f"-> TTFT: {res['ttft']:.3f}s | Tốc độ: {res['speed']:.1f} tok/s | Tổng: {res['total_time']:.2f}s | RAM: {res['ram_mb']:.0f} MB")
                else:
                    print(f"-> LỖI: {res['error']}")

                new_results.append({
                    "Server": s_name,
                    "Model": model,
                    "Quantization": quant,
                    "Processor": proc,
                    "Context": ctx,
                    "Backend": backend,
                    "Question_ID": q_idx,
                    "Question": q_text,
                    "Run": run_num,
                    "Success": res["success"],
                    "TTFT_sec": res["ttft"],
                    "Speed_tok_per_sec": res["speed"],
                    "Total_Time_sec": res["total_time"],
                    "Tokens_Generated": res["tokens"],
                    "RAM_MB": res["ram_mb"],
                    "Error": res["error"]
                })

                new_answers.append({
                    "Server": s_name,
                    "Model": model,
                    "Quantization": quant,
                    "Processor": proc,
                    "Context": ctx,
                    "Backend": backend,
                    "Question_ID": q_idx,
                    "Question": q_text,
                    "Run": run_num,
                    "Answer": res["answer"],
                    "Tokens": res["tokens"],
                    "Speed_tok_per_sec": res["speed"],
                    "Total_Time_sec": res["total_time"]
                })

    all_results = existing_results + new_results
    df_results = pd.DataFrame(all_results)
    df_results.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[Lưu tệp] Đã lưu dữ liệu đo chi tiết vào: {RESULTS_CSV}")

    all_answers = existing_answers + new_answers
    df_answers = pd.DataFrame(all_answers)
    df_answers.to_csv(ANSWERS_CSV, index=False, encoding="utf-8-sig")
    print(f"[Lưu tệp] Đã lưu câu trả lời vào: {ANSWERS_CSV}")

    summarize_and_report()
    print("\nBenchmark hoàn tất!")


if __name__ == "__main__":
    main()
