###   uvicorn main:app --reload --port 5000 --timeout-keep-alive 5
# above line to run server on port 5000
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Form
import uvicorn
from fastapi.responses import JSONResponse
from pymongo import MongoClient, UpdateOne
from datetime import datetime, date, timedelta, timezone
from bson import ObjectId
import math
import os
from dotenv import load_dotenv
import numpy as np
load_dotenv()
app = FastAPI()



var=int(os.getenv("example_env_var"))



@app.get("/")
async def demo():
    return JSONResponse(content={"status":f"this is a new page {var}"})