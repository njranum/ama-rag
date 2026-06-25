import { expect, it } from "vitest";

import { type SseEvent, parseSseStream } from "./sse";

function streamFrom(chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  const bytes = chunks.map((c) => (typeof c === "string" ? enc.encode(c) : c));
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const b of bytes) controller.enqueue(b);
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<SseEvent[]> {
  const out: SseEvent[] = [];
  for await (const evt of parseSseStream(stream)) out.push(evt);
  return out;
}

it("routes named events sources -> delta -> done in order (obligation 2)", async () => {
  const evts = await collect(
    streamFrom([
      'event: sources\ndata: {"sources":[{"title":"A"}]}\n\n',
      'event: delta\ndata: {"text":"Hi "}\n\n',
      'event: delta\ndata: {"text":"there"}\n\n',
      "event: done\ndata: {}\n\n",
    ]),
  );
  expect(evts.map((e) => e.event)).toEqual(["sources", "delta", "delta", "done"]);
  expect(JSON.parse(evts[1].data).text).toBe("Hi ");
});

it("buffers an event split across read() chunks (obligation 1)", async () => {
  const evts = await collect(
    streamFrom([
      "event: delta\nda", // the data line is split mid-way...
      'ta: {"text":"abc"}\n', // ...and the \n\n delimiter is split too
      "\n",
    ]),
  );
  expect(evts).toHaveLength(1);
  expect(JSON.parse(evts[0].data).text).toBe("abc");
});

it("decodes a multibyte char split across chunks (obligation 3)", async () => {
  const full = new TextEncoder().encode('event: delta\ndata: {"text":"—"}\n\n'); // em dash = 3 bytes
  const cut = full.indexOf(0xe2) + 1; // split inside the em-dash byte sequence
  const evts = await collect(streamFrom([full.slice(0, cut), full.slice(cut)]));
  expect(JSON.parse(evts[0].data).text).toBe("—");
});

it("ignores ':' comment lines (obligation 4)", async () => {
  const evts = await collect(
    streamFrom([": ping\n\n", 'event: delta\ndata: {"text":"ok"}\n\n']),
  );
  expect(evts.map((e) => e.event)).toEqual(["delta"]);
});
