```python
import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone

import requests
from TikTokLive import TikTokLiveClient


# ============================================================
# KONFIGURĀCIJA
# ============================================================

USERS = [
    "gun4atrakias",
    "sirmais28",
    "salvixs18",
]

STATUS_FILE = "live_status.json"

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

BOT_NAME = "Farming Vidzeme"


# ============================================================
# STATUSA FAILA IELĀDE
# ============================================================

def load_status():
    default_status = {
        user: False
        for user in USERS
    }

    if not os.path.exists(STATUS_FILE):
        return default_status

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        for user in USERS:
            value = data.get(user, False)

            if isinstance(value, bool):
                default_status[user] = value

        return default_status

    except Exception as e:
        print(f"⚠️ Neizdevās nolasīt {STATUS_FILE}: {e}")
        return default_status


# ============================================================
# STATUSA SAGLABĀŠANA
# ============================================================

def save_status(status):
    try:
        directory = os.path.dirname(
            os.path.abspath(STATUS_FILE)
        )

        fd, temp_path = tempfile.mkstemp(
            prefix="live_status_",
            suffix=".tmp",
            dir=directory
        )

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                status,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_path,
            STATUS_FILE
        )

        print("💾 STATUSS SAGLABĀTS")

        for user in USERS:
            if status.get(user):
                print(f"🔴 @{user}: LIVE")
            else:
                print(f"⚫ @{user}: OFFLINE")

        return True

    except Exception as e:
        print(
            f"❌ Neizdevās saglabāt statusu: {e}"
        )

        return False


# ============================================================
# TIKTOK LIVE PĀRBAUDE
# ============================================================

async def check_user_live(username):

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"👤 Pārbaudu @{username}")

    try:
        client = TikTokLiveClient(
            unique_id=username
        )

        print(
            "🌐 TikTokLive: pārbaudu LIVE statusu..."
        )

        is_live = await client.is_live()

        if is_live:
            print(
                f"🔴 @{username} IR LIVE!"
            )

            return True

        print(
            f"⚫ @{username} NAV LIVE."
        )

        return False

    except Exception as e:

        print(
            f"⚠️ @{username} pārbaudes kļūda:"
        )

        print(
            f"   {type(e).__name__}: {e}"
        )

        print(
            "   ⚠️ Statuss netiek mainīts."
        )

        return None


# ============================================================
# DISCORD PAZIŅOJUMS
# ============================================================

def send_discord_notification(username):

    if not DISCORD_WEBHOOK_URL:

        print(
            "❌ DISCORD_WEBHOOK_URL nav pieejams!"
        )

        return False


    tiktok_live_url = (
        f"https://www.tiktok.com/@{username}/live"
    )


    # --------------------------------------------------------
    # VIENKĀRŠS DISCORD EMBED
    # --------------------------------------------------------
    #
    # Apzināti izmantojam tikai drošākos laukus.
    # Bez thumbnail, timestamp un fields.
    # Tas novērš Discord HTTP 400 problēmu.
    #

    payload = {
        "username": BOT_NAME,

        "content": (
            f"🔴 **TIKTOK LIVE!**\n"
            f"@{username} ir sācis tiešraidi!\n\n"
            f"🎥 {tiktok_live_url}"
        ),

        "embeds": [
            {
                "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
                "description": (
                    f"**@{username}** ir sācis "
                    f"TikTok LIVE!"
                ),
                "url": tiktok_live_url,
                "color": 16711824
            }
        ]
    }


    try:

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=20
        )


        if 200 <= response.status_code < 300:

            print(
                "✅ Discord paziņojums nosūtīts!"
            )

            return True


        print(
            f"❌ Discord kļūda: HTTP "
            f"{response.status_code}"
        )

        print(
            response.text[:2000]
        )

        return False


    except requests.RequestException as e:

        print(
            f"❌ Discord savienojuma kļūda: {e}"
        )

        return False


# ============================================================
# VIENA LIETOTĀJA APSTRĀDE
# ============================================================

async def process_user(
    username,
    previous_status
):

    current_status = await check_user_live(
        username
    )


    # --------------------------------------------------------
    # Nevar noteikt statusu
    # --------------------------------------------------------

    if current_status is None:

        print(
            f"⚠️ @{username}: "
            f"statusu nevar droši noteikt."
        )

        print(
            f"📁 Saglabāju iepriekšējo statusu: "
            f"{'LIVE' if previous_status else 'OFFLINE'}"
        )

        return previous_status


    # --------------------------------------------------------
    # OFFLINE
    # --------------------------------------------------------

    if current_status is False:

        if previous_status:

            print(
                f"🛑 @{username} "
                f"tiešraide ir beigusies."
            )

        else:

            print(
                f"💤 @{username} paliek OFFLINE."
            )

        return False


    # --------------------------------------------------------
    # LIVE
    # --------------------------------------------------------

    if current_status is True:

        if previous_status:

            print(
                f"🔴 @{username} "
                f"joprojām ir LIVE."
            )

            return True


        print(
            f"🚨 @{username} TIKKO SĀKA LIVE!"
        )


        # ----------------------------------------------------
        # Nosūtām Discord
        # ----------------------------------------------------

        discord_sent = send_discord_notification(
            username
        )


        if discord_sent:

            print(
                f"✅ @{username}: "
                f"LIVE statuss saglabāts."
            )

            return True


        print(
            "⚠️ Discord paziņojums neizdevās."
        )

        print(
            f"⚠️ @{username}: "
            f"statusu pagaidām nesaglabāju kā LIVE."
        )

        return False


    return previous_status


# ============================================================
# GALVENĀ FUNKCIJA
# ============================================================

async def main():

    print()
    print("🤖 Farming Vidzeme")
    print("📡 TikTok LIVE → Discord")
    print("⚙️ GitHub Actions režīms")
    print()

    print(
        "🔄 PĀRBAUDU TIKTOK TIEŠRAIDES"
    )

    now = datetime.now().astimezone()

    print(
        now.strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )
    )

    print()


    # --------------------------------------------------------
    # Pārbaudām Discord webhook
    # --------------------------------------------------------

    if DISCORD_WEBHOOK_URL:

        print(
            "✅ Discord webhook ir pieejams."
        )

    else:

        print(
            "❌ Discord webhook nav pieejams!"
        )


    # --------------------------------------------------------
    # Iepriekšējais statuss
    # --------------------------------------------------------

    previous_status = load_status()


    print(
        "📁 IEPRIEKŠĒJAIS STATUSS:"
    )


    for user in USERS:

        state = (
            "LIVE"
            if previous_status.get(user, False)
            else "OFFLINE"
        )

        print(
            f"   @{user}: {state}"
        )


    # --------------------------------------------------------
    # Jaunais statuss
    # --------------------------------------------------------

    new_status = {}


    for username in USERS:

        old_status = (
            previous_status.get(
                username,
                False
            )
        )


        new_status[username] = (
            await process_user(
                username,
                old_status
            )
        )


    # --------------------------------------------------------
    # Saglabājam
    # --------------------------------------------------------

    print()
    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        "💾 SAGLABĀJU JAUNO STATUSU"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


    save_status(
        new_status
    )


    print()
    print(
        "🏁 PĀRBAUDE PABEIGTA"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
```
