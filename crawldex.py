"""
Crawldexer for typesense search engine

This module crawls through a defined list of domains in .env and then indexes the contents.
"""
import os
from io import BytesIO
import time
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader, errors
import client_setup

client = client_setup.send_info()


def extract_content(url):
    """This extracts the contents of a given url"""
    try:
        if url.startswith(("mailto:", "javascript:")):
            return None

        r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=10)
        r.raise_for_status()

        content_type = r.headers.get('Content-Type', '')
        domain = urlparse(url).netloc
        path = urlparse(url).path
        is_pdf = False
        word_count = 0
        doc_headers = []
        meta_keywords = []
        language = "en"

        if 'application/pdf' in content_type or url.endswith('.pdf'):
            is_pdf = True
            try:
                pdf_reader = PdfReader(BytesIO(r.content))
                content = " ".join(page.extract_text() or "" for page in pdf_reader.pages)
                title = url.split('/')[-1]
                word_count = len(content.split())
            except errors.PdfReadError as e:
                print(f"Failed to parse PDF {url}: {e}")
                return None
        else:
            soup = BeautifulSoup(r.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else url


            doc_headers = [h.get_text().strip() for h in soup.find_all(['h1', 'h2',
                                                                        'h3', 'h4',
                                                                        'h5', 'h6'])]


            meta_keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords_tag:
                meta_keywords = [kw.strip() for kw in meta_keywords_tag.get('content',
                                                                            '').split(',')]
            html_tag = soup.find('html')
            if html_tag and html_tag.get('lang'):
                language = html_tag.get('lang')[:2]

            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
                tag.decompose()

            content = soup.get_text(separator=' ', strip=True)
            word_count = len(content.split())

        #temporary popularity score (not ready for pagerank yet)
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
            "headers": doc_headers,
            "keywords": meta_keywords,
            "language": language,
            "is_pdf": is_pdf
        }
    except requests.exceptions.RequestException as e:
        print(f"Failed {url}: {e}")
        return None

def crawl(seed_url, max_depth=3):
    """This will crawl website starting from seed URL up to specified depth."""
    banned_extensions = ('.xml', '.atom', '.png', '.json', '.jpg', '.jpeg',
                     '.gif', '.svg', '.webp', '.bmp', '.ico', '.zip', '.tar',
                     '.gz', '.exe', '.dmg', '.mp3', '.mp4', '.avi', '.mov')

    state = {
        'visited': set(),
        'docs': [],
        'domain': urlparse(seed_url).netloc
    }
    queue = [(seed_url.rstrip('/'), 0)]


    priority_urls = {
        'index': 0,
        'home': 0,
        'about': 1,
        'contact': 1,
        'blog': 2,
        'articles': 2,
        'docs': 2
    }

    while queue:
        url, depth = queue.pop(0)
        base_url = url.split('#')[0].split('?')[0]

        if base_url in state['visited'] or depth > max_depth:
            continue

        state['visited'].add(base_url)
        print(f"Crawling: {base_url}")

        path = urlparse(base_url).path.lower()
        priority = next((v for k, v in priority_urls.items() if k in path), 3)

        if (doc := extract_content(base_url)):
            doc['popularity'] += (3 - priority)
            state['docs'].append(doc)

        try:
            response = requests.get(base_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                abs_url = urljoin(base_url, href).split('#')[0].rstrip('/')
                parsed = urlparse(abs_url)

                if (not href.startswith(('mailto:', 'javascript:'))) \
                   and not abs_url.lower().endswith(banned_extensions) \
                   and "/cdn-cgi/l/email-protection" not in abs_url \
                   and parsed.scheme in ('http', 'https') \
                   and parsed.netloc == state['domain']:


                    path = parsed.path.lower()
                    link_priority = next((v for k, v in priority_urls.items() if k in path), 3)
                    links.append((abs_url, depth + 1, link_priority))

            links.sort(key=lambda x: x[2])
            queue.extend((url, d) for url, d, _ in links)

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


if __name__ == "__main__":

    seeds = os.getenv("SEARCH_DOMAINS").split(",")

    for seed in seeds:
        print(f"Crawling: {urlparse(seed).netloc}")
        done_docs = crawl(seed)
        index_documents(done_docs)

    print("Crawldexing completed successfully.")
