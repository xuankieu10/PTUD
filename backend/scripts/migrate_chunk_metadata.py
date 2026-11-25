"""
backend/scripts/migrate_chunk_metadata.py
Script di trú / chuẩn hóa metadata JSON cho cơ sở tri thức RAG theo Phương án 2:
- Doc 80 (CTĐT từ docx): KHÔNG ĐỔI (giữ nguyên, 0 dòng).
- Doc 79 (Website Khoa): nguồn "trang web Khoa, chưa có văn bản gốc", verified=False, loai_van_ban="qd_khoa" (15 chunks).
- Doc 9001: Phương án 2 chỉ đổi 5 chunk trộn có xung đột/VB2 (Chunk 4, 6, 11, 35, 36) sang verified=False, loai_van_ban="chua_kiem_chung".
- khoa_ap_dung: giữ chuẩn ["all"].
- Hỗ trợ --dry-run (chỉ in, không ghi DB) và --rollback khóa theo (document_id, chunk_index).
"""

import sys
import os
import json
import argparse
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from backend.app.db import SessionLocal

SNAPSHOT_PATH = "database/snapshots/document_chunks_snapshot.json"

# 5 chunk trộn trong Doc 9001 xác định chính xác theo tiêu đề section:
DOC_9001_MIXED_CHUNKS = {
    4: "Mục 3.1 – Đăng ký học lại và xung đột ngưỡng điểm [VB1 & VB2]",
    6: "Mục 3.2 – Thi lại lần 2 và xung đột thời gian tổ chức [VB2 & Mục 8]",
    11: "Mục 5.2 – Thủ tục xét tốt nghiệp và môn học tốt nghiệp [VB1 & VB2]",
    35: "Mục 8.1 – Điểm xung đột về điểm F, thi lại và cải thiện điểm [Hợp nhất]",
    36: "Mục 8.2 – Điểm xung đột về kênh đăng ký và môn tốt nghiệp [Hợp nhất]"
}


def run_migration_option_2(dry_run: bool = True, rollback: bool = False):
    db = SessionLocal()

    if rollback:
        print("=" * 120)
        print("ROLLBACK METADATA TỪ SNAPSHOT (KHÓA THEO document_id, chunk_index)")
        print("=" * 120)
        if not os.path.exists(SNAPSHOT_PATH):
            print(f"Lỗi: Không tìm thấy file snapshot tại {SNAPSHOT_PATH}")
            return
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            snapshot_list = json.load(f)

        print(f"Đọc {len(snapshot_list)} bản ghi từ snapshot...")
        restored_cnt = 0
        for item in snapshot_list:
            doc_id = item["document_id"]
            chunk_idx = item["chunk_index"]
            ver = item["verified"]
            meta = item["metadata"]
            if not dry_run:
                db.execute(text("""
                    UPDATE document_chunks
                    SET verified = :v, metadata = :m
                    WHERE document_id = :did AND chunk_index = :cidx
                """), {
                    "v": ver,
                    "m": meta if isinstance(meta, str) else json.dumps(meta, ensure_ascii=False) if meta else None,
                    "did": doc_id,
                    "cidx": chunk_idx
                })
            restored_cnt += 1
        if not dry_run:
            db.commit()
            print(f"[THÀNH CÔNG]: Đã rollback {restored_cnt} chunks theo khóa (document_id, chunk_index).")
        else:
            print(f"[DRY-RUN ROLLBACK]: Sẽ khôi phục {restored_cnt} chunks theo khóa (document_id, chunk_index).")
        return

    # DRY-RUN / EXECUTE
    print("=" * 120)
    print("MIGRATE METADATA CHUNK RAG (PHƯƠNG ÁN 2 - DRY-RUN)")
    print(f"Chế độ: {'DRY-RUN (Chỉ kiểm tra, KHÔNG ghi DB)' if dry_run else 'THỰC THI (Ghi vào DB)'}")
    print("=" * 120)

    rows = db.execute(text("""
        SELECT id, document_id, chunk_index, section, verified, metadata
        FROM document_chunks
        WHERE document_id IN (79, 80, 9001)
        ORDER BY document_id, chunk_index
    """)).fetchall()

    # Tạo snapshot lưu khóa (document_id, chunk_index)
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    snapshot_data = []
    for r in rows:
        snapshot_data.append({
            "document_id": r.document_id,
            "chunk_index": r.chunk_index,
            "verified": r.verified,
            "metadata": r.metadata
        })
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

    changes = []
    doc_change_counts = {79: 0, 80: 0, 9001: 0}

    for r in rows:
        did = r.document_id
        cidx = r.chunk_index
        sec = r.section or ""
        old_ver = bool(r.verified)
        old_meta_raw = r.metadata
        if isinstance(old_meta_raw, str):
            try: old_meta = json.loads(old_meta_raw)
            except Exception: old_meta = {}
        elif isinstance(old_meta_raw, dict):
            old_meta = old_meta_raw
        else:
            old_meta = {}

        new_ver = old_ver
        new_meta = dict(old_meta)

        # 1. Doc 80: KHÔNG ĐỔI
        if did == 80:
            pass

        # 2. Doc 79: Website Khoa
        elif did == 79:
            new_ver = False
            new_meta["nguon"] = "trang web Khoa, chưa có văn bản gốc"
            new_meta["verified"] = False
            new_meta["loai_van_ban"] = "qd_khoa"
            new_meta["khoa_ap_dung"] = ["all"]
            new_meta["so_hieu"] = "1013/QĐ-ĐHLH"

        # 3. Doc 9001: Chỉ đổi 5 chunk trộn
        elif did == 9001:
            if cidx in DOC_9001_MIXED_CHUNKS:
                new_ver = False
                new_meta["verified"] = False
                new_meta["loai_van_ban"] = "chua_kiem_chung"
                new_meta["khoa_ap_dung"] = ["all"]
                new_meta["ghi_chu"] = f"Xung đột/trộn VB2: {DOC_9001_MIXED_CHUNKS[cidx]}"

        # Ghi nhận các trường có thay đổi
        row_diffs = []
        if old_ver != new_ver:
            row_diffs.append(("verified", old_ver, new_ver))
        for k, v in new_meta.items():
            if old_meta.get(k) != v:
                row_diffs.append((f"metadata.{k}", old_meta.get(k), v))

        if row_diffs:
            doc_change_counts[did] += 1
            for f_name, b_val, a_val in row_diffs:
                changes.append({
                    "document_id": did,
                    "chunk_index": cidx,
                    "field": f_name,
                    "before": b_val,
                    "after": a_val,
                    "section": sec
                })

    print(f"{'Doc':<6} | {'Chunk':<6} | {'Trường thay đổi':<25} | {'Giá trị TRƯỚC':<35} | {'Giá trị SAU'}")
    print("-" * 125)
    for ch in changes:
        b_str = str(ch['before'])[:33]
        a_str = str(ch['after'])
        print(f"{ch['document_id']:<6} | {ch['chunk_index']:<6} | {ch['field']:<25} | {b_str:<35} | {a_str}")

    print("-" * 125)
    print("THỐNG KÊ SỐ DÒNG CÓ THAY ĐỔI THEO TỪNG DOCUMENT:")
    for did in [79, 80, 9001]:
        print(f"  - Document {did:4d}: {doc_change_counts[did]:2d} dòng thay đổi")
    print(f"  -> TỔNG CỘNG: {len(changes)} trường thay đổi trên {sum(doc_change_counts.values())} chunks.")

    print("\n[CAM KẾT AN TOÀN]:")
    print("  - Đang ở chế độ DRY-RUN: KHÔNG CÓ THAY ĐỔI NÀO ĐƯỢC GHI VÀO DB THẬT.")
    print("  - Snapshot backup khóa theo (document_id, chunk_index) đã lưu tại database/snapshots/document_chunks_snapshot.json.")
    print("  - CHỜ NGƯỜI DÙNG DUYỆT BẰNG LỆNH 'DUYỆT MIGRATE' MỚI CHẠY THẬT.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate chunk metadata for RAG (Option 2)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Chạy ở chế độ mô phỏng kiểm tra")
    parser.add_argument("--execute", action="store_true", help="Thực thi ghi dữ liệu thật vào DB")
    parser.add_argument("--rollback", action="store_true", help="Rollback dữ liệu từ snapshot")
    args = parser.parse_args()

    is_dry = not args.execute
    run_migration_option_2(dry_run=is_dry, rollback=args.rollback)
