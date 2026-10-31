"""
Backwards-compatible entrypoint shim — the unified application lives in
app.main. `uvicorn main:app`, `uvicorn app.main:app`, and
`from main import app/root` all work.
"""
from app.main import app, root  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
