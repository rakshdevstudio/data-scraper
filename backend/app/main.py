from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, database, scraper_engine, config, state
import shutil
import os
import pandas as pd
from datetime import datetime

# Init DB
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Maps Scraper Dashboard")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = scraper_instance = scraper_engine.scraper_instance


# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "Maps Scraper API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok", "db": "connected" if database.SessionLocal() else "error"}


@app.get("/status")
def get_status():
    return state.state_manager.get_state()


@app.post("/control/{action}")
def control_scraper(action: str):
    if action == "start":
        engine.start()
    elif action == "stop":
        engine.stop()
    elif action == "pause":
        engine.pause()
    elif action == "resume":
        engine.resume()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    return {"message": f"Scraper {action} command sent"}


@app.get("/config")
def get_config():
    return config.load_config()


@app.post("/config")
def update_config_endpoint(settings: dict):
    for k, v in settings.items():
        config.update_config(k, v)
    return {"message": "Config updated", "config": config.load_config()}


@app.get("/metrics")
def get_metrics(db: Session = Depends(get_db)):
    total = db.query(models.Keyword).count()
    done = db.query(models.Keyword).filter(models.Keyword.status == "done").count()
    pending = (
        db.query(models.Keyword).filter(models.Keyword.status == "pending").count()
    )
    processing = (
        db.query(models.Keyword).filter(models.Keyword.status == "processing").count()
    )
    failed = db.query(models.Keyword).filter(models.Keyword.status == "failed").count()

    return {
        "total": total,
        "done": done,
        "pending": pending,
        "processing": processing,
        "failed": failed,
    }


@app.get("/keywords")
def get_keywords(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    keywords = db.query(models.Keyword).offset(skip).limit(limit).all()
    return keywords


@app.post("/keywords/upload")
async def upload_keywords(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Ensure storage dir exists
    os.makedirs("storage", exist_ok=True)

    file_location = f"storage/{file.filename}"
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)

    # Process file
    try:
        df = pd.read_excel(file_location)
        # Normalize columns
        df.columns = [c.lower() for c in df.columns]

        if "keyword" not in df.columns:
            return {"error": "Invalid file format. Must have 'keyword' column."}

        # Deduplicate inside the file first
        new_keywords = df["keyword"].dropna().unique().astype(str).tolist()

        # Batch check against DB to avoid 116k queries
        # We'll chunks of 1000 to avoid SQL variable limits
        chunk_size = 900
        new_to_insert = []

        existing_set = set()

        # Optimization: If DB is huge, fetching all might be bad. But checking 1-by-1 is worse.
        # Let's check in batches of input.

        for i in range(0, len(new_keywords), chunk_size):
            chunk = new_keywords[i : i + chunk_size]
            existing_objs = (
                db.query(models.Keyword.text)
                .filter(models.Keyword.text.in_(chunk))
                .all()
            )
            existing_in_chunk = {r[0] for r in existing_objs}

            for k in chunk:
                if k not in existing_in_chunk:
                    new_to_insert.append({"text": k, "status": "pending"})

        if new_to_insert:
            # Bulk insert
            try:
                db.bulk_insert_mappings(models.Keyword, new_to_insert)
                db.commit()
            except Exception as e:
                db.rollback()
                # Fallback to slower method if bulk fails (rare)
                print(f"Bulk insert failed: {e}")
                raise e

        return {"message": f"Imported {len(new_to_insert)} new keywords"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = (
        db.query(models.LogEntry)
        .order_by(models.LogEntry.timestamp.desc())
        .limit(limit)
        .all()
    )
    return logs


from .websocket_manager import manager
import asyncio
import json


@app.on_event("startup")
async def startup_event():
    # Start the log broadcaster
    asyncio.create_task(broadcast_logs())


async def broadcast_logs():
    while True:
        try:
            # Non-blocking get from queue
            while not state.state_manager.log_queue.empty():
                log_entry = state.state_manager.log_queue.get_nowait()
                # Broadcast format
                # We send string for simplicity, or json
                msg = f"{log_entry['timestamp']} {log_entry['message']}"
                # Or better: send JSON and let frontend format
                await manager.broadcast(json.dumps(log_entry))

            await asyncio.sleep(0.5)  # Poll queue every 500ms
        except Exception as e:
            print(f"Log broadcast error: {e}")
            await asyncio.sleep(1)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep alive
            data = await websocket.receive_text()
    except:
        manager.disconnect(websocket)
