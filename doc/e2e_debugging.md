# Browser-driven E2E debugging

How to debug "I clicked the thing and nothing happened" bugs by driving the
real UI in a real browser and watching everything it emits. This is the method
that found the silent browse-upload bug, where `curl` and the backend logs were
all green but the **browser** dropped the file before it ever hit the network.

## When to reach for this

Use it when a failure lives in the browser, not the server:

- The backend works under `curl` but the UI "does nothing".
- A click/drag/select produces **no network request** and **no console error**.
- You suspect event-handler wiring, live DOM objects (e.g. `FileList`), the
  Vite `/api` proxy, or CORS — anything that only manifests in a real DOM.

If the backend itself errors, plain `curl` against the API is faster — start
there. This harness is for the gap between "API is fine" and "UI is broken".

## The tool

[`frontend/e2e/upload-smoke.mjs`](../frontend/e2e/upload-smoke.mjs) drives
headless Chrome through the exact **click-to-browse → pick a PDF** flow and
streams the four signals that matter:

| Signal | Playwright event | Catches |
|---|---|---|
| Console logs | `page.on('console')` | the `[documents] …` app logs (or their absence) |
| Page errors | `page.on('pageerror')` | uncaught exceptions crashing a handler/render |
| Failed requests | `page.on('requestfailed')` | `ECONNREFUSED` (server down), proxy misroutes |
| API responses | `page.on('response')` | every `/api/*` call + status — proves it reached the backend |

It exits `0` only if a `POST /api/documents/upload` returns 2xx, so it doubles
as a CI-able smoke test.

### Run it

```bash
cd frontend
# Dev server + backend must be running first (npm run dev; uvicorn).
npm run e2e:upload                      # self-contained: generates a sample PDF
node e2e/upload-smoke.mjs my.pdf        # use a specific PDF
HEADED=1 npm run e2e:upload             # watch the browser do it
BASE_URL=http://localhost:5174 npm run e2e:upload
```

No browser download is needed — it uses your installed Chrome via
Playwright's `channel: 'chrome'`. Only `playwright-core` (a devDependency) is
required.

## The method (reusable for any UI flow)

1. **Confirm the backend in isolation first.** `curl` the endpoint (and the
   Vite proxy at `:5173/api/...`). If that's green, the bug is in the browser.
2. **Drive the *exact* user action.** Don't shortcut with `setInputFiles` —
   it can behave differently from a real file chooser. Use the genuine path:
   `waitForEvent('filechooser')` + click + `chooser.setFiles(...)`.
3. **Stream all four signals** (console / pageerror / requestfailed / response).
   The decisive clue is usually an **absence**: no `upload start` log + no POST
   ⇒ the handler never ran or bailed early.
4. **Bisect the paths.** The upload bug reproduced via browse but *not* drag-
   drop. That split (live `input.files` vs independent `dataTransfer.files`)
   pointed straight at the live-FileList clearing.
5. **Drop to native events when a handler silently no-ops.** Attaching raw
   listeners exposed the smoking gun:
   ```
   [NATIVE] input fired, files= 1     ← file present
   [NATIVE] change fired, files= 0    ← emptied before the Vue handler ran
   ```
6. **Re-run the same script after the fix** to verify (it relies on Vite HMR,
   so no rebuild needed) and keep it as a regression check.

## Adapting it to other flows

Copy `upload-smoke.mjs` and swap step 2 for your action — e.g. drive the chat
WebSocket by typing a query and asserting `type:"token"` frames arrive, or
exercise the New Chat dialog's document picker and session creation. Keep the
four `page.on(...)` listeners; they are the reusable core.
