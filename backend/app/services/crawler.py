import hashlib
import json
import os
import requests
import sys
from bs4 import BeautifulSoup
import pdfplumber
import docx
from urllib.parse import urljoin
import time
from backend.app.services.chunking import chunk_text
from backend.app.db import engine
from sqlalchemy import text
from backend.app.services.embedding import get_embedding

def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def is_garbage_text(text: str) -> tuple[bool, str]:
    if not text:
        return True, "Empty text"
    
    # Calculate (cid: ratio
    cid_count = text.count("(cid:")
    # each (cid: is usually accompanied by 1-3 digits and a closing bracket, say 8 chars
    # We'll just count occurrences * 6 to be safe, or just occurrences / len(text)
    cid_ratio = (cid_count * 5) / len(text)
    
    if cid_ratio > 0.01:
        return True, f"Too many (cid: patterns (ratio: {cid_ratio:.3f})"
        
    # Check Vietnamese
    import re
    vn_chars = len(re.findall(r'[àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳýỵỷỹÀÁÃẠẢĂẮẰẲẴẶÂẤẦẨẪẬÈÉẸẺẼÊỀẾỂỄỆĐÌÍĨỈỊÒÓÕỌỎÔỐỒỔỖỘƠỚỜỞỠỢÙÚŨỤỦƯỨỪỬỮỰỲÝỴỶỸ]', text))
    if vn_chars < len(text) * 0.01 and len(text) > 100: # less than 1% Vietnamese characters
        return True, "Almost no valid Vietnamese characters"
        
    # Check meaningful words ratio
    words = text.lower().split()
    if len(words) > 50:
        common_words = set('là của và có trong các một cho với không những được người về từ đó đây cũng như sẽ lại tại đã ra hay đến để nhưng còn này lúc nào rồi phải đang do thế nên sinh viên học kỳ tín chỉ điều kiện quy chế nhà trường đại đào tạo khoa ngành năm điểm thi đánh giá kết quả thông báo giáo dục môn lịch tuần chương trình quản lý hướng dẫn thực hiện công tác khen thưởng kỷ luật cấp bằng tốt nghiệp chính xét công nhận miễn giảm phí bảo hiểm y tế hoạt động ngoại khóa phong trào đoàn hội nghiên cứu khởi nghiệp'.split())
        recognized = sum(1 for w in words if w in common_words or w.isalpha())
        recognized = sum(1 for w in words if w.strip(".,;:!?()[]{}\"'-") in common_words)
        if recognized / len(words) < 0.4:
            return True, f"Too few meaningful words (ratio: {recognized / len(words):.3f})"
            
    return False, "Valid"

def extract_text_from_pdf(filepath: str) -> tuple[str, int]:
    text = ""
    num_pages = 0
    try:
        with pdfplumber.open(filepath) as pdf:
            num_pages = len(pdf.pages)
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF {filepath}: {e}")
    return text, num_pages

def extract_text_from_docx(filepath: str) -> str:
    text = ""
    try:
        doc = docx.Document(filepath)
        text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"Error reading DOCX {filepath}: {e}")
    return text

def crawl_page(url: str):
    print(f"Crawling {url}...")
    
    domain = url.split("/")[2]
    if domain == "graduate.lhu.edu.vn":
        print("Áp dụng Crawl-delay 60s cho graduate.lhu.edu.vn...")
        time.sleep(60)
        
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return

    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Xóa menu, header, footer
    for tag in soup.find_all(['header', 'footer', 'nav']):
        tag.decompose()
    # Tìm vùng chứa thông tin cho...
    for tag in soup.find_all('div', class_='thongtincho'):
        tag.decompose()
        
    main_text = ""
    content_div = soup.find('div', class_='noidung') or soup.find('div', class_='content')
    if content_div:
        main_text = content_div.get_text(separator='\n', strip=True)
    else:
        main_text = soup.get_text(separator='\n', strip=True)
        
    title = soup.title.string.strip() if soup.title else url
    print(f"Trang chính: {title} - {len(main_text)} ký tự")
    
    # 2. Attachments
    downloads = {}
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.lower().endswith('.pdf') or href.lower().endswith('.docx'):
            abs_url = urljoin(url, href)
            if abs_url not in downloads:
                downloads[abs_url] = link.text.strip() or "Tài liệu đính kèm"
            
    print(f"Tìm thấy {len(downloads)} file đính kèm: {list(downloads.keys())}")
    
    results = []
    
    # Process main page
    if main_text:
        ch = get_content_hash(main_text)
        chunks = chunk_text(main_text)
        results.append({
            'url': url,
            'title': title,
            'hash': ch,
            'chunks': chunks
        })
        
    # Process attachments
    os.makedirs('tmp_downloads', exist_ok=True)
    for attach_url, attach_title in downloads.items():
        time.sleep(1) # rate limit
        ext = attach_url.split('.')[-1].lower()
        filepath = f"tmp_downloads/temp_{hashlib.md5(attach_url.encode()).hexdigest()}.{ext}"
        try:
            r = requests.get(attach_url, headers=headers)
            with open(filepath, 'wb') as f:
                f.write(r.content)
                
            extracted_text = ""
            if ext == 'pdf':
                extracted_text, num_pages = extract_text_from_pdf(filepath)
                print(f"File PDF {attach_url}: {num_pages} trang, {len(extracted_text)} ký tự")
                if not extracted_text.strip():
                    print("=> ĐÂY LÀ PDF SCAN (KHÔNG CÓ TEXT), chưa tự OCR.")
                else:
                    print("300 ký tự đầu:")
                    print(extracted_text[:300])
                    # In 1 trang giữa (ước lượng bằng cách chia chuỗi)
                    mid = len(extracted_text) // 2
                    print("\n300 ký tự giữa:")
                    print(extracted_text[mid:mid+300])
            elif ext == 'docx':
                extracted_text = extract_text_from_docx(filepath)
                
            if extracted_text:
                is_garbage, reason = is_garbage_text(extracted_text)
                if is_garbage:
                    print(f"BỎ FILE {attach_url}: {reason}")
                    continue
                    
                ch = get_content_hash(extracted_text)
                chunks = chunk_text(extracted_text)
                results.append({
                    'url': attach_url,
                    'title': f"{title} - {attach_title}",
                    'hash': ch,
                    'chunks': chunks
                })
        except Exception as e:
            print(f"Error processing {attach_url}: {e}")
            
    # Lưu vào DB
    with engine.connect() as c:
        for res in results:
            # Check if exists and hash unchanged
            existing = c.execute(
                text("SELECT id, content_hash FROM documents WHERE source_url = :url"),
                {"url": res['url']}
            ).fetchone()
            
            if existing:
                if existing.content_hash == res['hash']:
                    print(f"Bỏ qua (không đổi hash): {res['url']}")
                    continue
                else:
                    print(f"Cập nhật document (hash thay đổi): {res['url']}")
                    c.execute(text("DELETE FROM document_chunks WHERE document_id = :id"), {"id": existing.id})
                    c.execute(text("DELETE FROM documents WHERE id = :id"), {"id": existing.id})
            
            print(f"Đang lưu {res['url']} vào DB...")
            # Insert document
            doc_id = c.execute(
                text("INSERT INTO documents (title, status, source, uploaded_by, source_url, fetched_at, content_hash) OUTPUT INSERTED.id VALUES (:title, 'indexed', 'crawler', 1, :url, GETDATE(), :hash)"),
                {"title": res['title'], "url": res['url'], "hash": res['hash']}
            ).scalar()
            
            for i, chunk_str in enumerate(res['chunks']):
                emb = get_embedding(chunk_str)
                c.execute(
                    text("INSERT INTO document_chunks (document_id, chunk_index, content, embedding) VALUES (:did, :idx, :content, :emb)"),
                    {"did": doc_id, "idx": i, "content": chunk_str, "emb": emb}
                )
        c.commit()
            
    # In kết quả 3 chunk đầu của trang đầu tiên
    if results:
        first_doc = results[0]
        print(f"\n--- TỔNG KẾT ---")
        print(f"URL: {first_doc['url']}")
        print(f"Tiêu đề: {first_doc['title']}")
        print(f"Hash: {first_doc['hash']}")
        print(f"Số chunk: {len(first_doc['chunks'])}")
        for i, chk in enumerate(first_doc['chunks'][:3]):
            print(f"\n[Chunk {i+1}]")
            print(chk[:300] + ("..." if len(chk)>300 else ""))
            
if __name__ == "__main__":
    crawl_page("https://sinhviendanghoc.lhu.edu.vn/483/Nien-giam.html")
