from fastapi import FastAPI
from app.database.database import supabase
from app.api.routers import auth, admin, pages, incidents, technicians
from fastapi.staticfiles import StaticFiles 
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize the FastAPI app
app = FastAPI(title="IT Service Management API")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" /"static"), name="static")

# Include the auth router and the others routesr
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(incidents.router)
app.include_router(technicians.router)
app.include_router(admin.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the IT Service Management Backend!"}


@app.get("/health")
def health_check():
    from app.database.database import supabase

    try:
        supabase.table("categories").select("id", count="exact").limit(1).execute()
    except Exception as exc:
        return {"status": "degraded", "database": str(exc)}
    return {"status": "ok", "database": "connected"}
    