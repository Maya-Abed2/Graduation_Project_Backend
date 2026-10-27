from unittest import result

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

# استيراد قاعدة البيانات والنماذج
from database.session import get_db
from database.models import User, ChatHistory

# استيراد دالة الذكاء الاصطناعي/RAG
from core.brain import get_legal_advice

# استيراد دالة التوثيق لجلب المستخدم الحالي
from core.auth import get_current_user

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# نموذج استقبال السؤال من الفرونت إيند
class ChatRequest(BaseModel):
    query: str

@router.post("")
async def chat_query(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_query = request.query
        
        print("================ DEBUG RAG INPUT ================")
        print("User Query Received:", user_query)
        print("Type of Query:", type(user_query))   
        # 1. جلب الاستشارة القانونية من الـ RAG
        result = get_legal_advice(user_query)
        
        print("================ DEBUG RAG OUTPUT ================")
        print("Raw Result from Brain:", result)
        print("==================================================")
        
        # 2. معالجة وتنسيق الإجابة والمصادر
        if isinstance(result, dict):
            legal_advice = result.get("legal_advice") or result.get("answer") or result.get("response") or str(result)
            sources = result.get("sources") or result.get("context") or []
        else:
            legal_advice = str(result)
            sources = []

        # 3. حفظ المحادثة في جدول ChatHistory بقاعدة البيانات
        try:
            # اقتطاع أول 30 حرف من السؤال ليصبح عنواناً للمحادثة
            chat_title = user_query[:30] + "..." if len(user_query) > 30 else user_query
            
            new_history_entry = ChatHistory(
                user_id=current_user.id,
                title=chat_title,
                type="chat",
                prompt_text=user_query,
                response_text=legal_advice
            )
            
            db.add(new_history_entry)
            db.commit()
            db.refresh(new_history_entry)
            
        except Exception as hist_err:
            db.rollback()
            print(f"⚠️ تحذير: لم يتم حفظ المحادثة في السجل: {hist_err}")

        # 4. إرجاع النتيجة للفرونت إيند
        return {
            "legal_advice": legal_advice,
            "sources": sources
        }

    except Exception as e:
        print(f"❌ RAG Execution Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ أثناء جلب الاستشارة القانونية: {str(e)}"
        )