from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    
    # الصلاحيات المعتمدة: 'lawyer' أو 'client'
    role = Column(String, default="client", nullable=False)

    # 📊 نظام الاشتراكات والحدود الأسبوعية للمحامين المتدربين
    weekly_analysis_count = Column(Integer, default=0, nullable=False)
    last_reset_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # علاقة السجلات التابعة للمستخدم
    histories = relationship("ChatHistory", back_populates="owner", cascade="all, delete-orphan")


class ChatHistory(Base):
    __tablename__ = "chat_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # نوع السجل: 'chat' (استفسار عام) أو 'analysis' (تحليل قضية للمحامي)
    type = Column(String, nullable=False, default="chat") 
    
    # عنوان السجل (أو ملخص بسيط للاستعراض في القائمة الجانبية)
    title = Column(String, nullable=False)
    
    # المدخلات (سؤال المستخدم أو نص القضية)
    prompt_text = Column(Text, nullable=False)
    
    # مخرجات الذكاء الاصطناعي (الرد أو التقرير القانوني)
    response_text = Column(Text, nullable=False)
    
    # تاريخ وتوقيت العملية
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # رابط العودة للمستخدم
    owner = relationship("User", back_populates="histories")