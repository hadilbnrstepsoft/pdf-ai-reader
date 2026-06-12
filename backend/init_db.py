from database.db import engine, Base
from database.models import PDFRecord

Base.metadata.create_all(bind=engine)

print("DB READY")