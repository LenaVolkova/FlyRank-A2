from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends
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

    class Config:
        from_attributes = True

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
    print(f"Текущее количество задач в БД при старте: {count}")
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

# class TaskCreate(BaseModel):
#     title: str

# # Validation for update (PUT)
# class UpdateTaskModel(BaseModel):
#     # Field(..., min_length=1) is to ensure that the string is not empty.
#     # "Optional" allows to update "title" or "done", or both.
#     title: str | None = Field(None, min_length=1, description="Task's title cannot be empty")
#     done: bool | None = Field(None, description="Status of the task")

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

# #Endpoint to get a task by id
# @app.get("/tasks/{task_id}")
# def get_task_by_id(task_id: int):
#     for task in tasks_db:
#         if task["id"] == task_id:
#             return task
            
#     # If there is no task with such a number, then return 404 error code
#     raise HTTPException(status_code=404, detail="Task not found")

# #Enpoint for adding new task
# @app.post("/tasks", status_code=201)
# def create_task(task_data: TaskCreate):
#     # Delete spaces from string's ends
#     clean_title = task_data.title.strip()
    
#     # If the title is not empty
#     if not clean_title:
#         raise HTTPException(
#             status_code=400, 
#             detail="Title cannot be empty or contain only spaces"
#         )
    
#     new_id = max([t["id"] for t in tasks_db], default=0) + 1
    
#     new_task = {
#         "id": new_id,
#         "title": clean_title,  
#         "done": False              
#     }
    
#     tasks_db.append(new_task)
#     return new_task


# ### Endpoint PUT /tasks/{id}
# @app.put("/tasks/{id}")
# async def update_task(id: int, task_body: UpdateTaskModel):
#     task = next((t for t in tasks_db if t["id"] == id), None)
    
#     if task is None:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND, 
#             detail=f"Task with id {id} not found"
#         )
    
#     update_data = task_body.model_dump(exclude_unset=True)
#     if not update_data:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, 
#             detail="Body cannot be empty. Provide 'title' or 'done'."
#         )
    
#     if "title" in update_data:
#         task["title"] = update_data["title"]
#     if "done" in update_data:
#         task["done"] = update_data["done"]
        
#     return task


# ### Endpoint DELETE /tasks/{id}
# @app.delete("/tasks/{task_id}", status_code=204, tags=["Tasks"])
# async def delete_task(task_id: int):
#     for index, task in enumerate(tasks_db):
#         if task["id"] == task_id:
#             tasks_db.pop(index)  
#             return None          # FastAPI returns 204
            
#     #If nothing is found then return 404
#     raise HTTPException(status_code=404, detail=f"Task with ID {task_id})

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
