from bs4 import BeautifulSoup
import json
import requests
from fastapi import FastAPI
from crawler import crawl_site
from services.answering import AnswerConfig, answer_user_query
from services.chunking import ChunkingConfig, chunk_crawled_pages
from services.crawler.crawl_empower import crawl_all
from services.vector_store import ChromaStoreConfig, EmbeddingConfig, index_chunks, query_chunks
from core.env_config import envConfig
app = FastAPI()


def get_waters_article_links():
    # The API endpoint provided
    # api_url = "https://support.waters.com/@api/deki/pages/=Template%253AMindTouch%252FIDF3%252FViews%252FArticle_directory/contents?dream.out.format=json&origin=mt-web&pageid=48609&draft=false&guid=086abdff-0ca9-267d-515a-6718239639b1"
    api_url = "https://support.waters.com/@api/deki/pages/=Template%253AMindTouch%252FIDF3%252FViews%252FArticle_directory/contents?dream.out.format=json&origin=mt-web&pageid=48609&draft=false&guid=086abdff-0ca9-267d-515a-6718239639b1"
    try:
        # 1. Execute the GET request
        response = requests.get(api_url)
        response.raise_for_status()  # Raise exception for 4XX/5XX errors

        # 2. Parse the JSON response
        data = response.json()

        # 3. Extract the HTML string from the 'body' key
        html_body = data.get("body", "")
        if not html_body:
            print("No HTML content found in the response body.")
            return

        # 4. Parse the inner HTML content
        soup = BeautifulSoup(html_body, 'html.parser')

        # 5. Find all anchor tags and extract hrefs
        # We target links within the directory list for accuracy
        articles = []
        for link in soup.find_all('a', href=True):
            title = link.get_text(strip=True)
            url = link['href']
            articles.append({"title": title, "url": url})

        # Output the results
        print(f"Successfully extracted {len(articles)} links:\n")
        # for article in articles:
        #     print(f"Title: {article['title']}")
        #     print(f"Link:  {article['url']}")
        #     print("-" * 30)
        return articles
    except requests.exceptions.RequestException as e:
        print(f"Network error occurred: {e}")
    except json.JSONDecodeError:
        print("Failed to parse JSON response.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


@app.get("/crawl")
async def crawl(seed_url: str, max_pages: int = 40):
    from google import genai

    # The client gets the API key from the environment variable `GEMINI_API_KEY`.
    client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)

    # response = client.models.generate_content(
    #     model="gemini-3-flash-preview", contents="Explain how AI works in a few words"
    # )
    # print(response.text)
    links = get_waters_article_links()
    results = await crawl_all(links)
    chunks = chunk_crawled_pages(results)
    index_result = index_chunks(chunks, genai_client=client)

    # return await crawl_site(seed_url, max_pages)
    return {
        "pages_crawled": len(results),
        "chunks_created": len(chunks),
        "vector_store": index_result,
    }


@app.get("/crawl/chunks")
async def crawl_chunks(
    seed_url: str = "https://support.waters.com/@api/deki/pages/=Template%253AMindTouch%252FIDF3%252FViews%252FArticle_directory/contents?dream.out.format=json&origin=mt-web&pageid=48609&draft=false&guid=086abdff-0ca9-267d-515a-6718239639b1",
    max_pages: int = 40,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
):
    links = get_waters_article_links()
    results = await crawl_all(links)

    return chunk_crawled_pages(
        results[:20],  # limit to first 20 for chunking demo
        config=ChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
    )


@app.get("/crawl/index")
async def crawl_index(
    max_pages: int = 40,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    collection_name: str = "waters_articles",
):
    from google import genai

    client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)

    links = get_waters_article_links()
    results = await crawl_all(links)
    chunks = chunk_crawled_pages(
        results,
        config=ChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        ),
    )
    index_result = index_chunks(
        chunks[:100],  # limit to first 100 chunks for indexing demo
        genai_client=client,
        store_config=ChromaStoreConfig(collection_name=collection_name),
        embedding_config=EmbeddingConfig(),
    )

    return {
        "pages_crawled": len(results),
        "chunks_created": len(chunks),
        "vector_store": index_result,
    }


@app.get("/search")
async def search(
    query: str,
    collection_name: str = "waters_articles",
    n_results: int = 5,
):
    from google import genai

    client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)

    return query_chunks(
        query=query,
        genai_client=client,
        store_config=ChromaStoreConfig(collection_name=collection_name),
        n_results=n_results,
    )


@app.get("/answer")
async def answer(
    query: str,
    collection_name: str = "waters_articles",
    n_results: int = 5,
):
    from google import genai

    client = genai.Client(api_key=envConfig.GOOGLE_API_KEY)

    return answer_user_query(
        query=query,
        genai_client=client,
        store_config=ChromaStoreConfig(collection_name=collection_name),
        answer_config=AnswerConfig(n_results=n_results),
    )
