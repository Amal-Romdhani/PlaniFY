from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.crud import router as crud_router


app = FastAPI(title="PlaniFY API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(crud_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Vérifie que l'API est disponible."""

    return {"status": "ok"}
