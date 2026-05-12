# main.py
from fastapi import FastAPI

app = FastAPI(title="MotoEgine", version="0.1.0")

@app.get("/")
def read_root():
    return {"message": "Hello from MotoEgine!"}