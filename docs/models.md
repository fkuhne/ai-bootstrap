# Suggested models

Any GGUF model on Hugging Face works. Set `LLM_HF_MODEL` in `.env` to its repository, followed by the quantization after a colon when the repository holds several. The server downloads the model on its first start, together with its image and audio component when it has one, and keeps both in a Docker volume.

These five are a starting point, from small to large. All are licensed Apache 2.0.

| `LLM_HF_MODEL` | Download | Inputs | Notes |
|---|---|---|---|
| `unsloth/Qwen3.5-2B-GGUF:Q4_K_M` | 2.0 GB | text, images, video | The smallest that answers well. For machines without a GPU. |
| `unsloth/Qwen3.5-4B-GGUF:Q4_K_M` | 3.4 GB | text, images, video | The default. The best quality for its size among these. |
| `google/gemma-4-E4B-it-qat-q4_0-gguf` | 6.1 GB | text, images, audio | Long conversations take little extra memory. |
| `unsloth/Qwen3.5-9B-GGUF:Q4_K_M` | 6.6 GB | text, images, video | The strongest of the five on most published benchmarks. |
| `google/gemma-4-12B-it-qat-q4_0-gguf` | 7.2 GB | text, images, audio | The largest. Strong at code and agent tasks, but leaves little room for long conversations on an 8 GB GPU. |

- **Download** is the model plus its image and audio component. The memory it needs is roughly that, plus the context, which grows with `LLM_CONTEXT_SIZE`.
- **Inputs** are what the model cards state. `docker compose run --rm llm-check` lists the inputs the server reports for the running model, and asks it in text, and with an image or a sound when it takes them.
- **Reasoning:** the Qwen3.5 models reason before they answer, by default. A request can turn that off with `"chat_template_kwargs": {"enable_thinking": false}`.
- **Quantization:** `Q4_K_M` and Google's `q4_0` keep about 4 bits per weight. A larger quantization, such as `Q8_0`, is more accurate and about twice the size.

The list reflects October 2026. Sources: the model cards ([Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B), [Gemma 4 E4B](https://huggingface.co/google/gemma-4-E4B-it)) and [an independent comparison of small models](https://pinggy.io/blog/small_llms_that_fit_in_8gb_memory/).
