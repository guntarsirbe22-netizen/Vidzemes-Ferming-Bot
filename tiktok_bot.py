
import asyncio
import json
import os
import tempfile
from datetime import datetime

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

DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    ""
).strip()

BOT_NAME = "Farming Vidzeme"


# ============================================================
# IELĀDĒ IEPRIEKŠĒJO STATUSU
# ============================================================

def load_status():
    default_status = {
        user: False
        for user in USERS
    }

    if not os.path.exists(STATUS_FILE):
        print("📁 live_status.json nav atrasts.")
        print("📁 Tiek izmantots sākuma OFFLINE statuss.")
        return default_status

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        for user in USERS:
            if isinstance(
                data.get(user),
                bool
            ):
                default_status[user] = data[user]

        return default_status

    except Exception as error:
        print(
            f"⚠️ Kļūda lasot {STATUS_FILE}: "
            f"{type(error).__name__}: {error}"
        )

        return default_status


# ============================================================
# SAGLABĀ STATUSU
# ============================================================

def save_status(status):
    temp_path = None

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
        ) as file:

            json.dump(
                status,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temp_path,
            STATUS_FILE
        )

        print()
        print("💾 STATUSS SAGLABĀTS")

        for user in USERS:
            if status.get(user, False):
                print(f"🔴 @{user}: LIVE")
            else:
                print(f"⚫ @{user}: OFFLINE")

        return True

    except Exception as error:
        print(
            f"❌ Neizdevās saglabāt statusu: "
            f"{type(error).__name__}: {error}"
        )

        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

        return False


# ============================================================
# PĀRBAUDA TIKTOK LIVE
# ============================================================

async def check_user_live(username):

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"👤 Pārbaudu @{username}")
    print("🌐 TikTokLive: pārbaudu LIVE statusu...")

    try:
        client = TikTokLiveClient(
            unique_id=username
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

    except Exception as error:

        print(
            f"⚠️ @{username} pārbaudes kļūda:"
        )

        print(
            f"   {type(error).__name__}: {error}"
        )

        print(
            "   ⚠️ Iepriekšējais statuss netiek mainīts."
        )

        return None


# ============================================================
# NOSŪTA DISCORD PAZIŅOJUMU
# ============================================================

def send_discord_notification(username):

    if not DISCORD_WEBHOOK_URL:
        print(
            "❌ DISCORD_WEBHOOK_URL nav pieejams!"
        )
        return False

    tiktok_url = (
        f"https://www.tiktok.com/@{username}/live"
    )

    message = (
        f"🔴 **TIKTOK LIVE!**\n\n"
        f"**@{username}** ir sācis TikTok LIVE!\n\n"
        f"🎥 Skatīties tiešraidi:\n"
        f"{tiktok_url}"
    )

    payload = {
        "content": message,
        "username": BOT_NAME
    }

    try:

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=20
        )

        print(
            f"📡 Discord HTTP: {response.status_code}"
        )

        if 200 <= response.status_code < 300:

            print(
                "✅ Discord paziņojums nosūtīts!"
            )

            return True

        print(
            "❌ Discord kļūda:"
        )

        print(
            response.text[:2000]
        )

        return False

    except requests.RequestException as error:

        print(
            f"❌ Discord savienojuma kļūda:"
        )

        print(
            f"   {type(error).__name__}: {error}"
        )

        return False


# ============================================================
# APSTRĀDĀ VIENU TIKTOK LIETOTĀJU
# ============================================================

async def process_user(
    username,
    previous_status
):

    current_status = await check_user_live(
        username
    )

    # --------------------------------------------------------
    # TikTok statusu nevarēja noteikt
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
    # LIETOTĀJS NAV LIVE
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
    # LIETOTĀJS IR LIVE
    # --------------------------------------------------------

    if current_status is True:

        # Ja iepriekš jau bija LIVE,
        # jaunu Discord ziņu nesūtām.

        if previous_status:

            print(
                f"🔴 @{username} "
                f"joprojām ir LIVE."
            )

            return True


        # ----------------------------------------------------
        # LIVE tikko sākās
        # ----------------------------------------------------

        print(
            f"🚨 @{username} TIKKO SĀKA LIVE!"
        )

        print(
            "📨 Sūtu paziņojumu uz Discord..."
        )

        discord_sent = send_discord_notification(
            username
        )


        # ----------------------------------------------------
        # Discord veiksmīgi saņēma ziņu
        # ----------------------------------------------------

        if discord_sent:

            print(
                f"✅ @{username}: "
                f"LIVE statuss saglabāts."
            )

            return True


        # ----------------------------------------------------
        # Discord ziņu neizdevās nosūtīt
        # ----------------------------------------------------

        print(
            f"⚠️ @{username}: "
            f"Discord paziņojums neizdevās."
        )

        print(
            "⚠️ LIVE statuss netiek saglabāts."
        )

        return False


    return previous_status


# ============================================================
# GALVENĀ PROGRAMMA
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

    now = datetime.now()

    print(
        now.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    print()


    # ========================================================
    # DISCORD WEBHOOK PĀRBAUDE
    # ========================================================

    if DISCORD_WEBHOOK_URL:

        print(
            "✅ Discord webhook ir pieejams."
        )

    else:

        print(
            "❌ Discord webhook nav pieejams!"
        )

        print(
            "❌ Pārbaude tiks turpināta, "
            "bet Discord ziņu nosūtīt nevarēs."
        )


    # ========================================================
    # IELĀDĒ IEPRIEKŠĒJO STATUSU
    # ========================================================

    previous_status = load_status()

    print()
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


    # ========================================================
    # PĀRBAUDA VISUS LIETOTĀJUS
    # ========================================================

    new_status = {}

    for username in USERS:

        old_status = previous_status.get(
            username,
            False
        )

        new_status[username] = (
            await process_user(
                username,
                old_status
            )
        )


    # ========================================================
    # SAGLABĀ JAUNO STATUSU
    # ========================================================

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
# STARTĒ PROGRAMMU
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
