import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from backend.app.services.chunking import chunk_text
text = "Đây là đoạn một. " * 200
chunks = chunk_text(text)
print("Số chunk:", len(chunks))
for i, c in enumerate(chunks):
    print(f"Chunk {i+1} độ dài: {len(c)}")
    
if len(chunks) > 1:
    overlap = len(set(chunks[0].split()) & set(chunks[1].split()))
    print("Overlap estimated words:", overlap)
