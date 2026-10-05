import os
import io
import docx
import pdfplumber
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db import get_db
from backend.app.deps import get_current_user, require_admin
from backend.app.services.chunking import chunk_text
from backend.app.services.embedding import get_embeddings_batch
from backend.app.config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

def extract_text(file: UploadFile, content: bytes) -> str:
    filename = file.filename.lower()
    text_content = ""
    if filename.endswith('.pdf'):
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
    elif filename.endswith('.docx'):
        doc = docx.Document(io.BytesIO(content))
        for para in doc.paragraphs:
            text_content += para.text + "\n"
    elif filename.endswith('.txt'):
        text_content = content.decode('utf-8', errors='ignore')
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    return text_content.strip()

@router.post("")
def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin)
):
    # limit size checking, e.g. 10MB
    content = file.file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")
        
    try:
        # Create document
        doc_id = db.execute(
            text("INSERT INTO documents (title, source, status, uploaded_by) OUTPUT INSERTED.id VALUES (:title, :source, 'pending', :uid)"),
            {"title": title, "source": file.filename, "uid": admin_user["id"]}
        ).scalar()
        db.commit()

        # Extract text
        text_content = extract_text(file, content)
        if not text_content:
            raise Exception("No text could be extracted")

        # Chunk text
        chunks = chunk_text(text_content, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

        # Batch embed and insert
        batch_size = 16
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i+batch_size]
            embeddings = get_embeddings_batch(batch_chunks)
            
            for j, chunk_str in enumerate(batch_chunks):
                chunk_index = i + j
                db.execute(
                    text("INSERT INTO document_chunks (document_id, chunk_index, content, embedding) VALUES (:did, :idx, :content, :emb)"),
                    {"did": doc_id, "idx": chunk_index, "content": chunk_str, "emb": embeddings[j]}
                )
        
        # Update status
        db.execute(text("UPDATE documents SET status = 'indexed' WHERE id = :did"), {"did": doc_id})
        db.commit()

        return {"id": doc_id, "title": title, "status": "indexed", "chunks": len(chunks)}

    except Exception as e:
        db.rollback()
        if 'doc_id' in locals():
            db.execute(text("UPDATE documents SET status = 'failed' WHERE id = :did"), {"did": doc_id})
            db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
def get_documents(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    docs = db.execute(text("""
        SELECT d.id, d.title, d.status, d.created_at, COUNT(c.id) as num_chunks
        FROM documents d
        LEFT JOIN document_chunks c ON d.id = c.document_id
        GROUP BY d.id, d.title, d.status, d.created_at
        ORDER BY d.id DESC
    """)).fetchall()
    
    return [{"id": d.id, "title": d.title, "status": d.status, "num_chunks": d.num_chunks, "created_at": d.created_at} for d in docs]

@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    doc = db.execute(text("SELECT id, title, status, source, created_at FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = db.execute(
        text("SELECT chunk_index, content FROM document_chunks WHERE document_id = :id ORDER BY chunk_index ASC OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY"), 
        {"id": doc_id}
    ).fetchall()
    
    return {
        "id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "source": doc.source,
        "created_at": doc.created_at,
        "sample_chunks": [{"index": c.chunk_index, "content": c.content} for c in chunks]
    }

@router.put("/{doc_id}")
def update_document(
    doc_id: int,
    title: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    admin_user: dict = Depends(require_admin)
):
    doc = db.execute(text("SELECT id FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if title:
        db.execute(text("UPDATE documents SET title = :t WHERE id = :id"), {"t": title, "id": doc_id})
        db.commit()
        
    if file:
        content = file.file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")
            
        try:
            db.execute(text("UPDATE documents SET status = 'pending', source = :s WHERE id = :id"), {"s": file.filename, "id": doc_id})
            db.execute(text("DELETE FROM document_chunks WHERE document_id = :id"), {"id": doc_id})
            db.commit()
            
            text_content = extract_text(file, content)
            if not text_content:
                raise Exception("No text could be extracted")

            chunks = chunk_text(text_content, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)

            batch_size = 16
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i+batch_size]
                embeddings = get_embeddings_batch(batch_chunks)
                
                for j, chunk_str in enumerate(batch_chunks):
                    chunk_index = i + j
                    db.execute(
                        text("INSERT INTO document_chunks (document_id, chunk_index, content, embedding) VALUES (:did, :idx, :content, :emb)"),
                        {"did": doc_id, "idx": chunk_index, "content": chunk_str, "emb": embeddings[j]}
                    )
            
            db.execute(text("UPDATE documents SET status = 'indexed' WHERE id = :did"), {"did": doc_id})
            db.commit()
            
        except Exception as e:
            db.rollback()
            db.execute(text("UPDATE documents SET status = 'failed' WHERE id = :did"), {"did": doc_id})
            db.commit()
            raise HTTPException(status_code=500, detail=str(e))
            
    return {"message": "Document updated"}

@router.delete("/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db), admin_user: dict = Depends(require_admin)):
    doc = db.execute(text("SELECT id FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    db.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
    db.commit()
    return {"message": "Document deleted"}
