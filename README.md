# mdo

Marisa's todo app

## Running the project

1. Install backend dependencies:

   ```powershell
   python -m venv backend\.venv
   .\backend\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r backend\requirements.txt
   ```

2. Start the API and static frontend:

   ```powershell
   .\backend\.venv\Scripts\Activate.ps1
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. Visit [http://localhost:8000](http://localhost:8000) to use the app. The page talks to the API endpoints at `/api/tasks` and persists tasks to `backend/data/tasks.json`.

Drag a task onto another task to create a subtask; drop between tasks to reorder within the same parent.


## API Overview

- `GET /api/tasks` &mdash; return the saved tasks (sorted by their stored order).
- `POST /api/tasks` &mdash; create a new task by providing `{ "title": "..." }`.
- `POST /api/tasks/reorder` &mdash; reorder the top-level lists by sending `{ "order": ["id1", "id2", "..."] }`.
- `POST /api/tasks/move` &mdash; move or nest a task using `{ "task_id": "...", "parent_id": "... or null", "position": 0 }`.
- `DELETE /api/tasks/{task_id}` &mdash; remove the specified task.
