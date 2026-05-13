import httpx, json
KEY = open(".langsmith/.env").read().split("LANGSMITH_PROD_CX_IQ_AIA_API_KEY=")[1].split("\n")[0].strip()
HOST = "https://langsmith.prod.usw2.plat.cxp.csco.cloud/api"
H = {"X-API-Key": KEY}
QUEUE_ID = "e84a5659-26bd-4bb9-bc30-9f1dc29963bf"

# Get queue config & try several status filter values to map vocabulary
r = httpx.get(f"{HOST}/annotation-queues/{QUEUE_ID}", headers=H, timeout=15)
print("Queue config:", json.dumps(r.json(), indent=2)[:1200])

print("\n--- counts by status filter ---")
for s in ["completed","pending","needs_review","in_progress","reserved","reviewed","archived","all"]:
    r = httpx.get(f"{HOST}/annotation-queues/{QUEUE_ID}/runs", headers=H, params={"limit":200, "status": s}, timeout=15)
    try:
        n = len(r.json())
    except Exception:
        n = r.text[:80]
    print(f"  status={s}: {n}")
