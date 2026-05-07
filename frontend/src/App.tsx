import { FormEvent, Fragment, useMemo, useState } from "react";
import {
  BookOpen,
  ExternalLink,
  Image as ImageIcon,
  Link2,
  Loader2,
  Search,
} from "lucide-react";

type Citation = {
  citation_id: number;
  title: string;
  source: string;
  chunk_index: number;
  distance?: number | null;
};

type RetrievedChunk = {
  citation_id: number;
  id: string;
  content: string;
  metadata?: {
    title?: string;
    source?: string;
    link?: string;
    images?: string;
    chunk_index?: number;
  };
  distance?: number | null;
};

type AnswerResponse = {
  answer: string;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const exampleQueries = [
  "What audit trails are available in Empower?",
  "How can I view method audit trail differences?",
  "Where do sample set changes appear?",
];

export function App() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const citationById = useMemo(() => {
    const map = new Map<number, Citation>();
    result?.citations.forEach((citation) =>
      map.set(citation.citation_id, citation),
    );
    return map;
  }, [result]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedQuery = query.trim();
    if (!trimmedQuery || loading) return;

    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        query: trimmedQuery,
        n_results: "5",
      });
      const response = await fetch(`${API_BASE_URL}/answer?${params}`);
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const data = (await response.json()) as AnswerResponse;
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while querying the backend.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="query-panel">
        <div className="brand-row">
          <BookOpen size={24} aria-hidden="true" />
          <div>
            <h1>Waters Article Assistant</h1>
            <p>Ask indexed support articles and inspect the exact citations.</p>
          </div>
        </div>

        <form className="query-form" onSubmit={handleSubmit}>
          <label htmlFor="query">Query</label>
          <div className="query-input-row">
            <textarea
              id="query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ask about Empower audit trails, methods, samples..."
              rows={4}
            />
            <button type="submit" disabled={loading || !query.trim()}>
              {loading ? (
                <Loader2 className="spin" size={18} aria-hidden="true" />
              ) : (
                <Search size={18} aria-hidden="true" />
              )}
              <span>{loading ? "Searching" : "Ask"}</span>
            </button>
          </div>
        </form>

        <div className="examples" aria-label="Example queries">
          {exampleQueries.map((item) => (
            <button key={item} type="button" onClick={() => setQuery(item)}>
              {item}
            </button>
          ))}
        </div>

        {error && <p className="error-message">{error}</p>}
      </section>

      <section className="results-layout">
        <article className="answer-panel">
          <div className="panel-heading">
            <h2>Answer</h2>
            {result && (
              <span>{result.citations.length} citation sources</span>
            )}
          </div>
          {result ? (
            <AnswerText
              answer={result.answer}
              citationById={citationById}
            />
          ) : (
            <div className="empty-state">
              <Search size={28} aria-hidden="true" />
              <p>Your grounded response will appear here.</p>
            </div>
          )}
        </article>

        <aside className="citation-panel">
          <h2>Citations</h2>
          {result?.citations.length ? (
            <div className="citation-list">
              {result.citations.map((citation) => (
                <CitationCard citation={citation} key={citation.citation_id} />
              ))}
            </div>
          ) : (
            <p className="muted">No citations yet.</p>
          )}
        </aside>
      </section>

      {result?.retrieved_chunks.length ? (
        <section className="chunk-section">
          <div className="panel-heading">
            <h2>Retrieved Chunks</h2>
            <span>{result.retrieved_chunks.length} chunks used</span>
          </div>
          <div className="chunk-grid">
            {result.retrieved_chunks.map((chunk) => (
              <ChunkCard chunk={chunk} key={chunk.id} />
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function AnswerText({
  answer,
  citationById,
}: {
  answer: string;
  citationById: Map<number, Citation>;
}) {
  return (
    <div className="answer-text">
      {answer.split(/\n{2,}/).map((block, index) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        if (trimmed.startsWith("###")) {
          return (
            <h3 key={index}>
              {renderInlineText(trimmed.replace(/^#+\s*/, ""), citationById)}
            </h3>
          );
        }

        if (/^(\*|-)\s+/m.test(trimmed)) {
          return (
            <ul key={index}>
              {trimmed.split("\n").map((line) => (
                <li key={line}>
                  {renderInlineText(line.replace(/^(\*|-)\s+/, ""), citationById)}
                </li>
              ))}
            </ul>
          );
        }

        return <p key={index}>{renderInlineText(trimmed, citationById)}</p>;
      })}
    </div>
  );
}

function renderInlineText(text: string, citationById: Map<number, Citation>) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+\])/g);
  return parts.map((part, index) => {
    const citationMatch = part.match(/^\[(\d+)\]$/);
    if (citationMatch) {
      const id = Number(citationMatch[1]);
      const citation = citationById.get(id);
      return (
        <a
          className="inline-citation"
          href={citation?.source || undefined}
          target="_blank"
          rel="noreferrer"
          title={citation?.title || `Citation ${id}`}
          key={`${part}-${index}`}
        >
          {part}
        </a>
      );
    }

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>;
    }

    return <Fragment key={`${part}-${index}`}>{part}</Fragment>;
  });
}

function CitationCard({ citation }: { citation: Citation }) {
  return (
    <a
      className="citation-card"
      href={citation.source}
      target="_blank"
      rel="noreferrer"
    >
      <span className="citation-id">[{citation.citation_id}]</span>
      <span className="citation-title">{citation.title}</span>
      <span className="citation-meta">
        Chunk {citation.chunk_index}
        {typeof citation.distance === "number"
          ? ` · distance ${citation.distance.toFixed(3)}`
          : ""}
      </span>
      <ExternalLink size={16} aria-hidden="true" />
    </a>
  );
}

function ChunkCard({ chunk }: { chunk: RetrievedChunk }) {
  const metadata = chunk.metadata || {};
  const images = parseImages(metadata.images);
  const source = metadata.source || metadata.link || "";

  return (
    <article className="chunk-card">
      <div className="chunk-title-row">
        <span className="citation-id">[{chunk.citation_id}]</span>
        <h3>{metadata.title || "Untitled source"}</h3>
      </div>
      <p>{truncate(chunk.content, 520)}</p>

      {images.length ? (
        <div className="image-strip">
          {images.slice(0, 4).map((src) => (
            <a href={src} target="_blank" rel="noreferrer" key={src}>
              <img src={src} alt="" loading="lazy" />
            </a>
          ))}
        </div>
      ) : (
        <div className="no-images">
          <ImageIcon size={16} aria-hidden="true" />
          <span>No images in this chunk</span>
        </div>
      )}

      {source && (
        <a className="source-link" href={source} target="_blank" rel="noreferrer">
          <Link2 size={16} aria-hidden="true" />
          Open source article
        </a>
      )}
    </article>
  );
}

function parseImages(value?: string) {
  if (!value) return [];
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function truncate(value: string, maxLength: number) {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength).trim()}...`;
}
