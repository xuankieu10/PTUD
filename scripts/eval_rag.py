import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.prompts import REFUSAL_RESPONSE, NO_CONTEXT_RESPONSE, has_vietnamese
from backend.api import app
from fastapi.testclient import TestClient
from scripts.test_step1 import make_headers, upload_doc, delete_doc

client = TestClient(app)
headers = make_headers(role="admin", subject=1)

REFUSAL_PATTERNS = [
    "không có thông tin",
    "không chứa thông tin",
    "không liên quan",
    "chỉ hỗ trợ",
    "không tìm thấy",
    "không cung cấp thông tin",
    "không đề cập",
    "không nêu"
]

def check_refusal(answer: str) -> bool:
    if answer == REFUSAL_RESPONSE or answer == NO_CONTEXT_RESPONSE:
        return True
    ans_lower = answer.lower()
    return any(p in ans_lower for p in REFUSAL_PATTERNS)

def chat_api_full(message):
    r = client.post("/chat", json={"message": message}, headers=headers)
    if r.status_code != 200:
        return None, r.status_code, []
    data = r.json()
    return data.get("answer", ""), 200, data.get("sources", [])

def run_eval():
    cases_file = os.path.join(os.path.dirname(__file__), "eval_cases.json")
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)
        
    doc_id = upload_doc("__TEST__", "Sinh viên bị cảnh báo học vụ 2 lần liên tiếp thì bị buộc thôi học.", headers)
    time.sleep(2)
    
    try:
        # We need expected_source and expected_keywords for these 3 cases
        cases[0]["expected_source"] = "__TEST__"
        cases[0]["expected_keywords"] = ["2 lần"]
        
        cases[3]["expected_source"] = None
        cases[3]["expected_keywords"] = []
        
        cases[6]["expected_source"] = None
        cases[6]["expected_keywords"] = []
        
        for idx, case in enumerate([cases[0], cases[3], cases[6]]):
            query = case["query"]
            expect_refusal = case.get("expect_refusal", False)
            expected_source = case.get("expected_source")
            expected_keywords = case.get("expected_keywords", [])
            
            print(f"\n{'='*40}\n[{idx+1}] Query: {query}")
            
            # Run 3 times for consistency
            keyword_hits = []
            for i in range(3):
                t0 = time.time()
                ans, status, sources = chat_api_full(query)
                latency = time.time() - t0
                
                is_refusal = check_refusal(ans or "")
                refusal_ok = (is_refusal == expect_refusal)
                vietnamese = has_vietnamese(ans) if ans else False
                
                source_titles = [s.get("title") for s in sources]
                
                if expected_source is None: # e.g. injection, no_context
                    has_source_metric = "N/A"
                    retrieval_hit = "N/A"
                    kw_hit = "N/A"
                else:
                    has_source_metric = expected_source in source_titles or expected_source in (ans or "")
                    retrieval_hit = expected_source in source_titles
                    kw_hit = all(kw.lower() in (ans or "").lower() for kw in expected_keywords)
                
                keyword_hits.append(kw_hit)
                
                print(f"  -> Answer (Run {i+1}): {ans}")
                print(f"  -> Metrics (Run {i+1}):")
                print(f"     - refusal_ok: {refusal_ok} (is_refusal={is_refusal}, expected={expect_refusal})")
                print(f"     - vietnamese: {vietnamese}")
                print(f"     - latency: {latency:.2f}s")
                print(f"     - retrieval_hit: {retrieval_hit}")
                print(f"     - keyword_hit: {kw_hit}")
                print(f"     - has_source: {has_source_metric}")
                    
            consistency = all(h == keyword_hits[0] for h in keyword_hits)
            print(f"     - consistency (3 runs): {consistency}")
            
    finally:
        print(f"\n[INFO] Deleting __TEST__ document_id={doc_id} ...")
        st = delete_doc(doc_id, headers)
        print(f"[INFO] Delete status: {st}")

if __name__ == "__main__":
    run_eval()
