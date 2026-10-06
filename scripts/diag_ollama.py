import subprocess, time, requests

print("--- ollama ps ---")
print(subprocess.getoutput("ollama ps"))

print("\n--- ollama list ---")
print(subprocess.getoutput("ollama list"))

print("\n--- RAM ---")
print(subprocess.getoutput("powershell -Command \"Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory\""))

print("\n--- Chat Time ---")
t0 = time.time()
try:
    r = requests.post("http://localhost:11434/api/chat", json={"model": "qwen2.5:7b", "messages": [{"role": "user", "content": "Xin chào"}], "stream": False})
    print(f"Status: {r.status_code}, Time: {time.time() - t0:.2f}s")
    print(r.json().get("message", {}).get("content"))
except Exception as e:
    print(f"Error: {e}")

print("\n--- Embed Time ---")
t0 = time.time()
try:
    r = requests.post("http://localhost:11434/api/embed", json={"model": "bge-m3:latest", "input": "Xin chào"})
    print(f"Status: {r.status_code}, Time: {time.time() - t0:.2f}s")
except Exception as e:
    print(f"Error: {e}")
