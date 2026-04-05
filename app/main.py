from fastapi import FastAPI
from dotenv import load_dotenv
from .db import engine, Base
from .api import router

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hospitality Event Search API")

app.include_router(router)
