import os
import json
import time
import requests
from datetime import datetime, timezone

API_URL = "https://www.amdgaming.com/promotions"

STATE_FILE = "amd_state.json"
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK","https://discord.com/api/webhooks/1528295172096659486/_dwcUjlAC-OorUKLN68I1vf835oGLMpFmtpd_a2tJGHbiozFe5xxMJVCw9W4YKZvEtH-")

# Optional role ping. Add this in GitHub Secrets if you want.
# Example value: <@&123456789012345678>
ROLE_PING = os.getenv("ROLE_PING", "@&1528322259465404487").strip()

AMD_LOGO = "https://files.catbox.moe/pewooo.png"
FOOTER_TEXT = "Justice's AMD Gaming Informer"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def discord_timestamp(unix_time):
    try:
        return f"<t:{int(unix_time)}:F>"
    except Exception:
        return "Unknown"


def fetch_promotions():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
    }

    r = requests.get(API_URL, headers=headers, timeout=30)
    print("API:", r.status_code)

    if r.status_code != 200:
        print(r.text[:500])
        return []

    data = r.json()
    return data.get("items", [])


def get_status(keys, status):
    status = str(status or "").lower()

    if status == "active" and keys > 0:
        return "✅", 0x2ecc71

    if status == "active" and keys <= 0:
        return "❌", 0xed4245

    return "🔴", 0x992d22

def should_post(item, old):
    keys = int(item.get("keysAvailable") or 0)
    status = str(item.get("status", "")).lower()

    if not old:
        return True, "new"

    old_keys = int(old.get("keysAvailable") or 0)
    old_status = str(old.get("status", "")).lower()

    # Restock: 0 keys -> more than 0 keys
    if old_keys <= 0 and keys > 0 and status == "active":
        return True, "restock"

    # Out of keys: had keys -> now 0
    if old_keys > 0 and keys <= 0 and status == "active":
        return True, "out_of_keys"

    # Ended status changed
    if old_status != status and status != "active":
        return True, "ended"

    return False, None


def build_message_text(reason):
    if reason in ["new", "restock"] and ROLE_PING:
        return ROLE_PING
    return ""


def send_discord(item, reason):
    title = item.get("title", "Unknown Giveaway")
    slug = item.get("slug", "")
    image = item.get("thumbnailImageUrl")
    platform = item.get("platform", "Unknown")
    keys = int(item.get("keysAvailable") or 0)

    status_emoji, color = get_status(keys, item.get("status"))

    url = f"https://www.amdgaming.com/promotions/{slug}"

    embed = {
        "author": {
            "name": "AMDGaming - Promotions",
            "icon_url": AMD_LOGO,
        },
        "title": title,
        "url": url,
        "color": color,
        "fields": [
            {
                "name": "Status",
                "value": status_emoji,
                "inline": True
            },
            {
                "name": "Platform",
                "value": platform,
                "inline": True
            },
            {
                "name": "Keys",
                "value": f"🔑 {keys}",
                "inline": True
            }
        ],
        "footer": {
            "text": FOOTER_TEXT,
            "icon_url": "https://files.catbox.moe/oonmfa.jpg",
        }
    }

    if image:
        embed["image"] = {"url": image}

    payload = {
        "content": build_message_text(reason),
        "embeds": [embed],
        "allowed_mentions": {
            "parse": ["roles"]
        }
    }

    r = requests.post(WEBHOOK_URL, json=payload, timeout=30)

    print(title)
    print("Reason:", reason)
    print("Discord:", r.status_code)

    if r.status_code == 429:
        try:
            retry = r.json().get("retry_after", 2)
        except Exception:
            retry = 2

        print(f"Rate limited. Sleeping {retry} seconds...")
        time.sleep(float(retry) + 1)

    elif r.text:
        print(r.text[:300])

    time.sleep(1.5)
    
def main():
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK missing")
        return

    state = load_state()
    items = fetch_promotions()

    print(f"Found {len(items)} promotions")

    for item in items:
        promo_id = item.get("id")

        if not promo_id:
            continue

        promo_id = str(promo_id)
        old = state.get(promo_id)

        post, reason = should_post(item, old)

        if post:
            send_discord(item, reason)

        state[promo_id] = {
            "title": item.get("title"),
            "status": item.get("status"),
            "keysAvailable": int(item.get("keysAvailable") or 0),
            "updatedAt": item.get("updatedAt"),
            "slug": item.get("slug"),
        }

    save_state(state)


if __name__ == "__main__":
    main()
