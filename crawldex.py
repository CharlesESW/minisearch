"""
Crawldexer for typesense search engine

This module crawls through a defined list of domains in .env and then indexes the contents.
"""

# standard imports
import os
from io import BytesIO
import time
import concurrent.futures

# third-party imports
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader, errors
import client_setup


client = client_setup.send_info()


def get_priority(path):
    """Assign priority based on URL path segments."""
    priority_urls = {
        'index': 0,
        'home': 0,
        'about': 1,
        'contact': 1,
        'blog': 2,
        'articles': 2,
        'docs': 2
    }
    return next((v for k, v in priority_urls.items() if k in path), 3)


def parse_pdf_content(response, url):
    """Parse PDF content from response."""
    pdf_reader = PdfReader(BytesIO(response.content))
    content = " ".join(page.extract_text() or "" for page in pdf_reader.pages)
    title = pdf_reader.metadata.title or url.split('/')[-1]
    word_count = len(content.split())
    return content, title, word_count


def parse_html_content(response, url):
    """Parse HTML content from response."""
    soup = BeautifulSoup(response.text, 'html.parser')
    title = soup.title.string.strip() if soup.title else url

    headers = [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]

    meta_keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    keywords = [kw.strip() for kw in
                meta_keywords_tag.get('content','').split(',')] if meta_keywords_tag else []

    html_tag = soup.find('html')
    language = html_tag.get('lang')[:2] if html_tag and html_tag.get('lang') else 'en'

    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
        tag.decompose()

    content = soup.get_text(separator=' ', strip=True)
    word_count = len(content.split())

    return content, title, word_count, headers, keywords, language


def extract_content(url, response=None):
    """Extracts the contents of a given URL."""
    try:
        if url.startswith(("mailto:", "javascript:")):
            return None

        if response is None:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            response.raise_for_status()

        content_type = response.headers.get('Content-Type', '').lower()
        domain = urlparse(url).netloc
        path = urlparse(url).path
        is_pdf = False

        if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
            is_pdf = True
            try:
                content, title, word_count = parse_pdf_content(response, url)
                headers, keywords, language = [], [], "en"
            except errors.PdfReadError as e:
                print(f"Failed to parse PDF {url}: {e}")
                return None
        else:
            content, title, word_count, headers, keywords, language = parse_html_content(response,
                                                                                         url)

        popularity = 0
        if "blog" in path.lower():
            popularity += 1
        if "about" in path.lower():
            popularity += 1
        if word_count > 500:
            popularity += 1

        return {
            "id": f"{domain}:{url}",
            "url": url,
            "title": title,
            "content": content,
            "domain": domain,
            "path": path,
            "last_crawled": int(time.time()),
            "word_count": word_count,
            "popularity": popularity,
            "headers": headers,
            "keywords": keywords,
            "language": language,
            "is_pdf": is_pdf
        }
    except requests.exceptions.RequestException as e:
        print(f"Failed {url}: {e}")
        return None


def crawl(seed_url, max_depth=3):
    """Crawls a website starting from the seed URL using concurrency."""
    banned_extensions = ('.xml', '.atom', '.png', '.json', '.jpg', '.jpeg',
                         '.gif', '.svg', '.webp', '.bmp', '.ico', '.zip', '.tar',
                         '.gz', '.exe', '.dmg', '.mp3', '.mp4', '.avi', '.mov')

    state = {
        'visited': set(),
        'docs': [],
        'domain': urlparse(seed_url).netloc
    }
    queue = [(seed_url.rstrip('/'), 0)]

    def process_url(url, depth):
        base_url = url.split('#')[0].split('?')[0]
        if base_url in state['visited'] or depth > max_depth:
            return []
        try:
            print(f"Crawling: {base_url}")
            response = requests.get(base_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            state['visited'].add(base_url)

            doc = extract_content(base_url, response)
            if doc:
                path = urlparse(base_url).path.lower()
                priority = get_priority(path)
                doc['popularity'] += (3 - priority)
                state['docs'].append(doc)

            soup = BeautifulSoup(response.text, 'html.parser')
            new_links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                abs_url = urljoin(base_url, href).split('#')[0].rstrip('/')
                parsed = urlparse(abs_url)

                if (not href.startswith(('mailto:', 'javascript:'))) \
                   and not abs_url.lower().endswith(banned_extensions) \
                   and "/cdn-cgi/l/email-protection" not in abs_url \
                   and parsed.scheme in ('http', 'https') \
                   and parsed.netloc == state['domain']:

                    link_priority = get_priority(parsed.path.lower())
                    new_links.append((abs_url, depth + 1, link_priority))

            new_links.sort(key=lambda x: x[2])
            return [(url, d) for url, d, _ in new_links]

        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch {url}: {e}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        while queue:
            future_to_url = {executor.submit(process_url,
                                             url, depth): (url, depth) for url, depth in queue}
            queue = []
            for future in concurrent.futures.as_completed(future_to_url):
                try:
                    new_links = future.result()
                    queue.extend(new_links)
                except (concurrent.futures.CancelledError, concurrent.futures.TimeoutError) as e:
                    print(f"Future error: {e}")

    return state['docs']


def index_documents(docs_to_index):
    """Index documents to Typesense."""
    if not docs_to_index:
        print("Nothing to index.")
        return
    print(f"Indexing {len(docs_to_index)} documents...")
    client.collections['webpages'].documents.import_(docs_to_index, {'action': 'upsert'})


if __name__ == "__main__":
    seeds = os.getenv("SEARCH_DOMAINS", "").split(",")

    for seed in seeds:
        if not seed.strip():
            continue
        print(f"Starting crawl for: {urlparse(seed).netloc}")
        done_docs = crawl(seed.strip())
        index_documents(done_docs)

    print("Crawldexing completed successfully.")
