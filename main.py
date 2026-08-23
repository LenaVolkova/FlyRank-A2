from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
import uvicorn
import sqlite3

DB_PATH = "tasks.db"

# Create an app
app = FastAPI()

# Pydantic schema for conversion 1/0 into True/False as SQLite treats boolean like 0/1
class TaskResponse(BaseModel):
    id: int
    title: str
    done: bool # 1 is True, 0 is False

    class Config: #inner class of Pydantic to configure parent class TaskResponse
        from_attributes = True #it allows to work with task.id, not task["id"]

# Exception handler to return 400 instead of 422 for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid body"}
    )

# Function for lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # While starting the app
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    print(f"Current quantity of tasks ib database: {count}")
    if count == 0:
        initial_tasks = [("Learn FastAPI", 0), ("Install FastAPI", 1), ("Create the first app", 0)]
        cursor.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", initial_tasks)
        conn.commit()
    conn.close()
    print("Database is initialized")
    
    yield  #Here the application is launched
    
    # While stopping the app
    # If it is necessary to do while closing the app it can be added here
    print("Application is closing")

# lifespan is sent to app
app = FastAPI(lifespan=lifespan)

# Dependancy for endpoints (open/close connection)
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

class TaskCreate(BaseModel):
     title: str

# Validation for update (PUT)
class UpdateTaskModel(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

# Configure root path - retutn API description
@app.get("/")
def read_root():
    return { "name": "Task API", "version": "1.0", "endpoints": ["/tasks"] }

#Endpoint to check that server is working
@app.get("/health")
def get_info():
    return { "status": "ok" }

# Endpoint to get tasks list with parameters
@app.get("/tasks", response_model=list[TaskResponse])
def get_tasks(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, done FROM tasks")
    rows = cursor.fetchall()
    
    return [dict(row) for row in rows]

#Endpoint to get a task by id
@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task_by_id(task_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return dict(row)

#Endpoint for adding new task
# Curl string to test this endpoint:
# curl -X POST http://127.0.0.1:8000/tasks \
#      -H "Content-Type: application/json" \
#      -d '{"title": "My New Task"}'
#  (-X POST - request type, -H - sets content type to JSON, -d passes JSON peyload with specidied title)
@app.post("/tasks", status_code=201, response_model=TaskResponse)
def create_task(task_data: TaskCreate, db: sqlite3.Connection = Depends(get_db)):
#    Delete spaces from string's ends
    clean_title = task_data.title.strip()
    
    # If the title is not empty
    if not clean_title:
        raise HTTPException(
            status_code=400, 
            detail="Title cannot be empty or contain only spaces"
        )

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (clean_title, 0)
    )
    db.commit()

    new_id = cursor.lastrowid

    cursor.execute(
        "SELECT id, title, done FROM tasks WHERE id = ?", (new_id,)
    )
    row = cursor.fetchone()
    return dict(row)


### Endpoint PUT /tasks/{id}
@app.put("/tasks/{id}", response_model=TaskResponse)
def update_task(id: int, task_body: UpdateTaskModel, db: sqlite3.Connection = Depends(get_db)):
    if task_body.title is None and task_body.done is None:
        raise HTTPException(status_code=400, detail="Invalid body")
    if task_body.title is not None:
        clean_title = task_body.title.strip()
        if not clean_title:
            raise HTTPException(status_code=400, detail="Invalid body")
    else:
        clean_title = None

    cursor = db.cursor()

    cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_fields = []
    params = []
    if clean_title is not None:
        update_fields.append("title = ?")
        params.append(clean_title)
    if task_body.done is not None:
        update_fields.append("done = ?")
        params.append(1 if task_body.done else 0)

    params.append(id)  # Add id for the WHERE clause
    
    query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, params)
    db.commit()

    cursor.execute("SELECT id, title, done FROM tasks WHERE id = ?", (id,))
    row = cursor.fetchone()
    return dict(row)


### Endpoint DELETE /tasks/{id}
### for testing use the string curl -i -X DELETE http://127.0.0.1:8000/tasks/1
@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="Task not found")

    cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
    db.commit()
    
    return None


# #Endpoint for getting overall info on tasks
# @app.get("/stats")
# def get_stats():
#     total = len(tasks_db)
#     done_count = sum(1 for t in tasks_db if t["done"])
#     open_count = total - done_count
    
#     return {
#         "total": total,
#         "done": done_count,
#         "open": open_count
#     }

# #Endpoint to reset list of tasks to initial values
# @app.post("/reset")
# def reset_tasks():
#     global tasks_db
#     # Deep copy of initial tasks
#     tasks_db = [t.copy() for t in INITIAL_TASKS]
#     return {"message": "Tasks database has been reset to initial state"}

 # Launch server 
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
