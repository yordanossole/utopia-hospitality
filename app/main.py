from fastapi import FastAPI
from .db import engine, Base
from .api import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hospitality Event Search API")

app.include_router(router)
