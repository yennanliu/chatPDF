#!/usr/bin/env bash
# Core functionality smoke test against the live backend (http://localhost:8000).
# Usage: bash scripts/test_core.sh [path/to/test.pdf]
set -euo pipefail

BASE="http://localhost:8000/api"
PDF="${1:-}"
PASS=0; FAIL=0

ok()   { echo "  PASS  $1"; ((PASS++)) || true; }
fail() { echo "  FAIL  $1 — $2"; ((FAIL++)) || true; }
skip() { echo "  SKIP  $1"; }

# ── 1. Health ─────────────────────────────────────────────────────────────────
echo
echo "=== 1. Health ==="
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/libraries")
[ "$STATUS" = "200" ] && ok "GET /api/libraries → 200" || fail "GET /api/libraries" "HTTP $STATUS"

# ── 2. Library CRUD ───────────────────────────────────────────────────────────
echo
echo "=== 2. Libraries ==="
LIB=$(curl -s -o /tmp/lib_resp.json -w "%{http_code}" -X POST "$BASE/libraries" \
  -H "Content-Type: application/json" \
  -d '{"name":"smoke-test-lib"}')
LIB_ID=$(python3 -c "import json; print(json.load(open('/tmp/lib_resp.json'))['library_id'])" 2>/dev/null || true)
[ "$LIB" = "201" ] && ok "POST /api/libraries → 201" || fail "POST /api/libraries" "HTTP $LIB"
[ -n "$LIB_ID" ] && ok "Library created id=$LIB_ID" || fail "Library id" "$(cat /tmp/lib_resp.json)"

LIST=$(curl -s "$BASE/libraries")
echo "$LIST" | python3 -c "import sys,json; libs=json.load(sys.stdin); assert any(l['library_id']=='$LIB_ID' for l in libs)" 2>/dev/null \
  && ok "GET /api/libraries lists new lib" || fail "GET /api/libraries" "$LIST"

# ── 3. Document upload (PDF required) ────────────────────────────────────────
echo
echo "=== 3. Document upload ==="
if [ -z "$PDF" ]; then
  skip "No PDF path — skipping upload. Re-run: bash scripts/test_core.sh /path/to/file.pdf"
else
  DOC=$(curl -s -o /tmp/doc_resp.json -w "%{http_code}" -X POST "$BASE/documents/upload" \
    -F "file=@$PDF" \
    -F "library_id=$LIB_ID")
  DOC_ID=$(python3 -c "import json; print(json.load(open('/tmp/doc_resp.json'))['doc_id'])" 2>/dev/null || true)
  [ "$DOC" = "201" ] && ok "POST /api/documents/upload → 201" || fail "POST /api/documents/upload" "HTTP $DOC"
  [ -n "$DOC_ID" ] && ok "Document created id=$DOC_ID" || fail "Document id" "$(cat /tmp/doc_resp.json)"

  echo "  ... polling status (up to 30 s)"
  STATUS_VAL=""
  for i in $(seq 1 15); do
    STATUS_VAL=$(curl -s "$BASE/documents/$DOC_ID/status" \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || true)
    [ "$STATUS_VAL" = "indexed" ] && break
    sleep 2
  done
  [ "$STATUS_VAL" = "indexed" ] && ok "Document status → indexed" || fail "Document status" "$STATUS_VAL"
fi

# ── 4. Session CRUD ───────────────────────────────────────────────────────────
echo
echo "=== 4. Sessions ==="
SESS=$(curl -s -o /tmp/sess_resp.json -w "%{http_code}" -X POST "$BASE/sessions" \
  -H "Content-Type: application/json" \
  -d "{\"library_id\":\"$LIB_ID\",\"provider\":\"openai\",\"model\":\"gpt-4o-mini\"}")
SESS_ID=$(python3 -c "import json; print(json.load(open('/tmp/sess_resp.json'))['session_id'])" 2>/dev/null || true)
[ "$SESS" = "201" ] && ok "POST /api/sessions → 201" || fail "POST /api/sessions" "HTTP $SESS — $(cat /tmp/sess_resp.json)"
[ -n "$SESS_ID" ] && ok "Session created id=$SESS_ID" || fail "Session id" "$(cat /tmp/sess_resp.json)"

if [ -n "$SESS_ID" ]; then
  SESS_GET=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/sessions/$SESS_ID")
  [ "$SESS_GET" = "200" ] && ok "GET /api/sessions/{id} → 200" || fail "GET /api/sessions/{id}" "HTTP $SESS_GET"

  # Delete session
  DEL_SESS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/sessions/$SESS_ID")
  [ "$DEL_SESS" = "204" ] && ok "DELETE /api/sessions/{id} → 204" || fail "DELETE /api/sessions/{id}" "HTTP $DEL_SESS"
fi

# ── 5. Cleanup ────────────────────────────────────────────────────────────────
echo
echo "=== 5. Cleanup ==="
DEL=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/libraries/$LIB_ID")
[ "$DEL" = "204" ] && ok "DELETE /api/libraries/{id} → 204" || fail "DELETE /api/libraries/{id}" "HTTP $DEL"

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "────────────────────────────────────"
echo "  Passed: $PASS  |  Failed: $FAIL"
echo "────────────────────────────────────"
[ "$FAIL" -eq 0 ]
