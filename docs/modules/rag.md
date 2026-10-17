# The RAG module

RAG, retrieval-augmented generation, lets the model answer from your app's own text: its documents, split into chunks, are searched for each question, and the best ones go into the prompt. Your app creates the chunks, from its own documents and in its own way; the module embeds them, keeps them in Qdrant, and searches them two ways, by meaning and by exact words. Why it's built this way is in [the foundations](../foundations.md#rag).

An app stores its chunks; a question searches them, and is answered from them, citing them. The web UI's Documents page asks them questions, and shows each answer's sources.

## Try it

With the stack up (`docker compose up -d --wait`):
- `http://127.0.0.1:8000/api/health/ready` shows `"rag": "ok"` once Qdrant and the embedding model both answer.
- Qdrant's dashboard, at http://127.0.0.1:6333/dashboard, shows its collections.
- The samples, a fictional shop's help centre, twelve chunks of five documents under `samples/`, give the Documents page something to answer from. This stores them, replacing any stored before, keeps them, and checks that each of ten questions finds its chunk among the first three, printing its rank; `--delete` deletes them:

  ```
  docker compose run --rm rag-samples
  ```
- The Documents page, http://127.0.0.1:3000/documents, answers from what's stored. Under each answer are its sources, numbered, with their documents and similarities, the ones it cites marked; open one to read its text. The sidebar lists the stored documents, and each one's number of chunks.
- The demo stores three chunks of two documents, lists them, stores one again, changed; searches them for an exact code and for a question in other words; streams an answer citing them; and deletes them, printing each call so you can copy it into any language:

  ```
  docker compose run --rm rag-demo
  ```
- The module's live tests embed a few texts, and store, list and delete chunks in a collection of their own:

  ```
  docker compose run --rm backend-checks pytest -m integration --no-cov -k rag_live
  ```

## Produce your chunks

Your app cuts its documents into chunks, in its own way, since it knows them: a help page's sections, a contract's clauses, a ticket's messages.
- **Along the documents' structure,** 100 to 500 words a chunk. A chunk is found and cited whole: too short, it lacks what makes it relevant; too long, it mixes subjects and fills the model's context.
- **Its heading as its `title`,** embedded with the text, and **its file as its `source`,** which answers cite.
- **A stable `id`,** such as `returns.md#3`, so storing the document again replaces its chunks.
- **A document's new version:** delete its source, then store it.

This example, standard library only, cuts each Markdown file in a folder at its headings, and a section longer than 400 words between its paragraphs, then stores each file's chunks in place of its old ones. Save it as `store_docs.py`, and run `python store_docs.py <folder>` with the stack up:

```python
"""Cut a folder's Markdown files at their headings, and store each as a document's chunks."""

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000"
HEADING = re.compile(r"^#{1,6}\s+(.+)$")
WORDS = 400  # the most words in a chunk, about 550 tokens


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BACKEND_URL + path, data, {"Content-Type": "application/json"}, method=method
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def sections(text):
    """Each heading's title and the text under it, up to the next heading."""
    title, lines = None, []
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            yield title, "\n".join(lines).strip()
            title, lines = heading.group(1).strip(), []
        else:
            lines.append(line)
    yield title, "\n".join(lines).strip()


def pieces(text):
    """The text, cut between paragraphs where it's longer than WORDS."""
    piece = []
    for paragraph in text.split("\n\n"):
        if piece and len(" ".join([*piece, paragraph]).split()) > WORDS:
            yield "\n\n".join(piece)
            piece = []
        piece.append(paragraph)
    if piece:
        yield "\n\n".join(piece)


def store(path, folder):
    source = path.relative_to(folder).as_posix()
    cut = [
        (title, piece)
        for title, text in sections(path.read_text(encoding="utf-8"))
        if text
        for piece in pieces(text)
    ]
    chunks = [
        {"id": f"{source}#{number}", "source": source, "title": title, "text": text}
        for number, (title, text) in enumerate(cut, start=1)
    ]
    # A new version replaces the old: its chunks are deleted first.
    call("DELETE", "/api/rag/sources/" + urllib.parse.quote(source))
    print(source, call("PUT", "/api/rag/chunks", {"chunks": chunks}))


folder = Path(sys.argv[1])
for path in sorted(folder.rglob("*.md")):
    store(path, folder)
```

On CPU, it stored this template's four module pages, 23 chunks, in 16 seconds. It's a sketch: a `#` line inside a code block reads as a heading, and a file's chunks go in one request, so at most 1,000. Other formats, such as PDF, need their text extracted first.

## Store your chunks

Each chunk is:

| Field | | What it is |
|---|---|---|
| `id` | required | Your own id for the chunk. Storing it again replaces it. |
| `source` | required | The document it came from: answers will cite it, and a document's chunks are deleted together. It may hold slashes, such as `help/returns.md`. |
| `text` | required | What's embedded and searched. At most `RAG_CONTEXT_SIZE` tokens, 1,024 by default; a longer one is refused with the reason. |
| `title` | optional | A title, such as its section's: embedded and searched with the text. |
| `metadata` | optional | Any JSON object, such as a page number, kept and returned as given. |

Store them with `PUT /api/rag/chunks`, up to 1,000 in a request:

```json
{
  "chunks": [
    {
      "id": "returns-1",
      "source": "help/returns.md",
      "title": "Returns",
      "text": "Items can be returned within 30 days, unused.",
      "metadata": {"page": 1}
    }
  ]
}
```

It answers `{"stored": 1}` once each chunk is embedded and kept. On CPU, with the default model, chunks of about 100 words took 0.2 s each: 3,000 took ten minutes, and the embedding service stayed under 0.75 GB. A GPU is much faster.

- **What's stored:** `GET /api/rag/sources` lists each source and its number of chunks.
- **A document's new version:** `DELETE /api/rag/sources/help/returns.md` removes its chunks, and says how many; then store the new ones. Storing alone would leave a chunk the new version no longer has.

The first store makes the collection, `RAG_COLLECTION` (`chunks`), for the embedding model. A chunk's vector depends on the model, so once you change the model, a store answers 409: delete the collection, from Qdrant's dashboard or with `curl -X DELETE http://127.0.0.1:6333/collections/chunks`, or set another `RAG_COLLECTION`, then store your chunks again.

**Words, for BM25:** Qdrant weighs each chunk's words as for English, with an average length of 256 words. For chunks in another language, set `RAG_BM25_LANGUAGE`, such as `portuguese`, for its stop words and stems; for chunks much shorter or longer, set `RAG_BM25_AVG_LEN` to their average length in words. Set both before the first store: they weigh the chunks as they're stored.

## Search

`POST /api/rag/search` finds the chunks that best match a query, best first:

```json
{"query": "How long do refunds take?", "limit": 5, "mode": "hybrid", "sources": ["help/returns.md"]}
```

- **`mode`:** `hybrid`, the default, by meaning and by words, fused by rank; `dense`, by meaning alone; `words`, by BM25 alone. Compare them on your own questions to see what each half finds: an exact code, such as an error number, by its words; a question in other words than the text's, by its meaning.
- **`limit`:** 5 by default, up to 50. **`sources`:** only those documents' chunks.

Each hit is its chunk, its `score` in that mode, comparable within one search only, and its `similarity` to the query, from -1 to 1, the same whatever the mode.

## Answers

`POST /api/rag/ask` takes what chat takes, the conversation and any parameters, with `limit` and `sources`:

```json
{"messages": [{"role": "user", "content": "How long do refunds take?"}], "limit": 5}
```

It searches with the last message, gives the model the best chunks, numbered, each with its title and source, and asks it to answer from them alone and cite them as `[1]`. It answers the sources and the model's answer together; `/api/rag/ask/stream` sends a `sources` event first, then the model's `reasoning` and `token` events, then `done`. The prompt is in `backend/app/modules/rag/answers.py`: adapt it to your documents.

The `[1]` are the model's own writing, and a model may cite badly: the Documents page shows the sources under each answer, so a reader can check.

**When the documents don't say:** with no chunk found, the answer is "The documents don't say.", `refused` is true, and the model isn't asked. `RAG_MIN_SIMILARITY` does the same for a question whose closest chunk is less similar than it: off by default, since the right value depends on your documents and the embedding model. Look at the similarities `/api/rag/search` gives for questions your documents answer, and for questions they don't, and set it between.

Two limits to know:
- **The search uses the last message alone,** not rewritten from the conversation: a follow-up such as "and the second one?" finds little. Rewrite such questions in your app before asking.
- **The sources take room in the model's context:** five chunks of up to 1,024 tokens each, beside the conversation, within `LLM_CONTEXT_SIZE`.

## Models on this machine

The `embedding` service runs llama.cpp's server with `RAG_HF_MODEL`, on the LLM's CPU or GPU variant unless `RAG_GPU` says otherwise. Each model wants its questions and chunks written its own way, which `RAG_QUERY_FORMAT` and `RAG_DOCUMENT_FORMAT` set, with `{text}` standing for the text.

| `RAG_HF_MODEL` | Download | Licence | Languages | `RAG_QUERY_FORMAT` | `RAG_DOCUMENT_FORMAT` |
|---|---|---|---|---|---|
| `ggml-org/embeddinggemma-2-GGUF:Q8_0`, the default | 0.31 GB | Apache 2.0 | more than 100, and code | `task: search result \| query: {text}` | `title: none \| text: {text}` |
| `ggml-org/bge-m3-Q8_0-GGUF:Q8_0` | 0.64 GB | MIT | more than 100 | `{text}` | `{text}` |
| `Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0` | 0.64 GB | Apache 2.0 | more than 100, and code | `Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:{text}` | `{text}` |
| `ggml-org/bge-small-en-v1.5-Q8_0-GGUF:Q8_0` | 0.04 GB | MIT | English | `Represent this sentence for searching relevant passages: {text}` | `{text}` |

EmbeddingGemma 2 and bge-m3 were run on the template's llama.cpp; the other two weren't. In `.env`, put a format in double quotes; `\n` there is a new line. bge-small reads at most 512 tokens: set `RAG_CONTEXT_SIZE=512` with it.

**The batch, `RAG_CONTEXT_SIZE`:** an embedding model reads each text in one batch, so this is the longest chunk it takes, 1,024 tokens by default. A longer one is refused, with the reason. It also bounds the memory, which grows by about 1 MB per token in the batch on CPU: about 1.5 GB at 1,024, however many chunks a request carries. Raise it only as far as your chunks need.

The service downloads the model on its first start and keeps it in its own volume. The chunks' vectors depend on the model, so after changing it, store the chunks again.

## Elsewhere

**Embeddings:** any provider with an OpenAI-compatible `/v1/embeddings`. Set `RAG_LOCAL_EMBEDDING=0`, the format of the provider's model, then:

| Provider | `RAG_EMBEDDING_BASE_URL` | `RAG_EMBEDDING_MODEL` | Formats |
|---|---|---|---|
| [OpenAI](https://platform.openai.com/docs/guides/embeddings) | `https://api.openai.com/v1` | `text-embedding-3-small` | `{text}` |
| [Google Gemini](https://ai.google.dev/gemini-api/docs/openai#embeddings) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-embedding-001` | `{text}` |

with the provider's key in `RAG_EMBEDDING_API_KEY`. Neither has been called from this template yet: check yours with the live tests before relying on it.

**Qdrant:** set `RAG_LOCAL_QDRANT=0`, `RAG_QDRANT_URL`, and its key in `RAG_QDRANT_API_KEY`, as for Qdrant Cloud.

## Turn it off, or remove it

- **Off:** `RAG_ENABLED=0` removes the endpoints and the readiness check, and leaves Qdrant and the embedding server out, unless `RAG_LOCAL_QDRANT` or `RAG_LOCAL_EMBEDDING` says otherwise. Written `0` or `1`: Compose reads it as their count too.
- **Removed:** as [the recipe](README.md#remove-a-module) says. Qdrant's volume, `qdrant-data`, and the embedding model's, `embedding-models`, stay until `docker compose down -v`.
