from fastapi import FastAPI
from app.database import supabase

# Initialize the FastAPI app
app = FastAPI(title="IT Service Management API")

@app.get("/")
def read_root():
    return {"message": "Welcome to the IT Service Management Backend!"}


@app.get("/health")
def health_check():
    return {"status": "Database and API are connected and running."}
