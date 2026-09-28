from fastapi import FastAPI
 
from routes import download
 
app = FastAPI(title="Song Downloader")
 
app.include_router(download.router)