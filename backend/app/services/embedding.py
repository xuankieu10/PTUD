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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting embedding: {str(e)}")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting embeddings batch: {str(e)}")
