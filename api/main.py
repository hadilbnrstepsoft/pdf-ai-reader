from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="PDF AI SaaS")

app.include_router(router)


@app.get("/")
def home():
    return {"status": "PDF AI Backend is running"}