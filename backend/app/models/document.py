from datetime import datetime
from sqlalchemy import Column, String, Text, BigInteger, Integer, Float, JSON, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(Text, nullable=False)
    file_format = Column(String(10), nullable=False)  # PDF | DOCX | PPTX
    file_size_bytes = Column(BigInteger, nullable=False)
    page_count = Column(Integer, nullable=True)
    ai_label = Column(String(100), nullable=True, index=True)
    ai_confidence = Column(Float, nullable=True)  # 0.0–1.0
    review_state = Column(String(20), nullable=False, default="needs_review")
    user_label = Column(String(100), nullable=True)
    extracted_text = Column(JSON, nullable=True)  # [{page, text}]
    last_accessed_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="documents")
    folder = relationship("Folder", back_populates="documents")
    job_files = relationship("JobFile", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_documents_owner", "owner_id"),
        Index("idx_documents_expires", "expires_at"),
        Index("idx_documents_label", "ai_label"),
    )
