// Test doubles for streamed responses: a body sent in the given chunks, as the network splits it,
// that can stay open until the request is aborted.

const encoder = new TextEncoder()

export function body(
  chunks: readonly (string | Uint8Array)[],
  options: { signal?: AbortSignal | null; stayOpen?: boolean } = {},
): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(
          typeof chunk === 'string' ? encoder.encode(chunk) : chunk,
        )
      }
      if (!options.stayOpen) {
        controller.close()
        return
      }
      // Open until aborted, as a real fetch is while the model is still writing.
      options.signal?.addEventListener('abort', () => {
        controller.error(
          new DOMException('The operation was aborted.', 'AbortError'),
        )
      })
    },
  })
}

// One event in the format's text form.
export function event(name: string, data: unknown): string {
  return `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`
}

// A body the test writes to as it goes, to check the page between events. Aborting the request
// ends it, as a real fetch does.
export function controlledBody(signal?: AbortSignal | null) {
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined
  const stream = new ReadableStream<Uint8Array>({
    start(started) {
      controller = started
      signal?.addEventListener('abort', () => {
        started.error(
          new DOMException('The operation was aborted.', 'AbortError'),
        )
      })
    },
  })
  return {
    stream,
    send: (text: string) => controller?.enqueue(encoder.encode(text)),
    close: () => controller?.close(),
  }
}
