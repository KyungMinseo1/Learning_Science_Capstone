from fastapi import FastAPI
from backend.app.api import papers, auth, user

app = FastAPI(title="Paper Knowledge Base")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(papers.router, prefix="/api", tags=["papers"])

@app.get("/")
async def root():
    return {"message": "Welcome to Paper Knowledge Base API"}
