import sys, os, time, sqlite3
sys.path.insert(0, 'D:/PTUD')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.scripts.seed_dataset import build_knowledge_base_chunks
from backend.scripts.ingest_quy_dinh import parse_docx_chunks, find_docx_file
from backend.app.services.embedding import get_embeddings_batch

print("Checking chunk extraction...")
t0 = time.time()
chunks_doc1, chunks_doc2 = build_knowledge_base_chunks()
print(f"Doc 79: {len(chunks_doc1)} chunks, Doc 80: {len(chunks_doc2)} chunks")

docx_path = find_docx_file()
chunks_doc9001 = parse_docx_chunks(docx_path)
print(f"Doc 9001: {len(chunks_doc9001)} chunks")
print(f"Total chunks: {len(chunks_doc1) + len(chunks_doc2) + len(chunks_doc9001)} chunks")
print(f"Extracted in {time.time() - t0:.2f}s")
