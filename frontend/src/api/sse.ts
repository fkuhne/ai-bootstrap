// Server-sent events, read from a fetch response's body (docs/foundations.md#the-web-ui). The
// browser's EventSource only makes GET requests, and the stream endpoints take a POST, so the app
// reads the body itself.
//
// The format's rules, as far as the backend uses them: an event is a group of lines ended by a
// blank line; `event:` names it, `data:` lines hold its data; a line starting with `:` is a
// comment, such as a keep-alive ping; lines end with \n, \r\n or \r. The network can
// split a line, or a character, between chunks anywhere.

export interface ServerSentEvent {
  readonly event: string
  readonly data: string
}

export async function* readEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ServerSentEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let pending = '' // the start of a line whose end hasn't arrived yet
  let event = 'message'
  let data: string[] = []

  function* lines(text: string): Generator<ServerSentEvent> {
    for (const line of text.split(/\r\n|\r|\n/)) {
      if (line === '') {
        // A blank line ends the event; one with no data is dropped, as the format says.
        if (data.length > 0) {
          yield { event, data: data.join('\n') }
        }
        event = 'message'
        data = []
      } else if (!line.startsWith(':')) {
        const colon = line.indexOf(':')
        const field = colon < 0 ? line : line.slice(0, colon)
        const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'event') {
          event = value
        } else if (field === 'data') {
          data.push(value)
        }
      }
    }
  }

  try {
    for (;;) {
      const { value, done } = await reader.read()
      let text = pending + decoder.decode(value, { stream: !done })
      // A \r at the very end may be the first half of \r\n: wait for the next chunk.
      const heldReturn = !done && text.endsWith('\r')
      if (heldReturn) {
        text = text.slice(0, -1)
      }
      const end = Math.max(text.lastIndexOf('\n'), text.lastIndexOf('\r'))
      pending = text.slice(end + 1) + (heldReturn ? '\r' : '')
      if (end >= 0) {
        // The complete lines, without the ending of the last one.
        yield* lines(text.slice(0, end + 1).replace(/(\r\n|\r|\n)$/, ''))
      }
      if (done) {
        // What's left without a closing blank line is an unfinished event, dropped.
        return
      }
    }
  } finally {
    reader.releaseLock()
  }
}
