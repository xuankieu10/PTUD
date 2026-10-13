from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.db import get_db
from backend.app.security import verify_password, create_access_token
from backend.app.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(text("SELECT id, username, password_hash, role FROM users WHERE username = :usr"), {"usr": request.username}).fetchone()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role)
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "user_id": user.id}
from fastapi.security import OAuth2PasswordRequestForm

@router.post("/token")
def login_for_access_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.execute(text("SELECT id, username, password_hash, role FROM users WHERE username = :usr"), {"usr": request.username}).fetchone()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(subject=user.id, role=user.role)
    return {"access_token": access_token, "token_type": "bearer"}
@router.get("/me")
def read_users_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    res = {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user["role"],
    }
    stu = db.execute(
        text("SELECT student_code, full_name, major, cohort FROM students WHERE user_id = :uid"),
        {"uid": current_user["id"]}
    ).fetchone()
    if stu:
        res["student_code"] = stu.student_code
        res["full_name"] = stu.full_name
        res["major"] = stu.major
        res["cohort"] = stu.cohort
    else:
        if current_user["role"] == "admin":
            res["student_code"] = "ADMIN"
            res["full_name"] = "Quản trị viên"
            res["major"] = "Phòng Đào tạo"
        else:
            res["student_code"] = current_user["username"]
            res["full_name"] = current_user["username"]
            res["major"] = "Chưa cập nhật"
    return res
