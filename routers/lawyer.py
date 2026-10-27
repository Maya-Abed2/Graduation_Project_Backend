import io
import pypdf
from typing import Optional
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from database.session import get_db
from database.models import User, ChatHistory
from core.brain import get_legal_advice
from core.auth import get_current_user

router = APIRouter(prefix="/api/lawyer", tags=["Lawyer Analysis"])

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """استخراج النصوص العربية من ملف الـ PDF المرفوع"""
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        extracted_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
        return extracted_text.strip()
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return ""

# ---------------------------------------------------------
# 1. Endpoint حالة الاستهلاك الأسبوعي (حل الخطأ الظاهر بالفرونت)
# ---------------------------------------------------------
@router.get("/usage-status")
def get_lawyer_usage_status(
    current_user: User = Depends(get_current_user)
):
    # السماح للمحامي والمتدرب فقط
    if current_user.role not in ["lawyer", "trainee"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه الخاصية مخصصة للمحامين والمتدربين فقط"
        )

    # تحديد الحد الأسبوعي (4 للمتدرب، 0/غير محدود للمحامي)
    limit = 4 if current_user.role == "trainee" else 0
    used = current_user.weekly_analysis_count or 0
    remaining = max(0, limit - used) if limit > 0 else "غير محدود"

    return {
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "role": current_user.role
    }

# ---------------------------------------------------------
# 2. Endpoint تحليل القضايا
# ---------------------------------------------------------
@router.post("/analyze")
async def analyze_case(
    case_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 🌟 1. التحقق من الصلاحيات (محامي أو متدرب فقط)
    if current_user.role not in ["lawyer", "trainee"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="عذراً، تحليل القضايا المتقدم مخصص للمحامين والمتدربين فقط."
        )

    # 🌟 2. التحقق من حد الاستهلاك للمتدربين
    if current_user.role == "trainee" and (current_user.weekly_analysis_count or 0) >= 4:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="لقد استنفدت الحد الأسبوعي المتاح لك (4 تحليلات أسبوعياً)."
        )

    try:
        raw_case_content = ""

        # استخراج النص من ملف الـ PDF إن وجد
        if file and file.filename.endswith(".pdf"):
            file_bytes = await file.read()
            pdf_text = extract_text_from_pdf(file_bytes)
            if pdf_text:
                raw_case_content += pdf_text

        # إضافة النص المكتوب يدوياً إن وجد
        if case_text and case_text.strip():
            raw_case_content += "\n" + case_text.strip()

        # التأكد من وجود نص حقيقي للتحليل
        if not raw_case_content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="تعذر استخراج نص من الملف المرفق أو النص المدخل. يرجى التأكد من محتوى الملف."
            )

        # إرسال الوقائع القانونية للـ RAG / Gemini
        result = get_legal_advice(raw_case_content.strip())

        if isinstance(result, dict):
            report = result.get("legal_advice") or result.get("answer") or str(result)
        else:
            report = str(result)

        history_id = None
        # حفظ التحليل بداخل قاعدة البيانات (ChatHistory)
        try:
            if file and file.filename:
                title_summary = f"تحليل: {file.filename}"
            else:
                title_summary = f"تحليل: {raw_case_content.strip()[:20]}..."

            new_history_entry = ChatHistory(
                user_id=current_user.id,
                title=title_summary,
                type="chat",
                prompt_text=raw_case_content.strip(),
                response_text=report
            )

            # 🌟 زيادة عداد التحليلات للمتدرب
            if current_user.role == "trainee":
                current_user.weekly_analysis_count = (current_user.weekly_analysis_count or 0) + 1

            db.add(new_history_entry)
            db.commit()
            db.refresh(new_history_entry)
            history_id = new_history_entry.id

        except Exception as hist_err:
            db.rollback()
            print(f"⚠️ تحذير: لم يتم حفظ التحليل في السجل: {hist_err}")

        return {
            "id": history_id,
            "analysis_report": report
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ Lawyer Analysis Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ أثناء تحليل القضية: {str(e)}"
        )