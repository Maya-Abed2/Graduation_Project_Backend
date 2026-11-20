import os
import re
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def split_text_by_articles(raw_documents: List[Document], law_name: str, category: str) -> List[Document]:
    """
    تقوم هذه الدالة بتجميع نص القانون ثم تقطيعه بناءً على المواد القانونية (المادة 1، المادة 2...)
    مع حفظ البيانات الوصفية (Metadata) لكل مادة لضمان استرجاع دقيق.
    """
   
    full_text = ""
    for doc in raw_documents:
        full_text += f"\n{doc.page_content}"

    
    pattern = r'(المادة\s*\(?\d+\)?[\s\S]*?)(?=(المادة\s*\(?\d+\)?|$))'
    matches = list(re.finditer(pattern, full_text))

    processed_docs = []

    if not matches:
        
        print(f"⚠️ لم يتم التعرف على نمط المواد التقليصي في ({law_name})، سيتم التقسيم بحسب الفقرات.")
        paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > 30]
        for idx, para in enumerate(paragraphs):
            metadata = {
                "law_name": law_name,
                "category": category,
                "article_number": f"فقرة {idx+1}"
            }
            content = f"التشريع: {law_name}\nالتصنيف: {category}\n\n{para}"
            processed_docs.append(Document(page_content=content, metadata=metadata))
    else:
        for idx, match in enumerate(matches):
            article_text = match.group(1).strip()
            
            # استخراج رقم المادة
            art_num_match = re.search(r'المادة\s*\(?(\d+)\)?', article_text)
            art_num = art_num_match.group(1) if art_num_match else str(idx + 1)

            # إضافة رأس سياقي يضم اسم القانون والتصنيف لتغذية الـ Embeddings
            formatted_content = f"التشريع: {law_name}\nالتصنيف: {category}\nرقم المادة: {art_num}\n\n{article_text}"
            
            metadata = {
                "law_name": law_name,
                "category": category,
                "article_number": art_num
            }
            
            processed_docs.append(Document(page_content=formatted_content, metadata=metadata))

    return processed_docs


def run_ingestion(pdf_relative_path: str, db_name: str, law_name: str, category: str):
    full_pdf_path = os.path.join(BASE_DIR, "data", pdf_relative_path)
    persist_directory = os.path.join(BASE_DIR, db_name)
    
    print(f"\n⏳ جاري معالجة الملف: {full_pdf_path}")
    print(f"📌 القانون: {law_name} | التصنيف: {category}")
    
    if not os.path.exists(full_pdf_path):
        print(f"❌ ملف الـ PDF غير موجود في: {full_pdf_path}")
        return

    try:
        loader = PyPDFLoader(full_pdf_path)
        raw_documents = loader.load()
        print(f"📖 تم تحميل الملف بنجاح. عدد الصفحات: {len(raw_documents)}")
    except Exception as e:
        print(f"❌ فشل تحميل الملف: {str(e)}")
        return
    
    # التقطيع المخصص بناءً على المواد القانونية
    docs = split_text_by_articles(raw_documents, law_name=law_name, category=category)
    print(f"📊 تم توليد {len(docs)} مادة قانونية جاهزة للتخزين.")
    
    print("🧠 جاري بناء/تحديث قاعدة البيانات الدلالية...")
    try:
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/LaBSE")
        vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
        vector_db.add_documents(docs)
        print(f"✅ تم حفظ قاعدة البيانات بنجاح في: {persist_directory}")
    except Exception as e:
        print(f"❌ حدث خطأ أثناء البناء: {str(e)}")
        
    print("-" * 60)


if __name__ == "__main__":
    print("🚀 بدء بناء مستودعات البيانات القانونية المباشرة والمعدولة...")
    
    # 1. القوانين الأساسية القائمة
    run_ingestion("law_books/penal/penal_code.pdf", "chroma_penal_db", "قانون العقوبات الأردني", "جزائي")
    run_ingestion("law_books/civil/civil_code.pdf", "chroma_civil_db", "القانون المدني الأردني", "مدني")
    run_ingestion("law_books/procedures/procedures_code.pdf", "chroma_procedures_db", "قانون اصول المحاكمات المدنية", "إجراءات")
    
    # 2. القوانين الجديدة المضافة
    # - الجرائم الإلكترونية (يتبع المجلد الجزائي)
    run_ingestion("law_books/penal/cybercrime_code.pdf", "chroma_penal_db", "قانون الجرائم الإلكترونية", "جزائي")
    
    # - أصول المحاكمات الجزائية (يتبع مجلد الإجراءات)
    run_ingestion("law_books/procedures/penal_procedures_code.pdf", "chroma_procedures_db", "قانون اصول المحاكمات الجزائية", "إجراءات")
    
    # - الأحوال الشخصية
    run_ingestion("law_books/personal_status/personal_status_code.pdf", "chroma_civil_db", "قانون الأحوال الشخصية", "أحوال شخصية")
    
    # - قانون الشركات
    run_ingestion("law_books/companies/companies_code.pdf", "chroma_civil_db", "قانون الشركات الأردني", "تجاري")

    print("\n🎉 انتهى البناء النظيف بنجاح!")
