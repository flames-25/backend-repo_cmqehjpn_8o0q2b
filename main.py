import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Todo

app = FastAPI(title="Todo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TodoCreate(BaseModel):
    title: str

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None


def serialize_todo(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title", ""),
        "completed": bool(doc.get("completed", False)),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@app.get("/")
def read_root():
    return {"message": "Todo API is running"}


@app.get("/api/todos")
def list_todos() -> List[dict]:
    try:
        docs = get_documents("todo", {}, limit=None)
        # Sort newest first by created_at if present
        docs.sort(key=lambda d: d.get("created_at"), reverse=True)
        return [serialize_todo(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/todos", status_code=201)
def create_todo(payload: TodoCreate) -> dict:
    try:
        todo = Todo(title=payload.title)
        inserted_id = create_document("todo", todo)
        doc = db["todo"].find_one({"_id": ObjectId(inserted_id)})
        return serialize_todo(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/todos/{todo_id}")
def update_todo(todo_id: str, payload: TodoUpdate) -> dict:
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    update_fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    from datetime import datetime, timezone
    update_fields["updated_at"] = datetime.now(timezone.utc)

    result = db["todo"].update_one({"_id": oid}, {"$set": update_fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")

    doc = db["todo"].find_one({"_id": oid})
    return serialize_todo(doc)


@app.delete("/api/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: str):
    try:
        oid = ObjectId(todo_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = db["todo"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
