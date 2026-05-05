import asyncio
from playwright.async_api import async_playwright


async def extract_page_data(page, url, title):
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)

    # Remove cookie popup (important for this site)
    await page.evaluate("""
        const el = document.querySelector('#onetrust-consent-sdk');
        if (el) el.remove();
    """)

    # Wait for main content (adjust if needed)
    await page.wait_for_selector("main, article, .mt-content-container", timeout=15000)

    # Title
    # title = await page.title()

    # Extract visible text
    text = await page.evaluate("""
        () => {
            const el = document.querySelector("main, article, .mt-content-container");
            return el ? el.innerText : document.body.innerText;
        }
    """)

    # Extract images
    images = await page.eval_on_selector_all(
        "img",
        "imgs => imgs.map(img => img.src).filter(src => src)"
    )

    return {
        "link": url,
        "title": title,
        "text": text.strip(),
        "images": list(set(images))  # remove duplicates
    }


async def crawl_all(articles):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        semaphore = asyncio.Semaphore(5)  # limit concurrency

        async def worker(url, title):
            async with semaphore:
                page = await browser.new_page()
                try:
                    data = await extract_page_data(page, url, title)
                    results.append(data)
                    print(f"✔ Crawled: {url}")
                except Exception as e:
                    print(f"❌ Failed: {url}, error: {e}")
                finally:
                    await page.close()

        await asyncio.gather(*[worker(article['url'], article['title']) for article in articles])

        await browser.close()

    return results
