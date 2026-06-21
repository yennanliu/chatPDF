#!/usr/bin/env python3
"""WebSocket chat smoke test. Creates a session over all indexed documents."""
import asyncio, json, sys
import websockets

BASE = "http://localhost:8000/api"
WS_BASE = "ws://localhost:8000/ws"

async def create_session() -> str:
    import urllib.request
    # Chat against every indexed document currently in the backend.
    with urllib.request.urlopen(f"{BASE}/documents") as r:
        docs = json.loads(r.read())
    doc_ids = [d["doc_id"] for d in docs if d["status"] == "indexed"]
    payload = json.dumps({
        "doc_ids": doc_ids, "provider": "google", "model": "gemini-2.0-flash-lite",
    }).encode()
    req = urllib.request.Request(f"{BASE}/sessions", data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["session_id"]

async def delete_session(session_id: str):
    import urllib.request
    req = urllib.request.Request(f"{BASE}/sessions/{session_id}", method="DELETE")
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass

async def chat(session_id: str, query: str, retries: int = 5) -> dict:
    url = f"{WS_BASE}/chat/{session_id}"
    for attempt in range(retries):
        tokens = []
        sources = []
        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps({"query": query}))
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    msg = json.loads(raw)
                    if msg["type"] == "token":
                        tokens.append(msg["data"])
                        print(msg["data"], end="", flush=True)
                    elif msg["type"] == "done":
                        sources = msg.get("sources", [])
                        return {"answer": "".join(tokens), "sources": sources}
                    elif msg["type"] == "error":
                        detail = msg["detail"]
                        if "quota" in detail.lower() or "rate" in detail.lower():
                            wait = 30 * (attempt + 1)
                            print(f"\n  [rate limited, waiting {wait}s before retry {attempt+1}/{retries}]")
                            await asyncio.sleep(wait)
                            break
                        raise RuntimeError(f"Server error: {detail}")
        except websockets.exceptions.ConnectionClosedOK:
            if tokens:
                return {"answer": "".join(tokens), "sources": sources}
    raise RuntimeError(f"Failed after {retries} retries (rate limited)")

async def main():
    print("Creating session...")
    sess = await create_session()
    print(f"Session: {sess}\n")

    query = "Summarize what this document is about in 2 sentences."
    print(f"Query: {query}\n")
    print("Answer: ", end="")

    result = await chat(sess, query)
    print(f"\n\nSources ({len(result['sources'])}):")
    for s in result["sources"][:3]:
        print(f"  - {s.get('source','?')} p.{s.get('page','?')}: {str(s.get('content',''))[:80]}...")

    print("\nDeleting session...")
    await delete_session(sess)

    ok = bool(result["answer"]) and len(result["answer"]) > 20
    print(f"\n{'PASS' if ok else 'FAIL'}  WebSocket chat — got {len(result['answer'])} chars, {len(result['sources'])} sources")
    sys.exit(0 if ok else 1)

asyncio.run(main())
