"""Web crawler using Playwright for async page fetching."""
import asyncio
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page

from models import ImageRef, PageData


async def get_tab_name(page: Page, url: str) -> str:
    """
    Detect the tab/section name from the page.

    Tries in order:
    1. Active tab in nav/tablist elements
    2. Page title from <title>
    3. Last segment of URL path
    """
    # Try to find active tab
    try:
        nav_item = await page.query_selector('[role="tab"][aria-selected="true"]')
        if nav_item:
            text = await nav_item.text_content()
            if text and text.strip():
                return text.strip()[:50]
    except Exception:
        pass

    # Try page title
    try:
        title = await page.title()
        if title:
            return title[:50]
    except Exception:
        pass

    # Fall back to URL path
    path = urlparse(url).path.strip("/")
    if path:
        return path.split("/")[-1][:50] or "Home"
    return "Home"


async def extract_images(page: Page, page_dir: Path) -> list[ImageRef]:
    """
    Extract all images from the page.

    Filters:
    - Skip if < 50×50px
    - Skip SVG, animated GIF, tracking pixels (1×1)
    - Only same-domain images
    """
    images = []
    img_elements = await page.query_selector_all("img")

    for idx, img_elem in enumerate(img_elements):
        try:
            src = await img_elem.get_attribute("src")
            alt = await img_elem.get_attribute("alt") or ""

            if not src:
                continue

            # Skip data URLs, tracking pixels
            if src.startswith("data:") or src.startswith("javascript:"):
                continue

            # Resolve URL
            full_url = urljoin(str(page.url), src)

            # Skip different domains
            if urlparse(full_url).netloc != urlparse(str(page.url)).netloc:
                continue

            # Get dimensions
            try:
                box = await img_elem.bounding_box()
                if not box or box["width"] < 50 or box["height"] < 50:
                    continue
            except Exception:
                pass

            # Download image
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(full_url, timeout=10)
                    if resp.status_code == 200:
                        img_path = page_dir / f"img_{idx}.png"
                        img_path.write_bytes(resp.content)
                        images.append(ImageRef(src=src, alt=alt,
                                      local_path=str(img_path)))
            except Exception:
                continue
        except Exception:
            continue

    return images


async def crawl_page(page: Page, url: str, temp_dir: Path) -> PageData | None:
    """Crawl a single page and extract its content."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # 1. Remove cookie popup
        try:
            await page.click("button:has-text('Accept')", timeout=3000)
        except:
            pass

        await page.evaluate("""
            const el = document.querySelector('#onetrust-consent-sdk');
            if (el) el.remove();
        """)

        # 2. Click tab
        article_tab = page.locator(
            'li[data-guid="086abdff-0ca9-267d-515a-6718239639b1"] a'
        )

        await article_tab.click(force=True)

        # 3. Wait for content
        await page.wait_for_selector(
            '[id="086abdff-0ca9-267d-515a-6718239639b1"]',
            timeout=15000
        )

        # 4. Extract
        panel = await page.query_selector(
            '[id="086abdff-0ca9-267d-515a-6718239639b1"]'
        )

        # Get tab name
        tab_name = await get_tab_name(page, url)

        # Extract body text
        body_text = await page.inner_text("body")
        if not body_text or len(body_text.strip()) < 50:
            return None

        # Create subdirectory for this page's images
        page_slug = urlparse(url).path.replace("/", "_") or "home"
        page_dir = temp_dir / page_slug
        page_dir.mkdir(exist_ok=True)

        # Extract images
        images = await extract_images(page, page_dir)

        return PageData(
            url=url,
            tab_name=tab_name,
            raw_text=body_text,
            images=images,
            crawled_at=datetime.now()
        )
    except Exception as e:
        print(f"Error crawling {url}: {e}")
        return None


def get_same_domain_links(html: str, base_url: str) -> set[str]:
    """Extract all same-domain links from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    links = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()

        # Skip anchors, mailto, pdf, images
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.endswith((".pdf", ".jpg", ".png", ".gif", ".zip")):
            continue

        full_url = urljoin(base_url, href)
        domain = urlparse(full_url).netloc

        if domain == base_domain:
            # Normalize URL (remove fragment)
            full_url = full_url.split("#")[0]
            links.add(full_url)

    return links


async def crawl_site(seed_url: str, max_pages: int = 40) -> list[PageData]:
    """
    Crawl a website using BFS from the seed URL.

    Uses asyncio with semaphore to limit concurrent page fetches to 5.
    """
    temp_dir = Path("./crawl_temp")
    temp_dir.mkdir(exist_ok=True)

    visited = set()
    queue = [seed_url]
    pages_data = []
    all_links = {}  # Track page -> links mapping

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        semaphore = asyncio.Semaphore(5)

        # async def fetch_with_semaphore(url: str) -> tuple[PageData | None, set[str]]:
        #     async with semaphore:
        #         page = await browser.new_page()
        #         result = await crawl_page(page, url, temp_dir)
        #         # ARTICLE_DIR_GUID = "086abdff-0ca9-267d-515a-6718239639b1"

        #         # # Check if the Article directory tab exists on this page
        #         # article_tab = page.locator(
        #         #     f'li[data-guid="{ARTICLE_DIR_GUID}"]')
        #         # tab_count = await article_tab.count()
        #         # print(
        #         #     f"[DEBUG] Article directory tab count: {tab_count} on {url}")

        #         # if tab_count > 0:
        #         #     print(f"[DEBUG] Article directory tab found")

        #         #     is_active = await article_tab.get_attribute("aria-selected")
        #         #     print(f"[DEBUG] Tab already active: {is_active}")

        #         #     if is_active != "true":
        #         #         # Only click if not already active
        #         #         tab_link = page.locator(
        #         #             f'li[data-guid="{ARTICLE_DIR_GUID}"] a.mt-guide-tab-link')
        #         #         await tab_link.click()
        #         #         print(f"[DEBUG] Clicked Article directory tab link")

        #         #     # Wait for the panel content to be visible using the same GUID
        #         #     await page.wait_for_selector(
        #         #         f'#{ARTICLE_DIR_GUID}',
        #         #         state="visible",
        #         #         timeout=10000
        #         #     )
        #         #     print(f"[DEBUG] Article directory panel is visible")
        #         # Extract links from the page
        #         page_content = await page.content()
        #         links = get_same_domain_links(page_content, url)
        #         await page.close()
        #         return result, links

        async def fetch_with_semaphore(url: str) -> tuple[PageData | None, set[str]]:
            async with semaphore:
                page = await browser.new_page()
                captured_requests = []

                # Intercept all requests to find the AJAX call for tab content
                page.on("request", lambda req: captured_requests.append(req.url))

                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                # JS click directly on the anchor inside the tab — bypasses all Playwright checks
                await page.evaluate("""
                    const tabLink = document.querySelector('li[data-guid="086abdff-0ca9-267d-515a-6718239639b1"] a');
                    if (tabLink) tabLink.click();
                """)
                print(f"[DEBUG] JS click fired")

                # Wait for AJAX to complete
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(2000)

                # Print all captured requests to find the AJAX endpoint
                print("[DEBUG] All requests captured:")
                for r in captured_requests:
                    print(f"  {r}")

                # Extract all links via JS — much more reliable than parsing page.content()
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]'))
                            .map(a => a.href)
                            .filter(href => href.startsWith('http'))
                """)
                print(f"[DEBUG] Total links found: {len(links)}")

                result = await crawl_page(page, url, temp_dir)
                await page.close()
                return result, set(links)

        tasks = []
        task_urls = []

        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            tasks.append(fetch_with_semaphore(url))
            task_urls.append(url)

            if len(tasks) >= 5 or len(queue) == 0:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for idx, result in enumerate(results):
                    if isinstance(result, tuple) and not isinstance(result, Exception):
                        page_data, links = result
                        if isinstance(page_data, PageData):
                            pages_data.append(page_data)
                            # Add new links to queue
                            print(
                                f"Links found on {task_urls[idx]}: {len(links)}")
                            for link in links:
                                if link not in visited and len(visited) < max_pages:
                                    queue.append(link)
                tasks = []
                task_urls = []

        await browser.close()

    return pages_data


async def crawl_page_tabs(page: Page, page_dir: Path) -> list[str]:
    all_text = ""
    all_images = []

    tabs = await page.query_selector_all('[role="tab"]')

    if tabs:
        for tab in tabs:
            try:
                await tab.click()
                await page.wait_for_timeout(1000)  # allow content to load

                body_text = await page.inner_text("body")
                if body_text:
                    all_text += "\n\n" + body_text

                # extract images per tab
                images = await extract_images(page, page_dir)
                all_images.extend(images)

            except Exception:
                continue
    else:
        # fallback (no tabs)
        all_text = await page.inner_text("body")
        all_images = await extract_images(page, page_dir)
