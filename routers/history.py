# ROUTER>HISTORY
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database.session import get_db
from database.models import User, ChatHistory
from core.history_and_limits import WEEKLY_LIMIT_FOR_FREE_LAWYERS
from core.auth import get_current_user

router = APIRouter(prefix="/api", tags=["History & Limits"])

# 1. API جلب قائمة السجلات الخاصة بالمستخدم الحالي
@router.get("/history")
def get_user_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    histories = db.query(ChatHistory)\
                  .filter(ChatHistory.user_id == current_user.id)\
                  .order_by(ChatHistory.created_at.desc())\
                  .all()
    
    return [
        {
            "id": h.id,
            "title": h.title,
            "type": h.type,
            "created_at": h.created_at.strftime("%Y-%m-%d %H:%M")
        }
        for h in histories
    ]

# 2. API جلب تفاصيل محادثة أو تحليل فردي (مُعدل)
@router.get("/history/{history_id}")
def get_history_detail(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(ChatHistory)\
              .filter(ChatHistory.id == history_id, ChatHistory.user_id == current_user.id)\
              .first()
              
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="السجل غير موجود أو غير مصرح بالحصول عليه"
        )
        
    return {
        "id": entry.id,
        "title": entry.title,
        "type": entry.type,
        "prompt_text": entry.prompt_text,
        "response_text": entry.response_text,
        "legal_advice": entry.response_text,  # 👈 إضافة هذا الحقل ليتوافق مع استقبال الشات
        "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M")
    }

# 3. API معرفة حالة الاستهلاك الأسبوعي للمحامي والمتدرب
@router.get("/lawyer/usage-status")
def get_lawyer_usage_status(current_user: User = Depends(get_current_user)):
    user_role = getattr(current_user, 'role', None) or (current_user.get('role') if isinstance(current_user, dict) else None)
    
    # 🌟 التعديل: السماح للمحامي والمتدرب فقط
    if user_role not in ["lawyer", "trainee"]:
        raise HTTPException(status_code=403, detail="هذه الخاصية مخصصة للمحامين والمتدربين فقط")
        
    used = getattr(current_user, 'weekly_analysis_count', 0) if not isinstance(current_user, dict) else current_user.get('weekly_analysis_count', 0)
    
    # 🌟 تحديد الحد (مثلاً 4 للمتدرب، وممكن نخليه للمحامي 4 أو غير محدود حسب نظامكم)
    limit = WEEKLY_LIMIT_FOR_FREE_LAWYERS
    remaining = max(0, limit - used)
    
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining
    }
    user_role = getattr(current_user, 'role', None) or (current_user.get('role') if isinstance(current_user, dict) else None)
    
    if user_role != "lawyer":
        raise HTTPException(status_code=400, detail="هذه الخاصية مخصصة للمحامين فقط")
        
    used = getattr(current_user, 'weekly_analysis_count', 0) if not isinstance(current_user, dict) else current_user.get('weekly_analysis_count', 0)
    limit = WEEKLY_LIMIT_FOR_FREE_LAWYERS
    remaining = max(0, limit - used)
    
    return {
        "used": used,
        "limit": limit,
        "remaining": remaining
    }

# 4. API حذف عنصر محدد من السجل
@router.delete("/history/{history_id}")
def delete_history_item(
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    entry = db.query(ChatHistory)\
              .filter(ChatHistory.id == history_id, ChatHistory.user_id == current_user.id)\
              .first()
              
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="السجل غير موجود أو غير مصرح لك بحذفه"
        )
        
    db.delete(entry)
    db.commit()
    
    return {"message": "تم حذف العنصر من السجل بنجاح"}