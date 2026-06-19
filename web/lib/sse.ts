/**
 * Hand-rolled SSE parser over a `fetch()` response body (M3.1-02, L3 Decision 3).
 *
 * Native EventSource is GET-only and can't carry the POST body the /v1/ask contract requires, so
 * consumption routes through fetch + response.body. This parser honours the four obligations that
 * are the price of hand-rolling (L3 D3):
 *   1. Cross-chunk line buffering — a line/event can split across read() calls; buffer and split on
 *      the blank-line (`\n\n`) event delimiter, carrying the trailing partial forward.
 *   2. Named-event association — pair `event:` with its `data:` per block, resetting between blocks.
 *   3. Streaming UTF-8 decode — TextDecoder with `{stream: true}` so multibyte chars split across
 *      chunks don't become mojibake.
 *   4. Skip comment lines — a line starting with `:` is an SSE comment (the future `: ping`
 *      keepalive); ignore it.
 */

export interface SseEvent {
  event: string;
  data: string;
}

function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  let hasData = false;

  for (const raw of block.split("\n")) {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    if (line === "" || line.startsWith(":")) continue; // obligation 4: skip comments/blank
    if (line.startsWith("event:")) {
      event = line.slice(6).trim(); // obligation 2
    } else if (line.startsWith("data:")) {
      const value = line.slice(5);
      dataLines.push(value.startsWith(" ") ? value.slice(1) : value);
      hasData = true;
    }
  }
  return hasData ? { event, data: dataLines.join("\n") } : null;
}

export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }); // obligation 3

      let delimiter = buffer.indexOf("\n\n");
      while (delimiter !== -1) {
        // obligation 1: emit complete blocks, keep the trailing partial in `buffer`
        const block = buffer.slice(0, delimiter);
        buffer = buffer.slice(delimiter + 2);
        const evt = parseBlock(block);
        if (evt) yield evt;
        delimiter = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode(); // flush any pending multibyte
    const last = parseBlock(buffer);
    if (last) yield last;
  } finally {
    reader.releaseLock();
  }
}
