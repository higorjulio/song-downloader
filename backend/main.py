from fastapi import FastAPI
 
from routes import download
 
app = FastAPI(title="YT Music Downloader")
 
app.include_router(download.router)