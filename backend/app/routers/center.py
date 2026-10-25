"""
Router cung cấp các API liên quan đến Trung tâm Ngoại ngữ - Tin học (NNTH):
- POST /admin/sync-nnth: Chạy đồng bộ thủ công từ các API công khai của trung tâm.
- GET /api/center/schedules: Lấy danh sách lịch khai giảng sắp tới (lọc theo Ngoại ngữ / Tin học).
- GET /api/center/exams: Lấy danh sách lịch thi sắp tới (lọc theo Ngoại ngữ / Tin học, chính thức / dự kiến).
- GET /api/center/summary: Thống kê tổng quan lịch học và lịch thi.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import get_db
from backend.services.nnth_sync import (
    sync_nnth_data,
    get_upcoming_schedules,
    get_upcoming_exams,
    get_last_sync_info
)

logger = logging.getLogger("CenterRouter")
router = APIRouter(tags=["Trung tâm Ngoại ngữ - Tin học"])


@router.post("/admin/sync-nnth", summary="Đồng bộ thủ công lịch học và lịch thi từ NNTH")
def trigger_sync_nnth(db: Session = Depends(get_db)):
    """
    Endpoint kích hoạt đồng bộ thủ công lịch học và lịch thi từ các API công khai của NNTH.
    Chạy an toàn, không nhân đôi dữ liệu.
    """
    try:
        result = sync_nnth_data(db)
        if result["status"] == "ERROR":
            raise HTTPException(
                status_code=502,
                detail=f"Đồng bộ thất bại từ cổng API NNTH: {result.get('error')}"
            )
        return {
            "success": True,
            "message": "Đồng bộ dữ liệu Trung tâm Ngoại ngữ - Tin học thành công.",
            "data": result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Lỗi khi chạy sync-nnth thủ công: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi đồng bộ: {str(e)}")


@router.get("/api/center/schedules", summary="Lấy lịch khai giảng các lớp học NNTH sắp tới")
def list_center_schedules(
    loai: Optional[str] = Query(None, description="Lọc theo loại: 'Ngoại ngữ' hoặc 'Tin học'"),
    from_today: bool = Query(True, description="Chỉ lấy các lớp có ngày khai giảng từ hôm nay trở đi"),
    db: Session = Depends(get_db)
):
    """
    Truy vấn danh sách lịch khai giảng sắp tới từ cơ sở dữ liệu nội bộ.
    Không gọi trực tiếp sang API trường tại mỗi request của sinh viên.
    """
    try:
        schedules = get_upcoming_schedules(db, loai=loai, from_today=from_today)
        last_sync = get_last_sync_info(db)
        return {
            "success": True,
            "total": len(schedules),
            "schedules": schedules,
            "last_sync": last_sync
        }
    except Exception as e:
        logger.error("Lỗi truy vấn lịch khai giảng: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Không thể truy vấn lịch khai giảng.")


@router.get("/api/center/exams", summary="Lấy lịch thi chứng chỉ NNTH sắp tới")
def list_center_exams(
    loai: Optional[str] = Query(None, description="Lọc theo loại: 'Ngoại ngữ' hoặc 'Tin học'"),
    is_du_kien: Optional[bool] = Query(None, description="Lọc theo lịch dự kiến (true) hoặc chính thức (false)"),
    from_today: bool = Query(True, description="Chỉ lấy các kỳ thi có ngày thi từ hôm nay trở đi"),
    db: Session = Depends(get_db)
):
    """
    Truy vấn danh sách lịch thi sắp tới từ cơ sở dữ liệu nội bộ.
    """
    try:
        exams = get_upcoming_exams(db, loai=loai, is_du_kien=is_du_kien, from_today=from_today)
        last_sync = get_last_sync_info(db)
        return {
            "success": True,
            "total": len(exams),
            "exams": exams,
            "last_sync": last_sync
        }
    except Exception as e:
        logger.error("Lỗi truy vấn lịch thi: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Không thể truy vấn lịch thi.")


@router.get("/api/center/summary", summary="Tổng quan lịch học và lịch thi NNTH")
def get_center_summary(db: Session = Depends(get_db)):
    """
    Cung cấp tóm tắt nhanh số lượng lớp học và kỳ thi sắp tới kèm trạng thái đồng bộ.
    """
    schedules = get_upcoming_schedules(db, from_today=True)
    exams = get_upcoming_exams(db, from_today=True)
    last_sync = get_last_sync_info(db)
    return {
        "success": True,
        "upcoming_schedules_count": len(schedules),
        "upcoming_exams_count": len(exams),
        "last_sync": last_sync
    }
