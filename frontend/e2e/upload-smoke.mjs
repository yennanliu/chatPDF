#!/usr/bin/env node
/**
 * End-to-end upload smoke test / debug driver.
 *
 * Drives the real ChatPDF UI in a headless Chrome and replicates the exact
 * "click to browse -> pick a PDF" user flow, while streaming everything the
 * browser sees: console logs, page errors, failed requests, and every /api
 * response. This is the harness that caught the silent browse-upload bug
 * (the file-chooser path produced no logs and no network call).
 *
 * Why this exists: curl/unit tests confirm the backend works, but upload bugs
 * often live in the browser event plumbing (event handlers, live FileLists,
 * proxy wiring). Only a real browser exercising the real DOM surfaces them.
 *
 * Prereqs:
 *   - Frontend dev server running (default http://localhost:5173)
 *   - Backend running behind the Vite /api proxy
 *   - Google Chrome installed (uses channel:'chrome' — no browser download)
 *   - playwright-core devDependency (already in package.json)
 *
 * Usage:
 *   node e2e/upload-smoke.mjs [path/to/file.pdf]
 *   BASE_URL=http://localhost:5173 HEADED=1 node e2e/upload-smoke.mjs
 *
 * Env:
 *   BASE_URL  app URL                       (default http://localhost:5173)
 *   HEADED=1  show the browser window       (default headless)
 *   WAIT_MS   ms to wait for ingest polling  (default 8000)
 *
 * Exit code: 0 if the upload reached the backend (POST 2xx), 1 otherwise.
 */
import { chromium } from 'playwright-core'
import { writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const HEADED = process.env.HEADED === '1'
const WAIT_MS = Number(process.env.WAIT_MS || 8000)
const log = (...a) => console.log('[e2e]', ...a)

// A minimal valid PDF so the script is self-contained when no file is passed.
function makeSamplePdf() {
  const p = join(tmpdir(), 'chatpdf-e2e-sample.pdf')
  const pdf = `%PDF-1.1
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 58>>stream
BT /F1 12 Tf 20 100 Td (ChatPDF e2e smoke test PDF.) Tj ET
endstream endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
trailer<</Root 1 0 R>>
%%EOF`
  writeFileSync(p, pdf)
  return p
}

const filePath = process.argv[2] || makeSamplePdf()
if (!existsSync(filePath)) {
  console.error(`[e2e] file not found: ${filePath}`)
  process.exit(1)
}

const browser = await chromium.launch({ channel: 'chrome', headless: !HEADED })
const page = await (await browser.newContext()).newPage()

let uploadOk = false
// Stream everything the page emits — this is what makes it a debug tool.
page.on('console', (m) => console.log(`  [console.${m.type()}]`, m.text()))
page.on('pageerror', (e) => console.log('  [PAGEERROR]', e.message))
page.on('requestfailed', (r) =>
  console.log('  [REQ FAILED]', r.method(), r.url(), r.failure()?.errorText),
)
page.on('response', (r) => {
  if (!r.url().includes('/api/')) return
  const path = r.url().replace(BASE_URL, '')
  console.log(`  [resp] ${r.status()} ${r.request().method()} ${path}`)
  if (r.request().method() === 'POST' && path.includes('/upload') && r.ok()) uploadOk = true
})

try {
  log(`goto ${BASE_URL}`)
  await page.goto(BASE_URL, { waitUntil: 'networkidle' })

  // Exact user flow: click "click to browse" -> OS file chooser -> pick file.
  log('click "click to browse" -> file chooser')
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.getByText('click to browse').click(),
  ])
  await chooser.setFiles(filePath)
  log(`file set (${filePath}); waiting ${WAIT_MS}ms for upload + ingest poll…`)
  await page.waitForTimeout(WAIT_MS)
} finally {
  await browser.close()
}

log(uploadOk ? 'PASS — upload reached backend (POST 2xx)' : 'FAIL — no successful upload POST observed')
process.exit(uploadOk ? 0 : 1)
