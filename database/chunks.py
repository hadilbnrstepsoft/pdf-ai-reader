from sqlalchemy import Column, Integer, Text, ForeignKey
from database.db import Base

class PDFChunk(Base):
    __tablename__ = "pdf_chunks"

    id = Column(Integer, primary_key=True)
    pdf_id = Column(Integer)
    content = Column(Text)