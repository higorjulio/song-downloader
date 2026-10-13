from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import download
 
app = FastAPI(title="Song Downloader")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(download.router)