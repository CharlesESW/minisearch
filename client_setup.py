"""
Takes the client information from the .env file and send its out to who needs it
"""

import os

from dotenv import load_dotenv
import typesense

load_dotenv()

client = typesense.Client({
    'nodes': [{
        'host': os.getenv("TYPESENSE_INTERNAL_HOST"),
        'port': os.getenv("TYPESENSE_INTERNAL_PORT"),
        'protocol': os.getenv("TYPESENSE_INTERNAL_PROTOCOL")
    }],
    'api_key': os.getenv("TYPESENSE_INTERNAL_API_KEY"),
    'connection_timeout_seconds': 2
})

def send_info():
    """
    Sends client info
    """
    return client
