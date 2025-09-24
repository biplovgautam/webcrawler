
import re

CRAWL_DEPTH = 3
ALLOWED_DOMAIN = "example.com"
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
    if not ALLOWED_DOMAIN:
        errors.append("ALLOWED_DOMAIN cannot be empty")
    
    for pattern in BLOCK_PATTERNS:
        try:
            re.compile(pattern)
        except re.error:
            errors.append(f"Invalid regex: {pattern}")
    
    return errors

def show_config():
    print(f"Domain: {ALLOWED_DOMAIN}")
    print(f"Depth: {CRAWL_DEPTH}, Pages/seed: {PAGES_PER_SEED}, Max: {MAX_PAGES}")
    print(f"Delay: {REQUEST_DELAY}s, Timeout: {TIMEOUT}s, Retries: {MAX_RETRIES}")
    print(f"Blocked: {len(BLOCKED_PAGES_FULL)} URLs, {len(BLOCK_PATTERNS)} patterns")

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
        print("\n✅ Ready to crawl")
