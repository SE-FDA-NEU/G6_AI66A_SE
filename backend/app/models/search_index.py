"""Portable passage/term index: MySQL in production, SQLite in isolated tests."""
from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.database import Base


class SearchDocument(Base):
    __tablename__ = 'search_documents'

    document_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    doc_name = Column(String(255), nullable=False)
    revision = Column(String(64), nullable=False)
    source_sha256 = Column(String(64), nullable=False)
    reader_version = Column(String(64), nullable=False)
    document = relationship('Document', back_populates='search_index')
    passages = relationship('SearchPassage', back_populates='snapshot', cascade='all, delete-orphan')


class SearchPassage(Base):
    __tablename__ = 'search_passages'

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey('search_documents.document_id', ondelete='CASCADE'), nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    page = Column(Integer, nullable=False)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)
    embedding_model = Column(String(128), nullable=True)
    snapshot = relationship('SearchDocument', back_populates='passages')
    terms = relationship('SearchTerm', back_populates='passage', cascade='all, delete-orphan')
    __table_args__ = (
        Index('ix_search_owner_document_page', 'owner_id', 'document_id', 'page'),
        UniqueConstraint('document_id', 'page', 'start', 'end', name='uq_search_passage_span'),
    )


class SearchTerm(Base):
    __tablename__ = 'search_terms'

    passage_id = Column(Integer, ForeignKey('search_passages.id', ondelete='CASCADE'), primary_key=True)
    term = Column(String(64), primary_key=True)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    frequency = Column(Integer, nullable=False)
    passage = relationship('SearchPassage', back_populates='terms')
    __table_args__ = (Index('ix_search_owner_term', 'owner_id', 'term'),)
