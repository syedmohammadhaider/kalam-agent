from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Kalam API")
app.include_router(router)


@app.get("/")
def root():
    return {"message": "Kalam API"}
