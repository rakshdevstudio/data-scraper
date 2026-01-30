from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    BackgroundTasks,
    WebSocket,
    UploadFile,
    File,
    Form,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import models, database, scraper_engine, config, state
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
def get_metrics(response: Response, db: Session = Depends(get_db)):
    # Prevent caching
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

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


@app.get("/results/stats")
def get_results_stats():
    """Get scraping results statistics including Google Sheets sync status"""
    from .scraper_engine import scraper_instance

    if scraper_instance.data_saver:
        stats = scraper_instance.data_saver.get_stats()
        stats["status"] = "active"
        return stats

    return {
        "status": "not_started",
        "total_saved": 0,
        "buffer_size": 0,
        "failed_count": 0,
        "google_sheets_connected": False,
    }


@app.get("/keywords")
def get_keywords(
    response: Response, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    # Prevent caching
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    keywords = db.query(models.Keyword).offset(skip).limit(limit).all()
    return keywords


@app.post("/keywords/upload")
async def upload_keywords(
    file: UploadFile = File(...),
    mode: str = Form("add"),  # Receive from form data
    db: Session = Depends(get_db),
):
    """
    Upload keywords from Excel file with different modes:
    - add: Only add new keywords (default)
    - replace: Delete all existing keywords and insert from file
    - sync: Add new keywords and reset existing ones to pending
    """
    import hashlib

    # Validate mode
    if mode not in ["add", "replace", "sync"]:
        raise HTTPException(
            status_code=400, detail="Invalid mode. Use 'add', 'replace', or 'sync'"
        )

    # Ensure storage dir exists
    os.makedirs("storage", exist_ok=True)

    file_location = f"storage/{file.filename}"

    # Save file and calculate hash
    file_hash = hashlib.md5()
    file_size = 0

    with open(file_location, "wb+") as file_object:
        while chunk := file.file.read(8192):
            file_hash.update(chunk)
            file_size += len(chunk)
            file_object.write(chunk)

    file_hash_hex = file_hash.hexdigest()

    # Process file
    try:
        df = pd.read_excel(file_location)
        # Normalize columns
        df.columns = [c.lower() for c in df.columns]

        if "keyword" not in df.columns:
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Must have 'keyword' column.",
            )

        # Deduplicate inside the file first
        new_keywords = df["keyword"].dropna().unique().astype(str).tolist()
        total_in_file = len(new_keywords)

        new_count = 0

        if mode == "replace":
            # Delete all existing keywords
            db.query(models.Keyword).delete()
            db.commit()

            # Insert all keywords from file
            keywords_to_insert = [
                {"text": k, "status": "pending"} for k in new_keywords
            ]
            db.bulk_insert_mappings(models.Keyword, keywords_to_insert)
            db.commit()
            new_count = len(keywords_to_insert)
            message = f"Replaced all keywords. Inserted {new_count} keywords from file."

        elif mode == "sync":
            # Get all existing keywords
            existing_keywords = {k.text: k for k in db.query(models.Keyword).all()}

            # Add new keywords and reset existing ones to pending
            keywords_to_insert = []
            for k in new_keywords:
                if k in existing_keywords:
                    # Reset existing keyword to pending
                    existing_keywords[k].status = models.KeywordStatus.PENDING
                else:
                    # Add new keyword
                    keywords_to_insert.append({"text": k, "status": "pending"})
                    new_count += 1

            if keywords_to_insert:
                db.bulk_insert_mappings(models.Keyword, keywords_to_insert)

            db.commit()
            message = f"Synced keywords. Added {new_count} new, reset {len(new_keywords) - new_count} existing to pending."

        else:  # mode == "add"
            # Original behavior: only add new keywords
            chunk_size = 900
            new_to_insert = []

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
                db.bulk_insert_mappings(models.Keyword, new_to_insert)
                db.commit()

            new_count = len(new_to_insert)
            message = f"Added {new_count} new keywords (skipped {total_in_file - new_count} duplicates)."

        # Record upload history
        upload_record = models.UploadHistory(
            filename=file.filename,
            file_hash=file_hash_hex,
            file_size_bytes=file_size,
            keywords_count=total_in_file,
            new_keywords=new_count,
            mode=mode,
        )
        db.add(upload_record)
        db.commit()

        return {
            "message": message,
            "mode": mode,
            "total_in_file": total_in_file,
            "new_keywords": new_count,
            "file_hash": file_hash_hex,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/keywords/upload-history")
def get_upload_history(limit: int = 10, db: Session = Depends(get_db)):
    """Get upload history with metadata"""
    history = (
        db.query(models.UploadHistory)
        .order_by(models.UploadHistory.upload_time.desc())
        .limit(limit)
        .all()
    )
    return history


@app.post("/keywords/reset-failed")
def reset_failed_keywords(db: Session = Depends(get_db)):
    """Reset all failed keywords back to pending status"""
    try:
        failed_keywords = (
            db.query(models.Keyword)
            .filter(models.Keyword.status == models.KeywordStatus.FAILED)
            .all()
        )

        count = len(failed_keywords)

        for keyword in failed_keywords:
            keyword.status = models.KeywordStatus.PENDING

        db.commit()

        return {"message": f"Reset {count} failed keywords to pending", "count": count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/keywords/reset-all")
def reset_all_keywords(db: Session = Depends(get_db)):
    """Reset all non-done keywords (failed, processing) back to pending status"""
    try:
        keywords_to_reset = (
            db.query(models.Keyword)
            .filter(
                models.Keyword.status.in_(
                    [models.KeywordStatus.FAILED, models.KeywordStatus.PROCESSING]
                )
            )
            .all()
        )

        count = len(keywords_to_reset)

        for keyword in keywords_to_reset:
            keyword.status = models.KeywordStatus.PENDING

        db.commit()

        return {"message": f"Reset {count} keywords to pending", "count": count}
    except Exception as e:
        db.rollback()
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
