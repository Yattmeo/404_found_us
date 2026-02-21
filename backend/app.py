from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup, then hand control back to FastAPI."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="404 Found ML Backend API",
    version="2.0.0",
    description="Revenue projection and payment transaction processing API",
    lifespan=lifespan,
    docs_url="/api/v1/docs",          # Tells FastAPI where to host the Swagger UI
    openapi_url="/api/v1/openapi.json" # Tells FastAPI where to host the schema it needs
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "Welcome to 404 Found ML Backend API",
        "status": "success",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ml-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
