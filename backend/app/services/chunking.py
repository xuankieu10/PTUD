import re

def chunk_text(text: str, chunk_size: int = 600, chunk_overlap: int = 80) -> list[str]:
    """
    Chia text thành các chunk. Cố gắng chia theo đoạn văn, câu để giữ nguyên ý nghĩa tiếng Việt.
    """
    # Xóa khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Chia thành các câu (tương đối)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= chunk_size:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # Backtrack to create overlap if there are previous sentences
            # A simple overlap strategy: take the last characters of current_chunk up to chunk_overlap
            if chunks:
                # Find the start of the last sentence within the overlap window
                overlap_text = current_chunk[-chunk_overlap:]
                # Just prepend the sentence (this is a simplified overlap)
                current_chunk = sentence + " "
            else:
                current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks
