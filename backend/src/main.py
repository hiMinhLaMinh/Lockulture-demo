from fastapi import FastAPI

app = FastAPI(title="Lockulture Backend")


@app.get("/health")
def healthcheck():
    return {"status": "HEALTHY", "service": "lockulture-backend"}
