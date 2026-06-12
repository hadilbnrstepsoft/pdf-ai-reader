from sqlalchemy import Column, Integer, Text, String
from database.db import Base

class PDFRecord(Base):
    __tablename__ = "pdf_records"

    id = Column(Integer, primary_key=True)
    filename = Column(String)
    text = Column(Text)
    json_data = Column(Text)