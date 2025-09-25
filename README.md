# Smart Web Crawler

A high-performance, ethical web crawler that systematically crawls websites with configurable settings and comprehensive logging.

## Features

- **Domain-Restricted Crawling** - Crawl within specified domains or cross-domain
- **Smart Content Processing** - Convert HTML to clean Markdown format
- **Ethical Crawling** - Respects robots.txt and implements polite delays
- **Comprehensive Logging** - Detailed logs with timestamps and progress tracking
- **Error Resilience** - Retry logic and graceful error handling
- **Async Performance** - High-speed asynchronous crawling
- **Cross-Platform** - Works on Windows, Linux, and Mac

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add URLs to Crawl**
   ```bash
   echo "https://example.com" > seeds.txt
   ```

3. **Run Crawler**
   ```bash
   python crawler.py
   ```

## Project Structure

```
/scraper/
├── seeds.txt          # URLs to crawl
├── crawler.py         # Main crawler script
├── crawlLog.txt       # Detailed logging output
└── output/
    ├── MDs/           # Markdown files for each page
    ├── index.jsonl    # JSON index of all crawled pages
    └── failed_urls.txt # URLs that failed to crawl
```

## Configuration

Edit variables at the top of `crawler.py`:

```python
CRAWL_DEPTH = 1              # How many levels deep to crawl (depth start from 0 as seed only)
ALLOWED_DOMAIN = ""          # Domain restriction (empty = any domain)
PAGES_PER_SEED = 50          # Max pages per seed URL
MAX_PAGES = 200              # Total max pages across entire crawl

BLOCKED_PAGES_FULL = {       # Complete URLs to block
    "https://example.com/admin"
}

BLOCK_PATTERNS = [           # Regex patterns to block
    r".*\.(pdf|jpg|jpeg|png|gif)$",
    r".*/admin/.*"
]
```

## Usage Examples

### Basic Domain Crawling
```python
# crawler.py configuration
CRAWL_DEPTH = 2
ALLOWED_DOMAIN = "example.com"
PAGES_PER_SEED = 25
```

### Cross-Domain Crawling
```python
# crawler.py configuration  
CRAWL_DEPTH = 1
ALLOWED_DOMAIN = ""  # Empty = crawl any domain
PAGES_PER_SEED = 10
```

### Add URLs to seeds.txt
```text
https://jeevee.com/
http://kiec.edu.np/
https://prettyclickcosmetics.com/
```

## Output Files

### Markdown Files (`output/MDs/`)
- Clean, readable content for each crawled page
- Descriptive filenames based on URLs
- Page titles and structured content

### JSON Index (`output/index.jsonl`)
```json
{"url": "https://example.com", "title": "Example", "file_path": "MDs/example_com.md", "domain": "example.com", "word_count": 150, "timestamp": "2025-09-25T10:30:15"}
```

### Failed URLs (`output/failed_urls.txt`)
```text
https://broken-site.com/ - HTTP 404
https://timeout-site.com/ - Timeout after 3 retries
```

### Crawl Logs (`crawlLog.txt`)
```text
2025-09-25 10:30:15,123 - INFO - Crawling page 1: https://example.com/
2025-09-25 10:30:15,456 - INFO - Successfully fetched https://example.com/ (1500 chars)
2025-09-25 10:30:15,789 - INFO - Found 12 links on https://example.com/
```

## How It Works

1. **Load Seeds** - Reads URLs from `seeds.txt`
2. **URL Processing** - Validates, normalizes, and filters URLs
3. **Content Extraction** - Fetches HTML and converts to Markdown
4. **Link Discovery** - Finds new URLs to crawl (within depth limits)
5. **File Generation** - Saves Markdown files and JSON index
6. **Error Handling** - Retries failed requests, logs errors
7. **Completion** - Generates summary statistics

## Key Features Explained

### Domain Restrictions
- Set `ALLOWED_DOMAIN = "example.com"` to crawl only example.com
- Leave `ALLOWED_DOMAIN = ""` for cross-domain crawling
- Automatically rejects external links when domain is set

### Smart URL Filtering
- **Full URL Blocking**: Add complete URLs to `BLOCKED_PAGES_FULL`
- **Pattern Blocking**: Use regex in `BLOCK_PATTERNS` for flexible filtering
- **Duplicate Detection**: Automatically avoids crawling the same URL twice

### Ethical Crawling
- **Robots.txt Respect**: Automatically checks and follows robots.txt rules
- **Polite Delays**: 1-second delay between requests by default
- **User-Agent Rotation**: Uses realistic browser user agents
- **Rate Limiting**: Domain-specific delays to avoid overwhelming servers

### Error Resilience
- **Retry Logic**: 3 retry attempts for failed requests
- **Timeout Handling**: 30-second timeout per request
- **Graceful Degradation**: Continues crawling even if some URLs fail
- **Comprehensive Logging**: All errors logged with timestamps and details

## Troubleshooting

### Common Issues

**No URLs in seeds.txt**
```bash
echo "https://example.com" > seeds.txt
```

**Permission Denied**
```bash
# Windows
python crawler.py

# Linux/Mac  
sudo python crawler.py
```

**JavaScript Sites Not Working**
```bash
pip install playwright
playwright install chromium
```

**SSL Certificate Errors**
- Some sites have invalid certificates (normal)
- Check `failed_urls.txt` for details
- Crawler continues with other URLs

### Performance Tuning

**Faster Crawling** (Less Polite)
```python
REQUEST_DELAY = 0.5  # Reduce delay
MAX_RETRIES = 1      # Fewer retries
```

**More Thorough Crawling**
```python
CRAWL_DEPTH = 3      # Go deeper
TIMEOUT = 60         # Longer timeout
MAX_RETRIES = 5      # More retries
```

## Technical Details

- **Async Architecture**: Uses asyncio and aiohttp for high performance
- **Memory Efficient**: Processes one page at a time
- **Cross-Platform**: Pure Python, works everywhere
- **Modular Design**: Easy to modify and extend
- **Standards Compliant**: Follows web crawling best practices



## Files Description
```
├── seeds.txt          # Priority URLs to crawl
├── crawler.py         # Main crawler script
├── crawlLog.txt       # Detailed logging output
└── output/
    ├── MDs/          # Markdown files for each page
    │   └── Home.md   # Example crawled page
    ├── index.jsonl    # JSON index of all crawled pages
    └── failed_urls.txt # URLs that failed to crawl
```
- **seeds.txt**: This file contains the priority URLs that the crawler will use as starting points for crawling. You can add or modify URLs as needed.

- **crawler.py**: This is the main script for the web crawler. It contains the logic for crawling the web pages, extracting content, and saving the output.

- **crawlLog.txt**: This file stores detailed logging output from the crawler, including information about the crawling process and any errors encountered. It is useful for debugging and monitoring the crawler's performance.

- **output/**: This directory holds all the output generated by the crawler.

  - **MDs/**: This subdirectory contains Markdown files for each crawled page. Each file represents the content extracted from a specific page.

  - **Home.md**: This file serves as an example of a crawled page in Markdown format.

  - **index.jsonl**: This file is a JSON Lines file that serves as an index of all crawled pages, providing a structured format for easy access to the crawled data.

  - **failed_urls.txt**: This file lists URLs that failed to crawl, allowing you to review and troubleshoot any issues with specific links.

## License

MIT License - Feel free to use and modify.