"""
This module cleanly deletes and recreates the typesense database in case it is necessary
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


def reset_collection():
    """Delete and recreate the collection (won't be necessary once the schema stops changing)"""
    try:
        client.collections['webpages'].delete()
        print("Collection deleted.")
    except typesense.exceptions.ObjectNotFound as e:
        print("Collection does not exist", e)
    create_schema()

def create_schema():
    """This creates the database for the scraped data"""
    try:
        client.collections.create({
            "name": "webpages",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "url", "type": "string"},
                {"name": "title", "type": "string", "sort": True},
                {"name": "content", "type": "string"},
                {"name": "domain", "type": "string", "facet": True},
                {"name": "last_crawled", "type": "int64", "sort": True},
                {"name": "path", "type": "string", "facet": True},
                {"name": "word_count", "type": "int32", "sort": True},
                {"name": "popularity", "type": "int32", "sort": True},
                {"name": "headers", "type": "string[]", "optional": True},
                {"name": "keywords", "type": "string[]", "optional": True},
                {"name": "language", "type": "string", "facet": True},
                {"name": "is_pdf", "type": "bool", "facet": True}
            ],
            "default_sorting_field": "popularity"
        })
        print("Collection schema created.")
    except typesense.exceptions.ObjectAlreadyExists:
        print("Schema already exists")

if __name__ == "__main__":
    reset_collection()
