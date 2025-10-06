from fastapi import FastAPI
from api import routes_resume

app = FastAPI(
    title="AI Job Application Filler",
    version="1.0.0",
    description="Backend API for AI-powered job application autofill"
)

# Routers
# app.include_router(routes_health.router, prefix="/api/health", tags=["Health"])
app.include_router(routes_resume.router, prefix="/api/resume", tags=["Resume"])

@app.get("/")
def root():
    return {"message": "AI Job Application Filler Backend is running!"}
