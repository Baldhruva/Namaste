###   uvicorn main:app --reload --port 5000 host x.x.x.x
# find ip from ipconfig from cmd
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


#     from pymongo.mongo_client import MongoClient
# from pymongo.server_api import ServerApi

# uri = "mongodb+srv://namaste-user:<db_password>@sih2025-namaste.b7sdvkj.mongodb.net/?retryWrites=true&w=majority&appName=sih2025-namaste"

# # Create a new client and connect to the server
# client = MongoClient(uri, server_api=ServerApi('1'))

# # Send a ping to confirm a successful connection
# try:
#     client.admin.command('ping')
#     print("Pinged your deployment. You successfully connected to MongoDB!")
# except Exception as e:
#     print(e)





if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=5000, reload=True)
