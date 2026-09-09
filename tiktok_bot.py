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
# KRĀSAS
# ============================================================

DISCORD_COLOR = 0xFF0050


# ============================================================
# STATUSA FAILS
# ============================================================

def load_status():
    """
    Nolasa iepriekšējo LIVE statusu.
    Ja fails neeksistē vai ir bojāts, sāk ar OFFLINE.
    """

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


def save_status(status):
    """
    Droši saglabā statusu.
    Raksta pagaidu failā un pēc tam nomaina oriģinālo.
    """

    try:
        directory = os.path.dirname(os.path.abspath(STATUS_FILE))

        fd, temp_path = tempfile.mkstemp(
            prefix="live_status_",
            suffix=".tmp",
            dir=directory
        )

        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                status,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.replace(temp_path, STATUS_FILE)

        print("💾 STATUSS SAGLABĀTS")

        for user in USERS:
            if status.get(user):
                print(f"🔴 @{user}: LIVE")
            else:
                print(f"⚫ @{user}: OFFLINE")

        return True

    except Exception as e:
        print(f"❌ Neizdevās saglabāt statusu: {e}")
        return False


# ============================================================
# TIKTOK LIVE PĀRBAUDE
# ============================================================

async def check_user_live(username):
    """
    Izmanto TikTokLive bibliotēkas is_live() funkciju.

    Atgriež:
        True  = LIVE
        False = OFFLINE
        None  = pārbaudi nevarēja droši veikt
    """

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"👤 Pārbaudu @{username}")

    try:
        client = TikTokLiveClient(
            unique_id=username
        )

        print("🌐 TikTokLive: pārbaudu LIVE statusu...")

        is_live = await client.is_live()

        if is_live:
            print(f"🔴 @{username} IR LIVE!")
            return True

        print(f"⚫ @{username} NAV LIVE.")
        return False

    except Exception as e:
        print(f"⚠️ @{username} pārbaudes kļūda:")
        print(f"   {type(e).__name__}: {e}")
        print("   ⚠️ Statuss netiek mainīts.")

        return None


# ============================================================
# AVATĀRS
# ============================================================

async def get_avatar(username):
    """
    Mēģina iegūt TikTok profila avatāru.
    Ja neizdodas, atgriež None.
    """

    try:
        client = TikTokLiveClient(
            unique_id=username
        )

        avatar = await client.get_avatar_url()

        if avatar:
            return avatar

    except Exception as e:
        print(f"⚠️ Neizdevās iegūt @{username} avatāru: {e}")

    return None


# ============================================================
# DISCORD
# ============================================================

def send_discord_notification(username, avatar_url=None):
    """
    Nosūta LIVE paziņojumu uz Discord webhook.
    """

    if not DISCORD_WEBHOOK_URL:
        print("❌ Nav atrasts DISCORD_WEBHOOK_URL secrets!")
        return False

    now = datetime.now(timezone.utc)

    embed = {
        "title": "🔴 TIEŠRAIDE IR SĀKUSIES!",
        "description": (
            f"**@{username}** ir sācis TikTok LIVE!\n\n"
            f"🎥 [Skatīties TikTok LIVE]"
            f"(https://www.tiktok.com/@{username}/live)"
        ),
        "color": DISCORD_COLOR,
        "fields": [
            {
                "name": "📱 TikTok",
                "value": f"[@{username}](https://www.tiktok.com/@{username})",
                "inline": True
            },
            {
                "name": "🔴 Statuss",
                "value": "LIVE",
                "inline": True
            }
        ],
        "footer": {
            "text": BOT_NAME
        },
        "timestamp": now.isoformat()
    }

    if avatar_url:
        embed["thumbnail"] = {
            "url": avatar_url
        }

    payload = {
        "username": BOT_NAME,
        "embeds": [
            embed
        ]
    }

    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=20
        )

        if 200 <= response.status_code < 300:
            print("✅ Discord paziņojums nosūtīts!")
            return True

        print(
            f"❌ Discord kļūda: "
            f"HTTP {response.status_code}"
        )

        print(response.text[:1000])

        return False

    except requests.RequestException as e:
        print(f"❌ Discord savienojuma kļūda: {e}")
        return False


# ============================================================
# VIENA LIETOTĀJA PĀRBAUDE
# ============================================================

async def process_user(username, previous_status):
    """
    Apstrādā vienu TikTok lietotāju.

    Ļoti svarīgi:
    None NEKAD netiek uzskatīts par OFFLINE.
    """

    current_status = await check_user_live(username)

    # --------------------------------------------------------
    # TIKTOK PĀRBAUDE NEIZDEVĀS
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
                f"🛑 @{username} tiešraide ir beigusies."
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

        # Jau bija LIVE
        if previous_status:
            print(
                f"🔴 @{username} joprojām ir LIVE."
            )

            return True

        # Tikko sācies LIVE
        print(
            f"🚨 @{username} TIKKO SĀKA LIVE!"
        )

        avatar_url = await get_avatar(username)

        discord_sent = send_discord_notification(
            username,
            avatar_url
        )

        if discord_sent:
            print(
                f"✅ @{username}: "
                f"LIVE statuss saglabāts."
            )

            return True

        # Ja Discord neizdevās, saglabājam OFFLINE.
        # Nākamajā ciklā mēģinās vēlreiz.
        print(
            f"⚠️ Discord paziņojums neizdevās."
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

    print("🔄 PĀRBAUDU TIKTOK TIEŠRAIDES")

    now = datetime.now().astimezone()

    print(
        now.strftime("%Y-%m-%d %H:%M:%S %Z")
    )

    print()

    previous_status = load_status()

    print("📁 IEPRIEKŠĒJAIS STATUSS:")

    for user in USERS:
        state = (
            "LIVE"
            if previous_status.get(user, False)
            else "OFFLINE"
        )

        print(f"   @{user}: {state}")

    new_status = {}

    for username in USERS:

        old_status = previous_status.get(
            username,
            False
        )

        new_status[username] = await process_user(
            username,
            old_status
        )

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("💾 SAGLABĀJU JAUNO STATUSU")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    save_status(new_status)

    print()
    print("🏁 PĀRBAUDE PABEIGTA")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
