import os
from io import BytesIO
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import typesense
from PyPDF2 import PdfReader

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
    except Exception as e:
        print("Schema creation skipped or already exists:", e)

def extract_content(url):
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
            except PyPDF2.PdfReadError as e:
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
    visited = set()
    queue = [(seed_url.rstrip('/'), 0)]
    domain = urlparse(seed_url).netloc
    docs = []

    disallowed_extensions = ('.xml', '.atom', '.png', '.json', '.jpg', '.jpeg',
                             '.gif', '.svg', '.webp', '.bmp', '.ico')

    while queue:
        url, depth = queue.pop(0)
        base_url = url.split('#')[0].split('?')[0]
        if base_url in visited or depth > max_depth:
            continue

        visited.add(base_url)
        print(f"Crawling: {base_url}")
        doc = extract_content(base_url)
        if doc:
            docs.append(doc)

        try:
            r = requests.get(base_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                if href.startswith(('mailto:', 'javascript:')):
                    continue

                abs_url = urljoin(base_url, href).split('#')[0].rstrip('/')

                if abs_url.lower().endswith(disallowed_extensions):
                    continue

                if "/cdn-cgi/l/email-protection" in abs_url:
                    continue

                parsed = urlparse(abs_url)
                if parsed.scheme in ('http', 'https') and parsed.netloc == domain:
                    queue.append((abs_url, depth + 1))
        except:
            continue

    return docs

def index_documents(docs):
    if not docs:
        print("Nothing to index.")
        return
    print(f"Indexing {len(docs)} documents...")
    client.collections['webpages'].documents.import_(docs, {'action': 'upsert'})

def reset_collection():
    try:
        client.collections['webpages'].delete()
        print("deleted.")
    except typesense.objects.ObjectNotFound as e:
        print("does not exist", e)
    create_schema()

if __name__ == "__main__":
    reset_collection()

    seeds = os.getenv("SEARCH_DOMAINS").split(",")

    for seed in seeds:
        print(f"Crawling: {urlparse(seed).netloc}")
        docs = crawl(seed)
        index_documents(docs)

    print("Done crawldexing.")
