
import re
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from collections import deque
from bs4 import BeautifulSoup

CRAWL_DEPTH = 2  # Reduced to 2
ALLOWED_DOMAIN = ""  # Leave empty to crawl any domain
PAGES_PER_SEED = 50
MAX_PAGES = 200

BLOCKED_PAGES_FULL = {
    "https://example.com/admin",
    "https://example.com/login", 
    "https://example.com/wp-admin"
}

BLOCK_PATTERNS = [
    r".*\.(pdf|jpg|jpeg|png|gif|mp4|mp3|zip|exe)$",
    r".*/wp-admin/.*",
    r".*/admin/.*", 
    r".*\?.*utm_.*",
    r".*/feed/.*"
]

REQUEST_DELAY = 1.0
TIMEOUT = 30
MAX_RETRIES = 3

SEEDS_FILE = "seeds.txt"
LOG_FILE = "crawlLog.txt" 
OUTPUT_DIR = "output"
MDS_DIR = "output/MDs"
INDEX_FILE = "output/index.jsonl"
FAILED_URLS_FILE = "output/failed_urls.txt"

def validate_config():
    errors = []
    
    if CRAWL_DEPTH < 1:
        errors.append("CRAWL_DEPTH must be at least 1")
    if PAGES_PER_SEED < 1:
        errors.append("PAGES_PER_SEED must be at least 1") 
    if MAX_PAGES < 1:
        errors.append("MAX_PAGES must be at least 1")
    # ALLOWED_DOMAIN can be empty for cross-domain crawling
    
    for pattern in BLOCK_PATTERNS:
        try:
            re.compile(pattern)
        except re.error:
            errors.append(f"Invalid regex: {pattern}")
    
    return errors

def show_config():
    domain_info = ALLOWED_DOMAIN if ALLOWED_DOMAIN else "Any domain (cross-domain crawling)"
    print(f"Domain: {domain_info}")
    print(f"Depth: {CRAWL_DEPTH}, Pages/seed: {PAGES_PER_SEED}, Max: {MAX_PAGES}")
    print(f"Delay: {REQUEST_DELAY}s, Timeout: {TIMEOUT}s, Retries: {MAX_RETRIES}")
    print(f"Blocked: {len(BLOCKED_PAGES_FULL)} URLs, {len(BLOCK_PATTERNS)} patterns")

class WebCrawler:
    def __init__(self):
        self.session = None
        self.url_queue = deque()
        self.visited_urls = set()
        self.failed_urls = []
        self.crawled_pages = 0
        self.seed_pages = {}
        
    def load_seeds(self):
        try:
            with open(SEEDS_FILE, 'r') as f:
                seeds = [line.strip() for line in f if line.strip()]
                for seed in seeds:
                    self.url_queue.append((seed, 0))  # (url, depth)
                    self.seed_pages[seed] = []
                print(f"Loaded {len(seeds)} seed URLs")
                return len(seeds)
        except FileNotFoundError:
            print(f"Warning: {SEEDS_FILE} not found, using default")
            default_seed = "https://example.com"
            self.url_queue.append((default_seed, 0))
            self.seed_pages[default_seed] = []
            return 1
        
    async def start_session(self):
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def is_valid_domain(self, url):
        if not ALLOWED_DOMAIN:  # If empty, allow any domain
            return True
        parsed = urlparse(url)
        return ALLOWED_DOMAIN in parsed.netloc
    
    def normalize_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def is_blocked_url(self, url):
        if url in BLOCKED_PAGES_FULL:
            return True
        
        for pattern in BLOCK_PATTERNS:
            if re.match(pattern, url):
                return True
        return False
    
    async def fetch_page(self, url):
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    return content, response.status
                else:
                    return None, response.status
        except Exception as e:
            return None, str(e)
    
    def extract_links(self, content, base_url):
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for tag in soup.find_all(['a', 'link'], href=True):
            href = tag.get('href')
            if href:
                full_url = urljoin(base_url, href)
                normalized = self.normalize_url(full_url)
                if self.is_valid_domain(normalized) and not self.is_blocked_url(normalized):
                    links.append(normalized)
        
        return list(set(links))  # Remove duplicates
    
    async def crawl_url(self, url, depth):
        if url in self.visited_urls or self.is_blocked_url(url):
            return []
        
        if not self.is_valid_domain(url):
            return []
        
        if self.crawled_pages >= MAX_PAGES:
            return []
        
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited_urls:
            return []
        
        self.visited_urls.add(normalized_url)
        
        print(f"Crawling: {normalized_url} (depth {depth})")
        content, status = await self.fetch_page(normalized_url)
        
        discovered_links = []
        if content:
            self.crawled_pages += 1
            
            # Extract links for next depth level
            if depth < CRAWL_DEPTH:
                discovered_links = self.extract_links(content, normalized_url)
                print(f"  Found {len(discovered_links)} links")
                
                # Add to queue for next depth
                for link in discovered_links:
                    if link not in self.visited_urls:
                        self.url_queue.append((link, depth + 1))
            
            await asyncio.sleep(REQUEST_DELAY)
        else:
            self.failed_urls.append((normalized_url, status))
            print(f"  Failed: {status}")
        
        return discovered_links
    
    async def crawl(self):
        await self.start_session()
        
        seed_count = self.load_seeds()
        print(f"Starting crawl with {seed_count} seeds\n")
        
        while self.url_queue and self.crawled_pages < MAX_PAGES:
            url, depth = self.url_queue.popleft()
            
            # Check per-seed limit
            seed_url = self.find_seed_for_url(url)
            if seed_url and len(self.seed_pages[seed_url]) >= PAGES_PER_SEED:
                continue
            
            links = await self.crawl_url(url, depth)
            
            # Track which seed this page belongs to
            if seed_url:
                self.seed_pages[seed_url].append(url)
        
        await self.close_session()
        
        print(f"\nCrawl completed:")
        print(f"Total pages crawled: {self.crawled_pages}")
        print(f"Failed URLs: {len(self.failed_urls)}")
        for seed, pages in self.seed_pages.items():
            print(f"  {seed}: {len(pages)} pages")
    
    def find_seed_for_url(self, url):
        for seed in self.seed_pages.keys():
            if url.startswith(seed) or url == seed:
                return seed
        # Return first seed as default
        return list(self.seed_pages.keys())[0] if self.seed_pages else None

if __name__ == "__main__":
    print("Web Crawler Configuration\n")
    
    errors = validate_config()
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✓ Configuration valid\n")
        show_config()
        print("\n✅ Step 3: URL Management System Test")
        
        crawler = WebCrawler()
        asyncio.run(crawler.crawl())
