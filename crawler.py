
import re
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from collections import deque
from bs4 import BeautifulSoup
import os
import shutil
import json
import logging
from datetime import datetime

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawlLog.txt'),
        logging.StreamHandler()
    ]
)

CRAWL_DEPTH = 1 
ALLOWED_DOMAIN = ""  # Leave empty to crawl any domain
PAGES_PER_SEED = 50
MAX_PAGES = 200

BLOCKED_PAGES_FULL = {
    "https://example.com/admin",
    "https://example.com/login", 
    "https://example.com/wp-admin"
}

BLOCK_PATTERNS = [
    r".*\.(pdf|jpg|jpeg|png|gif|mp4|mp3|zip|exe|css)$",
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
    logging.info("Validating crawler configuration...")
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
    
    if errors:
        for error in errors:
            logging.error(f"Configuration error: {error}")
        return errors
    
    logging.info("Configuration validation passed")
    return errors

def show_config():
    logging.info("Displaying crawler configuration...")
    domain_info = ALLOWED_DOMAIN if ALLOWED_DOMAIN else "Any domain (cross-domain crawling)"
    config_msg = f"Domain: {domain_info}, Depth: {CRAWL_DEPTH}, Pages/seed: {PAGES_PER_SEED}, Max: {MAX_PAGES}, Delay: {REQUEST_DELAY}s, Timeout: {TIMEOUT}s, Retries: {MAX_RETRIES}, Blocked: {len(BLOCKED_PAGES_FULL)} URLs, {len(BLOCK_PATTERNS)} patterns"
    
    print(f"Domain: {domain_info}")
    print(f"Depth: {CRAWL_DEPTH}, Pages/seed: {PAGES_PER_SEED}, Max: {MAX_PAGES}")
    print(f"Delay: {REQUEST_DELAY}s, Timeout: {TIMEOUT}s, Retries: {MAX_RETRIES}")
    print(f"Blocked: {len(BLOCKED_PAGES_FULL)} URLs, {len(BLOCK_PATTERNS)} patterns")
    
    logging.info(config_msg)

class WebCrawler:
    def __init__(self):
        self.session = None
        self.url_queue = deque()
        self.visited_urls = set()
        self.failed_urls = []
        self.crawled_pages = 0
        self.seed_pages = {}
        self.crawled_data = []  # Store page data for JSONL
        self.seeds_list = []  # Track seeds order for indexing
        
    def load_seeds(self):
        logging.info(f"Loading seed URLs from {SEEDS_FILE}...")
        try:
            with open(SEEDS_FILE, 'r') as f:
                seeds = [line.strip() for line in f if line.strip()]
                self.seeds_list = seeds  # Store seeds for indexing
                for seed in seeds:
                    self.url_queue.append((seed, 0))  # (url, depth)
                    self.seed_pages[seed] = []
                logging.info(f"Loaded {len(seeds)} seed URLs: {seeds}")
                print(f"Loaded {len(seeds)} seed URLs")
                return len(seeds)
        except FileNotFoundError:
            logging.warning(f"{SEEDS_FILE} not found, using default seed")
            print(f"Warning: {SEEDS_FILE} not found, using default")
            default_seed = "https://example.com"
            self.seeds_list = [default_seed]
            self.url_queue.append((default_seed, 0))
            self.seed_pages[default_seed] = []
            return 1
    
    def clean_output_dir(self):
        """Clean existing output files before starting new crawl"""
        logging.info("Cleaning output directory...")
        try:
            # Clean all output files
            files_to_clean = [INDEX_FILE, FAILED_URLS_FILE]
            for file_path in files_to_clean:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Removed {file_path}")
            
            if os.path.exists(MDS_DIR):
                shutil.rmtree(MDS_DIR)
                logging.info(f"Removed directory {MDS_DIR}")
            
            logging.info("Output directory cleaned successfully")
            print("✓ Cleaned existing output files")
            
            os.makedirs(MDS_DIR, exist_ok=True)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            
        except Exception as e:
            logging.error(f"Could not clean output directory: {e}")
            print(f"Warning: Could not clean output directory: {e}")
        
    async def start_session(self):
        """Initialize session with comprehensive timeout and connection settings"""
        logging.info("Starting HTTP session...")
        try:
            timeout = aiohttp.ClientTimeout(
                total=TIMEOUT,
                connect=10,  # Connection timeout
                sock_read=TIMEOUT-5  # Socket read timeout
            )
            
            # Connection limits to prevent overwhelming servers
            connector = aiohttp.TCPConnector(
                limit=10,  # Total connection pool size
                limit_per_host=2,  # Max 2 connections per host
                keepalive_timeout=30
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; WebCrawler/1.0)'
                }
            )
            logging.info("HTTP session started successfully")
            
        except Exception as e:
            logging.error(f"Session initialization error: {e}")
            print(f"Session initialization error: {e}")
            # Fallback to basic session
            timeout = aiohttp.ClientTimeout(total=TIMEOUT)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        """Safely close session with error handling"""
        logging.info("Closing HTTP session...")
        if self.session:
            try:
                await self.session.close()
                # Wait a bit for proper cleanup
                await asyncio.sleep(0.1)
                logging.info("HTTP session closed successfully")
            except Exception as e:
                logging.warning(f"Session close warning: {e}")
                print(f"Session close warning: {e}")
    
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
    
    async def fetch_page(self, url, retry_count=0):
        """Fetch page with retry logic and comprehensive error handling"""
        if retry_count == 0:
            logging.info(f"Fetching page: {url}")
        else:
            logging.info(f"Retrying page ({retry_count}/{MAX_RETRIES}): {url}")
            
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    logging.info(f"Successfully fetched {url} ({len(content)} chars)")
                    return content, response.status
                elif response.status in [404, 403, 401]:
                    # Don't retry for these errors
                    logging.warning(f"HTTP {response.status} for {url}")
                    return None, f"HTTP {response.status}"
                else:
                    # Retry for server errors (5xx) and other issues
                    if retry_count < MAX_RETRIES:
                        logging.warning(f"HTTP {response.status} for {url}, retrying...")
                        await asyncio.sleep(REQUEST_DELAY * (retry_count + 1))
                        return await self.fetch_page(url, retry_count + 1)
                    logging.error(f"HTTP {response.status} for {url} (max retries exceeded)")
                    return None, f"HTTP {response.status} (max retries)"
                    
        except asyncio.TimeoutError:
            if retry_count < MAX_RETRIES:
                logging.warning(f"Timeout for {url}, retrying...")
                await asyncio.sleep(REQUEST_DELAY * (retry_count + 1))
                return await self.fetch_page(url, retry_count + 1)
            logging.error(f"Timeout for {url} after {MAX_RETRIES} retries")
            return None, f"Timeout after {MAX_RETRIES} retries"
            
        except aiohttp.ClientError as e:
            if retry_count < MAX_RETRIES:
                logging.warning(f"Network error for {url}: {type(e).__name__}, retrying...")
                await asyncio.sleep(REQUEST_DELAY * (retry_count + 1))
                return await self.fetch_page(url, retry_count + 1)
            logging.error(f"Network error for {url}: {type(e).__name__} (max retries exceeded)")
            return None, f"Network error: {type(e).__name__}"
            
        except Exception as e:
            # Don't retry for unexpected errors, but log them
            logging.error(f"Unexpected error for {url}: {type(e).__name__}: {str(e)}")
            return None, f"Unexpected error: {type(e).__name__}: {str(e)}"
    
    def extract_links(self, content, base_url):
        """Extract links with error handling for malformed HTML/URLs"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            links = []
            
            for tag in soup.find_all(['a', 'link'], href=True):
                try:
                    href = tag.get('href')
                    if not href:
                        continue
                        
                    # Handle relative URLs and malformed URLs
                    try:
                        full_url = urljoin(base_url, href)
                        normalized = self.normalize_url(full_url)
                        
                        # Additional validation
                        if not normalized.startswith(('http://', 'https://')):
                            continue
                            
                        if self.is_valid_domain(normalized) and not self.is_blocked_url(normalized):
                            links.append(normalized)
                            
                    except Exception:
                        # Skip malformed URLs
                        continue
                        
                except Exception:
                    # Skip malformed tags
                    continue
            
            return list(set(links))  # Remove duplicates
            
        except Exception as e:
            print(f"  Link extraction error: {type(e).__name__}")
            return []
    
    def extract_content(self, html_content, url):
        """Extract content with error handling for malformed HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'aside', 'header']):
                element.decompose()
            
            # Extract title with fallbacks
            title = None
            try:
                title_tag = soup.find('title')
                title = title_tag.get_text(strip=True) if title_tag else None
            except Exception:
                pass
            
            if not title:
                title = self.url_to_title(url)
            
            # Extract meta description with error handling
            description = ""
            try:
                meta_desc = soup.find('meta', {'name': 'description'})
                description = meta_desc.get('content', '').strip() if meta_desc else ''
            except Exception:
                pass
            
            # Find main content area with multiple fallbacks
            main_content = None
            try:
                main_content = (soup.find('main') or 
                               soup.find('article') or 
                               soup.find('div', class_=re.compile('content|main', re.I)) or
                               soup.body)
            except Exception:
                main_content = soup.body
            
            # Extract text content
            if main_content:
                try:
                    content_text = main_content.get_text(separator='\n', strip=True)
                except Exception:
                    content_text = str(main_content)
            else:
                try:
                    content_text = soup.get_text(separator='\n', strip=True)
                except Exception:
                    content_text = "Content extraction failed"
            
            # Clean up content
            try:
                lines = [line.strip() for line in content_text.split('\n') if line.strip()]
                clean_content = '\n\n'.join(lines)
            except Exception:
                clean_content = content_text
            
            return {
                'title': title,
                'description': description, 
                'content': clean_content,
                'url': url,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            # If all else fails, return basic structure
            return {
                'title': self.url_to_title(url),
                'description': '', 
                'content': f"Content extraction failed: {type(e).__name__}",
                'url': url,
                'timestamp': datetime.now().isoformat()
            }
    
    def url_to_title(self, url):
        parsed = urlparse(url)
        path = parsed.path.strip('/').split('/')[-1] or 'Home'
        return path.replace('-', ' ').replace('_', ' ').title()
    
    def url_to_filename(self, url):
        parsed = urlparse(url)
        domain = parsed.netloc.replace('.', '_').replace('www_', '')
        path = parsed.path.strip('/').replace('/', '_') or 'index'
        
        # Clean filename
        filename = f"{domain}_{path}"
        filename = re.sub(r'[^\w\-_]', '_', filename)
        filename = re.sub(r'_+', '_', filename).strip('_')
        
        return f"{filename[:100]}.md"  # Limit length
    
    def create_markdown(self, page_data):
        markdown = f"# {page_data['title']}\n\n"
        
        if page_data['description']:
            markdown += f"*{page_data['description']}*\n\n"
        
        markdown += f"**URL:** {page_data['url']}\n"
        markdown += f"**Crawled:** {page_data['timestamp']}\n\n"
        markdown += "---\n\n"
        markdown += page_data['content']
        
        return markdown
    
    def save_markdown(self, content, filename):
        """Save markdown with error handling and recovery"""
        try:
            filepath = os.path.join(MDS_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
        except UnicodeEncodeError:
            # Try with different encoding if UTF-8 fails
            try:
                filepath = os.path.join(MDS_DIR, filename)
                with open(filepath, 'w', encoding='utf-8', errors='replace') as f:
                    f.write(content)
                print(f"  Warning: Used fallback encoding for {filename}")
            except Exception as e:
                print(f"  Critical save error: {e}")
                
        except OSError as e:
            # Handle filename/path issues
            try:
                # Create safe filename
                safe_filename = re.sub(r'[^\w\-_.]', '_', filename)[:50] + '.md'
                filepath = os.path.join(MDS_DIR, safe_filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  Used safe filename: {safe_filename}")
            except Exception as e:
                print(f"  Critical save error: {e}")
                
        except Exception as e:
            print(f"  Unexpected save error: {e}")
    
    def save_jsonl_index(self):
        """Save crawled pages data to JSONL index file"""
        if not self.crawled_data:
            return
            
        try:
            with open(INDEX_FILE, 'w', encoding='utf-8') as f:
                for page_data in self.crawled_data:
                    json_line = json.dumps(page_data, ensure_ascii=False)
                    f.write(json_line + '\n')
            print(f"✓ Created index.jsonl with {len(self.crawled_data)} entries")
        except Exception as e:
            print(f"Error creating index.jsonl: {e}")
    
    def save_failed_urls(self):
        """Save failed URLs to file"""
        if not self.failed_urls:
            return
            
        try:
            with open(FAILED_URLS_FILE, 'w', encoding='utf-8') as f:
                f.write(f"Failed URLs - {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
                for url, status in self.failed_urls:
                    f.write(f"{url} - {status}\n")
            print(f"✓ Saved {len(self.failed_urls)} failed URLs")
        except Exception as e:
            print(f"Error saving failed URLs: {e}")
    
    async def crawl_url(self, url, depth):
        if url in self.visited_urls or self.is_blocked_url(url):
            return []
        
        if not self.is_valid_domain(url):
            logging.debug(f"Skipping invalid domain: {url}")
            return []
        
        if self.crawled_pages >= MAX_PAGES:
            logging.info(f"Reached maximum pages limit ({MAX_PAGES})")
            return []
        
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited_urls:
            return []
        
        self.visited_urls.add(normalized_url)
        
        logging.info(f"Crawling page {self.crawled_pages + 1}: {normalized_url} (depth {depth})")
        print(f"Crawling: {normalized_url} (depth {depth})")
        content, status = await self.fetch_page(normalized_url)
        
        discovered_links = []
        if content:
            self.crawled_pages += 1
            
            # Find which seed this belongs to and get indexes
            seed_url = self.find_seed_for_url(normalized_url)
            seed_index = self.seeds_list.index(seed_url) if seed_url in self.seeds_list else 0
            page_index = len(self.seed_pages[seed_url]) if seed_url else 0
            
            # Extract and process content
            page_data = self.extract_content(content, normalized_url)
            
            # Create markdown content
            markdown = self.create_markdown(page_data)
            
            # Save to file
            filename = self.url_to_filename(normalized_url)
            self.save_markdown(markdown, filename)
            
            # Store clean, minimal data for JSONL index
            page_data_jsonl = {
                'url': normalized_url,
                'title': page_data['title'],
                'file_path': f"MDs/{filename}",
                'page_index': f"{seed_index},{page_index},{depth}",
                'domain': urlparse(normalized_url).netloc,
                'word_count': len(page_data['content'].split()),
                'timestamp': page_data['timestamp']
            }
            self.crawled_data.append(page_data_jsonl)
            
            # Extract links for next depth level
            if depth < CRAWL_DEPTH:
                discovered_links = self.extract_links(content, normalized_url)
                logging.info(f"Found {len(discovered_links)} links on {normalized_url}")
                print(f"  Found {len(discovered_links)} links | Saved: {filename}")
                
                # Add to queue for next depth
                for link in discovered_links:
                    if link not in self.visited_urls:
                        self.url_queue.append((link, depth + 1))
            else:
                logging.info(f"Max depth reached for {normalized_url}")
                print(f"  Max depth reached | Saved: {filename}")
            
            await asyncio.sleep(REQUEST_DELAY)
        else:
            self.failed_urls.append((normalized_url, status))
            logging.error(f"Failed to crawl {normalized_url}: {status}")
            print(f"  Failed: {status}")
        
        return discovered_links
    
    async def crawl(self):
        """Main crawl method with comprehensive error handling"""
        logging.info("Starting web crawler...")
        try:
            await self.start_session()
            
            # Clean previous results
            self.clean_output_dir()
            
            seed_count = self.load_seeds()
            logging.info(f"Starting crawl with {seed_count} seeds")
            print(f"Starting crawl with {seed_count} seeds\n")
            
            successful_requests = 0
            
            while self.url_queue and self.crawled_pages < MAX_PAGES:
                try:
                    url, depth = self.url_queue.popleft()
                    
                    # Check per-seed limit
                    seed_url = self.find_seed_for_url(url)
                    if seed_url and len(self.seed_pages[seed_url]) >= PAGES_PER_SEED:
                        continue
                    
                    links = await self.crawl_url(url, depth)
                    
                    # Track which seed this page belongs to
                    if seed_url:
                        self.seed_pages[seed_url].append(url)
                        
                    if links is not None:  # Successful request
                        successful_requests += 1
                        
                except Exception as e:
                    logging.error(f"Error processing URL from queue: {e}")
                    print(f"Error processing URL from queue: {e}")
                    continue
            
            # Show crawl statistics
            stats_msg = f"Crawl completed - Successful: {successful_requests}, Pages: {self.crawled_pages}, Failed: {len(self.failed_urls)}"
            logging.info(stats_msg)
            
            if successful_requests == 0:
                logging.warning("No pages were successfully crawled")
                print("⚠️  Warning: No pages were successfully crawled")
            
        except Exception as e:
            logging.error(f"Critical crawl error: {e}")
            print(f"Critical crawl error: {e}")
            
        finally:
            # Always close session and save what we have
            try:
                await self.close_session()
            except Exception as e:
                logging.error(f"Session cleanup error: {e}")
                print(f"Session cleanup error: {e}")
            
            # Save output files even if crawl was interrupted
            try:
                self.save_jsonl_index()
                self.save_failed_urls()
                logging.info("Output files saved successfully")
            except Exception as e:
                logging.error(f"Error saving output files: {e}")
                print(f"Error saving output files: {e}")
            
            logging.info("Crawler session completed")
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
    logging.info("Web Crawler starting up...")
    print("Web Crawler Configuration\n")
    
    errors = validate_config()
    if errors:
        logging.error("Configuration validation failed")
        print("❌ Configuration errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        logging.info("Configuration validation passed")
        print("✓ Configuration valid\n")
        show_config()
        print("\n✅ Step 7: Logging System Implementation")
        
        crawler = WebCrawler()
        asyncio.run(crawler.crawl())
