import requests
import numpy as np
from backend.app.config import settings
from fastapi import HTTPException

def get_embedding(text: str) -> bytes:
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": text
            }
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) == 0:
            raise Exception("No embeddings returned from Ollama")
        
        # Convert first embedding to numpy float32 and then bytes
        embedding_arr = np.array(embeddings[0], dtype=np.float32)
        return embedding_arr.tobytes()
    except requests.exceptions.Timeout as e:
        import logging
        logging.getLogger(__name__).exception("Ollama timeout in get_embedding")
        raise HTTPException(status_code=504, detail="Hệ thống đang quá tải, vui lòng thử lại sau.")
    except requests.exceptions.ConnectionError as e:
        import logging
        logging.getLogger(__name__).exception("Ollama connection error in get_embedding")
        raise HTTPException(status_code=503, detail="Hệ thống AI đang bảo trì, vui lòng thử lại sau.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ollama unknown error in get_embedding")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống nội bộ.")

def get_embeddings_batch(texts: list[str]) -> list[bytes]:
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": texts
            },
            timeout=settings.OLLAMA_TIMEOUT_EMBED
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(texts):
            raise Exception("Invalid embeddings returned from Ollama")
        
        result = []
        for emb in embeddings:
            embedding_arr = np.array(emb, dtype=np.float32)
            result.append(embedding_arr.tobytes())
        return result
    except requests.exceptions.Timeout as e:
        import logging
        logging.getLogger(__name__).exception("Ollama timeout in get_embeddings_batch")
        raise HTTPException(status_code=504, detail="Hệ thống đang quá tải, vui lòng thử lại sau.")
    except requests.exceptions.ConnectionError as e:
        import logging
        logging.getLogger(__name__).exception("Ollama connection error in get_embeddings_batch")
        raise HTTPException(status_code=503, detail="Hệ thống AI đang bảo trì, vui lòng thử lại sau.")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Ollama unknown error in get_embeddings_batch")
        raise HTTPException(status_code=500, detail="Lỗi hệ thống nội bộ.")
