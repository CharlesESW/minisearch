"""
Crawldexer for typesense search engine

This module crawls through a defined list of domains in .env and then indexes the contents.
"""
import os
from io import BytesIO
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import typesense
from PyPDF2 import PdfReader, errors

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

def create_schema():
    """This creates the database for the scraped data """
    try:
        client.collections.create({
            "name": "webpages",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "url", "type": "string"},
                {"name": "title", "type": "string"},
                {"name": "content", "type": "string"},
                {"name": "domain", "type": "string", "facet": True}
            ]
        })
        print("Collection schema created.")
    except typesense.exceptions.ObjectAlreadyExists:
        print("Schema creation already exists")

def extract_content(url):
    """This extracts the contents of a given url"""
    try:
        if url.startswith("mailto:") or url.startswith("javascript:"):
            return None

        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)

        content_type = r.headers.get('Content-Type', '')
        if 'application/rss+xml' in content_type or url.endswith('.xml'):
            return None

        if 'application/pdf' in content_type or url.endswith('.pdf'):
            try:
                pdf_reader = PdfReader(BytesIO(r.content))
                content = " ".join(page.extract_text() or "" for page in pdf_reader.pages)
                title = url.split('/')[-1]
            except errors.PdfReadError as e:
                print(f"Failed to parse PDF {url}: {e}")
                return None
        else:
            soup = BeautifulSoup(r.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else url
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            content = soup.get_text(separator=' ', strip=True)

        domain = urlparse(url).netloc
        return {
            "id": f"{domain}:{url}",
            "url": url,
            "title": title,
            "content": content,
            "domain": domain
        }
    except requests.exceptions.RequestException as e:
        print(f"Failed {url}: {e}")
        return None

def crawl(seed_url, max_depth=3):
    """This will crawl website starting from seed URL up to specified depth."""
    banned_extensions = ('.xml', '.atom', '.png', '.json', '.jpg', '.jpeg',
                     '.gif', '.svg', '.webp', '.bmp', '.ico')

    state = {
        'visited': set(),
        'docs': [],
        'domain': urlparse(seed_url).netloc
    }
    queue = [(seed_url.rstrip('/'), 0)]

    while queue:
        url, depth = queue.pop(0)
        base_url = url.split('#')[0].split('?')[0]

        if base_url in state['visited'] or depth > max_depth:
            continue

        state['visited'].add(base_url)
        print(f"Crawling: {base_url}")

        if (doc := extract_content(base_url)):
            state['docs'].append(doc)

        try:
            response = requests.get(base_url, headers={'User-Agent' : 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                abs_url = urljoin(base_url, href).split('#')[0].rstrip('/')
                parsed = urlparse(abs_url)

                if not (href.startswith(('mailto:', 'javascript:'))) \
                   and not abs_url.lower().endswith(banned_extensions) \
                   and "/cdn-cgi/l/email-protection" not in abs_url \
                   and parsed.scheme in ('http', 'https') \
                   and parsed.netloc == state['domain']:
                    queue.append((abs_url, depth + 1))

        except requests.exceptions.RequestException:
            continue

    return state['docs']

def index_documents(docs_to_index):
    """This will add the gotten docs from crawling to the typesense collection"""
    if not docs_to_index:
        print("Nothing to index.")
        return
    print(f"Indexing {len(docs_to_index)} documents...")
    client.collections['webpages'].documents.import_(docs_to_index, {'action': 'upsert'})

def reset_collection():
    """
    This deletes everything from the collection so it can be clean readded
    Can probably removed when i trust it enough as well as the creation one
    """
    try:
        client.collections['webpages'].delete()
        print("deleted.")
    except typesense.exceptions.ObjectNotFound as e:
        print("does not exist", e)
    create_schema()

if __name__ == "__main__":
    reset_collection()

    seeds = os.getenv("SEARCH_DOMAINS").split(",")

    for seed in seeds:
        print(f"Crawling: {urlparse(seed).netloc}")
        done_docs = crawl(seed)
        index_documents(done_docs)

    print("Done crawldexing.")
