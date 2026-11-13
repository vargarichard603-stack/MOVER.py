import os, json, time, requests

TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT"]
RUN_SECONDS = 270
INTERVAL = 60
COOLDOWN = 3600
STATE = "state.json"
B = "https://fapi.binance.com"
RANK = {"24h": 1, "7d": 2, "30d": 3}

def get(path, **p):
    r = requests.get(B + path, params=p, timeout=15)
    r.raise_for_status()
    return r.json()

def tg(text):
    chunk = ""
    for line in text.split("\n"):
        if len(chunk) + len(line) > 3800:
            send(chunk)
            chunk = ""
        chunk += line + "\n"
    if chunk:
        send(chunk)

def send(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text, "disable_web_page_preview": True},
        timeout=10,
    )

def check(state):
    now = time.time()
    msgs = []
    for t in get("/fapi/v1/ticker/24hr"):
        s = t["symbol"]
        if not s.endswith("USDT"):
            continue
        last = float(t["lastPrice"])
        h24 = float(t["highPrice"])
        if h24 <= 0 or last < h24 * 0.995:
            continue
        k1 = get("/fapi/v1/klines", symbol=s, interval="1m", limit=15)
        m = max(float(k[2]) for k in k1)
        if m < h24:
            continue
        d = get("/fapi/v1/klines", symbol=s, interval="1d", limit=31)[:-1]
        lvl = "24h"
        if len(d) >= 30 and m >= max(float(k[2]) for k in d):
            lvl = "30d"
        elif len(d) >= 6 and m >= max(float(k[2]) for k in d[-6:]):
            lvl = "7d"
        prev = state.get(s)
        if prev and now - prev["t"] < COOLDOWN and RANK[lvl] <= RANK[prev["l"]]:
            continue
        state[s] = {"t": now, "l": lvl}
        chg = float(t["priceChangePercent"])
        msgs.append(f"🚀 {s} {chg:+.1f}% | New {lvl} High | {last}")
    return msgs

try:
    state = json.load(open(STATE))
except Exception:
    state = {}

start = time.time()
first = True
while True:
    try:
        msgs = check(state)
        if msgs:
            tg("\n".join(msgs))
    except Exception as e:
        print("hiba:", e)
        if first:
            raise
    first = False
    if time.time() - start + INTERVAL > RUN_SECONDS:
        break
    time.sleep(INTERVAL)

now = time.time()
state = {k: v for k, v in state.items() if now - v["t"] < 86400}
json.dump(state, open(STATE, "w"))
