def main() -> None:
    import uvicorn

    uvicorn.run("design_backend.api:app", host="127.0.0.1", port=8000, reload=False)
