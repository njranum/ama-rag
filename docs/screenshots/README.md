# Screenshots & demo assets

Drop the images referenced by the root `README.md` here, under these exact filenames. Capture them
from the running widget (`cd web && npm run dev`, with the backend up on port 8000).

| File | What to capture |
|------|-----------------|
| `hero_answer.png` | **Hero shot.** The widget mid- or post-answer: a real question, the streamed answer, and source cards below. ~900px wide. This is the first image a visitor sees. |
| `demo.gif` | **Demo loop (<10s).** One full cycle: type a question → watch it stream token by token → source cards appear → then ask an off-topic question that trips the relevance gate and gets a polite decline. |
| `widget_idle.png` | The idle widget — empty ask box with the suggested-question chips. |
| `widget_streaming.png` | An answer streaming in, part-way through (shows the token-by-token render). |
| `widget_sources.png` | The source cards from the `sources` event — grouped by page, preview + “read more →”. |
| `widget_decline.png` | An off-topic question declined by the relevance gate — note there are **no** source cards. |

Tips:
- Keep the browser window narrow so the widget fills the frame (it's an inline panel, not full-page).
- For the GIF, [Kap](https://getkap.co/) or macOS `⇧⌘5` → convert to GIF works well; aim for ≤ 900px wide so it renders cleanly on GitHub.
- Once the public portfolio content pages exist and `url`s are populated, re-shoot `widget_sources.png` so the “read more →” links are live.
