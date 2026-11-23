"""Run REPLAYD from the repository root: python run.py"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("replayd.web:app", host="127.0.0.1", port=8000, reload=True)
