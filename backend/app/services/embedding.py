from collections import OrderedDict
import requests
import numpy as np
from backend.app.config import settings
from fastapi import HTTPException

# Bộ nhớ đệm LRU in-memory lưu trữ embedding cho câu hỏi lặp lại (tránh gọi lại Ollama embed)
_EMBED_LRU_CACHE: OrderedDict[str, bytes] = OrderedDict()
_MAX_EMBED_CACHE_SIZE = 1024


def _get_from_cache(key: str) -> bytes | None:
    """Lấy embedding từ LRU cache nếu có và cập nhật thứ tự truy cập."""
    if key in _EMBED_LRU_CACHE:
        _EMBED_LRU_CACHE.move_to_end(key)
        return _EMBED_LRU_CACHE[key]
    return None


def _put_to_cache(key: str, val: bytes):
    """Lưu embedding vào LRU cache, giải phóng mục cũ nhất nếu vượt kích thước."""
    if key in _EMBED_LRU_CACHE:
        _EMBED_LRU_CACHE.move_to_end(key)
    else:
        if len(_EMBED_LRU_CACHE) >= _MAX_EMBED_CACHE_SIZE:
            _EMBED_LRU_CACHE.popitem(last=False)
    _EMBED_LRU_CACHE[key] = val


def get_embedding(text: str) -> bytes:
    # 1. Kiểm tra cache câu hỏi trước khi gọi Ollama
    cached = _get_from_cache(text)
    if cached is not None:
        return cached

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": text
            },
            timeout=settings.OLLAMA_TIMEOUT_EMBED
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) == 0:
            raise Exception("No embeddings returned from Ollama")

        # Convert first embedding to numpy float32 and then bytes
        embedding_arr = np.array(embeddings[0], dtype=np.float32)
        res_bytes = embedding_arr.tobytes()
        _put_to_cache(text, res_bytes)
        return res_bytes
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
    if not texts:
        return []

    # 1. Kiểm tra LRU cache để chỉ nhúng các chuỗi chưa có trong bộ nhớ
    results: list[bytes | None] = [None] * len(texts)
    missing_indices: list[int] = []
    missing_texts: list[str] = []

    for idx, t in enumerate(texts):
        cached = _get_from_cache(t)
        if cached is not None:
            results[idx] = cached
        else:
            missing_indices.append(idx)
            missing_texts.append(t)

    # Nếu tất cả đều có trong cache, trả về ngay lập tức
    if not missing_texts:
        return [r for r in results if r is not None]

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.EMBEDDING_MODEL,
                "input": missing_texts
            },
            timeout=settings.OLLAMA_TIMEOUT_EMBED
        )
        response.raise_for_status()
        data = response.json()
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(missing_texts):
            raise Exception("Invalid embeddings returned from Ollama")

        for k, emb in enumerate(embeddings):
            embedding_arr = np.array(emb, dtype=np.float32)
            emb_bytes = embedding_arr.tobytes()
            orig_idx = missing_indices[k]
            results[orig_idx] = emb_bytes
            # Lưu vào LRU cache
            _put_to_cache(missing_texts[k], emb_bytes)

        return [r for r in results if r is not None]
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

