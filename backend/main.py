from fastapi import FastAPI
import logging
from backend.app.api import papers, auth, user

# Configure basic logging for the application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s"
)

app = FastAPI(title="Paper Knowledge Base")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(user.router, prefix="/api/user", tags=["user"])
app.include_router(papers.router, prefix="/api", tags=["papers"])


@app.get("/")
async def root():
    return {"message": "Welcome to Paper Knowledge Base API"}
