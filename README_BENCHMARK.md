# Hướng dẫn Benchmark So sánh LLM Inference Servers (Ollama vs LM Studio)

Tài liệu này hướng dẫn cách cấu hình và thực hiện benchmark so sánh hiệu năng các inference server cục bộ (**Ollama** và **LM Studio**) phục vụ chatbot tư vấn học vụ.

---

## 1. Môi trường Thực nghiệm & Thông số Mô hình

Để đảm bảo tính khách quan và khoa học, hai công cụ được đo đạc với các điều kiện cấu hình tương đồng tuyệt đối:
- **Kiến trúc mô hình**: Qwen2.5-VL 3.8B tham số (`qwen2.5vl:3b` trên Ollama, `qwen2.5-vl-3b-instruct` trên LM Studio).
- **Mức lượng tử hóa (Quantization)**: `Q4_K_M`.
- **Processor**: **100% GPU** (Offload toàn bộ 37/37 layers lên GPU NVIDIA GeForce RTX 3050 Laptop).
- **Context Length**: `2048` tokens cho cả hai bên.
- **Backend Runtime**:
  - **Ollama**: `Vulkan` runner (`OLLAMA_VULKAN: true` trong server config).
  - **LM Studio**: `CUDA` runner (thông qua engine llama.cpp tối ưu CUDA của LM Studio).
- **Nguyên tắc cô lập tài nguyên**: Đo độc lập từng server; khi đo bên này thì tắt hoàn toàn tiến trình bên kia để tránh tranh chấp VRAM GPU và CPU.

---

## 2. Cài đặt môi trường

Cài đặt các gói phụ thuộc trong Python virtualenv:

```bash
.\venv\Scripts\python.exe -m pip install openai psutil matplotlib pandas tabulate
```

---

## 3. Cách chạy Benchmark từng server

### Bước 1: Đo Ollama (100% GPU)
1. Đảm bảo LM Studio đã tắt hoàn toàn.
2. Khởi động Ollama và chạy đo đạc:
   ```bash
   .\venv\Scripts\python.exe -u benchmark.py --server Ollama
   ```
   *(Script sẽ tự động truyền options `num_gpu=99`, `num_ctx=2048` để đảm bảo 100% GPU offload)*.

### Bước 2: Đo LM Studio (100% GPU - Context 2048)
1. Tắt dịch vụ Ollama:
   ```powershell
   Stop-Process -Name "*ollama*" -Force
   ```
2. Khởi chạy LM Studio và load model với context 2048:
   ```powershell
   $env:ELECTRON_RUN_AS_NODE = $null
   lms server start
   lms load qwen2.5-vl-3b-instruct -y --gpu max -c 2048
   ```
3. Chạy đo đạc cho LM Studio:
   ```bash
   .\venv\Scripts\python.exe -u benchmark.py --server "LM Studio"
   ```

---

## 4. Tệp kết quả xuất ra

- `results.csv`: Dữ liệu thô 90 lượt đo chi tiết với các trường: `Server`, `Model`, `Quantization`, `Processor`, `Context`, `Backend`, `Question_ID`, `Question`, `Run`, `TTFT_sec`, `Speed_tok_per_sec`, `Total_Time_sec`, `Tokens_Generated`, `RAM_MB`.
- `answers.csv`: Toàn bộ 90 câu trả lời sinh ra từ 15 câu hỏi học vụ tiếng Việt để phục vụ chấm điểm chất lượng nội dung.
- `benchmark_comparison.png`: Biểu đồ cột trực quan 4 chỉ số (TTFT, Tốc độ, Tổng thời gian, RAM) xuất ra từ Matplotlib.
- `questions.txt`: 15 câu hỏi học vụ tiếng Việt thực tế.
