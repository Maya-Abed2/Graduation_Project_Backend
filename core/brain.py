import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()


api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None


def ask_legal_brain(user_query: str, retrieved_docs: list = None):
    """
    محرك الاستشارات القانونية الأردنية القائم على Gemini
    """
    if not client:
        print("❌ Error: GEMINI_API_KEY is missing from environment variables.")
        return {
            "answer": "حدث خطأ في النظام: مفتاح الـ API غير معرف في بيئة العمل.",
            "retrieved_articles": []
        }

    print(f"\n================ DEBUG RAG INPUT ================")
    print(f"User Query Received: {user_query}")
    print(f"Docs Received: {len(retrieved_docs) if retrieved_docs else 0}")
    print("=================================================\n")

    # تجهيز السياق القانوني
    context_text = ""
    sources_list = []

    if retrieved_docs:
        for doc in retrieved_docs:
            source = doc.get("metadata", {}).get("law_name", "قانون أردني") if isinstance(doc, dict) else "قانون أردني"
            article = doc.get("metadata", {}).get("article", "") if isinstance(doc, dict) else ""
            text = doc.get("text", str(doc)) if isinstance(doc, dict) else str(doc)

            context_text += f"- المصدر: {source} (مادة {article}): {text}\n"
            sources_list.append({
                "law": source,
                "article": article,
                "text": text
            })
    else:
        context_text = "لا توجد نصوص قانونية مسجلة مسبقاً في قاعدة البيانات لهذه الحالة."

    # برومبت اللي رح ابعته للذكاء
    system_prompt = f"""
أنت مستشار قانوني خبير متخصص في التشريعات والقوانين الأردنية.
مهمتك هي الإجابة على استفسار المستخدم بناءً على النصوص القانونية المرفقة إن وجدت، والخلفية القانونية للتشريعات الأردنية.

[النصوص القانونية المتاحة]:
{context_text}

[سؤال المستخدم]:
{user_query}

[التعليمات]:
1. أجب بلغة عربية سليمة وبأسلوب قانوني واضح ومهني.
2. استشهد بالمواد القانونية الأردنية المناسبة.
3. اجعل الإجابة منظمة في نقاط وواضحة للمستخدم.
"""

    # استدعاء النموذج عبر google-genai
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt,
        )
        answer = response.text
    except Exception as e:
        print(f"⚠️ Primary Model Error (gemini-2.5-flash): {e}")
        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=system_prompt,
            )
            answer = response.text
        except Exception as err:
            print(f"❌ Backup Model Error: {err}")
            answer = "عذراً، حدث خطأ أثناء الاتصال بالمستشار الذكي. يرجى المحاولة بعد قليل."

    return {
        "answer": answer,
        "retrieved_articles": sources_list
    }


def get_legal_advice(query: str, retrieved_docs: list = None):
    """
    Alias function لتتوافق مع استدعاءات routers/chat.py
    """
    res = ask_legal_brain(query, retrieved_docs)
    if isinstance(res, dict):
        return res.get("answer", "لم يتم الحصول على رد.")
    return str(res)