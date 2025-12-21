from pymongo import MongoClient
import os
from dotenv import load_dotenv

def get_database(dbname='grail-kun'):
    # Load environment variables
    load_dotenv()

    # Get connection string from .env file
    connection_string = os.getenv("MONGODB_URI")
    if not connection_string:
        raise ValueError("MongoDB URI not found in .env file")
    
    # Create and return database connection
    client = MongoClient(connection_string)
    return client[dbname]