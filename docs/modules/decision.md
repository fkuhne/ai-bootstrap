# The decision module

A decision model answers typed questions about a text with probabilities, rather than with generated text. Use one where an app must choose a path:
- routing a message to a team, or an agent's request to a tool;
- classifying a document;
- telling whether a reply is a complaint.

It answers in milliseconds, and its probabilities can be compared with a threshold. Why it's built this way is in [the foundations](../foundations.md#the-decision-model).

## Try it

With the stack up (`docker compose up -d --wait`):

```
docker compose run --rm decision-demo
docker compose run --rm decision-demo "Your own text"
```

The demo asks three questions about a customer's message, or your text: is the customer angry, which team should handle it, how urgent it is. It prints each call, so you can copy them into any language. The API's own page, http://127.0.0.1:8000/api/docs, lets you try `POST /api/decide` in the browser.

**Its page,** Decide in the web UI's sidebar, opens with the same example. Edit the text and the questions in place, add or remove them, and the answers come back as bars, a percentage beside each, with the chosen option and the expected level in words. What the backend would refuse, such as two questions with one name, is said before anything is sent.

## The format

`POST /api/decide` takes the System One format, which llama.cpp's server, TypeSafe and OpenRouter share:

```json
{
  "state": "Customer: I was charged twice, and nobody replied.",
  "questions": {
    "angry": {"type": "noul", "instructions": "Is the customer angry?"},
    "team": {
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {"billing": "Payments and refunds", "shipping": null, "technical": null}
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this?",
      "criteria": ["can wait", "this week", "today", "right now"]
    }
  }
}
```

- **`state`:** text, or an object or array, which the model reads as JSON.
- **`files`, optional:** images as data URLs, for a model that takes them.
- **`questions`:** each under a name you choose.
  - `noul` is yes or no. Its `criteria` may describe what yes and no mean.
  - `choice` is one of its options. Each option has a description, or `null`.
  - `score` is a level on a scale of 2 to 10 levels, described lowest first.

Each question is answered on its own, under the same name:
- **`noul`:** the probability of yes.
- **`choice`:** the most likely option, each option's probability, and a confidence from 0, when every option is equally likely, to 1.
- **`score`:** the expected level, which can fall between two; each level's probability; a legend; and a confidence.

The probabilities aren't calibrated for your data. Measure the threshold your app needs on examples of its own.

## Models on this machine

The `decision` service runs llama.cpp's server with `DECISION_HF_MODEL`, on the LLM's CPU or GPU variant unless `DECISION_GPU` says otherwise. These are the native decision models ggml-org publishes:

| `DECISION_HF_MODEL` | Download | Licence | Notes |
|---|---|---|---|
| `ggml-org/Julia-1-GGUF:Q8_0` | 0.17 GB | Apache 2.0 | The fastest, about four times Laya's speed on CPU. It got a yes-or-no question wrong that Laya got right. |
| `ggml-org/Laya-GGUF:Q8_0` | 0.45 GB | Apache 2.0 | The default. Reads up to `DECISION_CONTEXT_SIZE` tokens at once. |
| `ggml-org/Kev-0.8B-GGUF:Q8_0` | 0.81 GB | Apache 2.0 | |
| `ggml-org/Kev-4B-GGUF:Q4_K_M` | 3.0 GB | Apache 2.0 | For a GPU. |
| `ggml-org/lev-GGUF:Q4_K_M` | 3.0 GB | Apache 2.0 | For a GPU. |
| `ggml-org/Kev-9B-GGUF:Q4_K_M` | 6.4 GB | Apache 2.0 | For a GPU. |
| `ggml-org/Clef-Flash-GGUF:Q4_K_M` | 6.5 GB, and 0.9 GB for images | Apache 2.0 | Takes images. For a GPU. |
| `ggml-org/Clef-GGUF:Q4_K_M` | 19 GB, and 0.9 GB for images | Apache 2.0 | Takes images. For a large GPU. |

OpenJev, 19 GB, is left out: its licence, CC BY-NC 4.0, forbids commercial use.

The service downloads the model on its first start and keeps it in its own volume. A text longer than `DECISION_CONTEXT_SIZE` is refused; a larger context takes more memory. With Laya on CPU, 8,192 tokens took 1.7 GB, against 0.4 GB idle.

## Models in the cloud

Set `DECISION_LOCAL_SERVER=0`, then:

| Provider | `DECISION_BASE_URL` | `DECISION_MODEL` | `DECISION_API_KEY` |
|---|---|---|---|
| [TypeSafe](https://docs.typesafe.ai/api) | `https://api.typesafe.ai/v1` | `jev-latest` | A TypeSafe key |
| [OpenRouter](https://openrouter.ai/docs/guides/community/jev) | `https://openrouter.ai/api/v1` | `typesafe/jev-1.13` | An OpenRouter key |

Both serve the same System One format at `/systemone`, which the backend adds. Neither has been called from this template yet: check your provider with the demo before relying on it.

## Turn it off, or remove it

- **Off:** `DECISION_ENABLED=0` removes the endpoint and the readiness check, and leaves the local server out, unless `DECISION_LOCAL_SERVER` says otherwise. Written `0` or `1`: Compose reads it as the server's count too.
- **Removed:** as [the recipe](README.md#remove-a-module) says. The model's volume, `decision-models`, stays until `docker compose down -v`.
