import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import User
from core.auth import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])


UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# ---------------------------------------------------------
# 1. Endpoint إنشاء حساب جديد
# ---------------------------------------------------------
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("client"),
    weekly_limit: Optional[int] = Form(None),
    used_analyses: Optional[int] = Form(None),
    lawyer_card: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    try:
        # التحقق من وجود المستخدم مسبقاً
        existing_user = db.query(User).filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="اسم المستخدم أو البريد الإلكتروني مسجل بالفعل"
            )
        
        # رفع بطاقة النقابة للمحامي
        card_path = None
        if role == "lawyer" and lawyer_card and lawyer_card.filename:
            card_path = os.path.join(UPLOAD_DIR, f"{username}_{lawyer_card.filename}")
            content = await lawyer_card.read()
            with open(card_path, "wb") as f:
                f.write(content)

        # تشفير كلمة المرور
        hashed_pwd = get_password_hash(password)
        
        # 🌟 تحديد حد التحليلات الأسبوعي للمتدرب (افتراضياً 4)
        init_weekly_limit = 4 if role == "trainee" else (weekly_limit or 0)
        init_used_analyses = 0 if role == "trainee" else (used_analyses or 0)

        # إنشاء المستخدم الجديد
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_pwd,
            role=role,
            weekly_limit=init_weekly_limit,
            used_analyses=init_used_analyses
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return {"message": "تم إنشاء الحساب بنجاح", "role": new_user.role}

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"❌ Server Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"حدث خطأ في السيرفر: {str(e)}"
        )

# ---------------------------------------------------------
# 2. Endpoint تسجيل الدخول
# ---------------------------------------------------------
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # البحث عن المستخدم بواسطة اسم المستخدم
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # التحقق من وجود المستخدم وصحة كلمة المرور
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة المرور غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # إنشاء Access Token ينطوي على الـ role
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    #  إرجاع بيانات الـ Role والحد الاستهلاكي مباشرة مع الـ Response
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "weekly_limit": getattr(user, 'weekly_limit', 4 if user.role == 'trainee' else 0),
        "used_analyses": getattr(user, 'used_analyses', 0)
    }
