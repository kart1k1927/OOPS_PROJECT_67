from fastapi import FastAPI
from app.database.database import supabase
from app.api.routers import auth

# Initialize the FastAPI app
app = FastAPI(title="IT Service Management API")

# Include the auth router
app.include_router(auth.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to the IT Service Management Backend!"}


@app.get("/health")
def health_check():
    return {"status": "Database and API are connected and running."}
