import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from TikTokLive import TikTokLiveClient


# ============================================================
# FARMING VIDZEME
# TIKTOK LIVE MONITOR → DISCORD
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

# Discord embed krāsa
DISCORD_COLOR = 0xE91E63

# TikTok pārbaudes mēģinājumi
TIKTOK_RETRIES = 3

# Pauze starp mēģinājumiem
TIKTOK_RETRY_DELAY = 4

# TikTok timeout
TIKTOK_TIMEOUT = 25

# Discord timeout
DISCORD_TIMEOUT = 20


# ============================================================
# LAIKS
# ============================================================

def timestamp():
    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


# ============================================================
# NOKLUSĒTAIS STATUSS
# ============================================================

def default_status():
    return {
        username: False
        for username in USERS
    }


# ============================================================
# STATUSA IELĀDE
# ============================================================

def load_status():

    status = default_status()

    if not os.path.exists(STATUS_FILE):
        print("📁 live_status.json nav atrasts.")
        print("🆕 Izveidoju sākuma statusu.")
        return status

    try:
        with open(
            STATUS_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            print("⚠️ live_status.json nav derīgs JSON objekts.")
            return status

        for username in USERS:

            value = data.get(username)

            if isinstance(value, bool):
                status[username] = value

        print("✅ Iepriekšējais LIVE statuss ielādēts.")

    except Exception as error:

        print(
            f"⚠️ Neizdevās nolasīt {STATUS_FILE}: "
            f"{type(error).__name__}: {error}"
        )

    return status


# ============================================================
# STATUSA DROŠA SAGLABĀŠANA
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

            file.write("\n")

        os.replace(
            temp_path,
            STATUS_FILE
        )

        print("💾 LIVE statuss saglabāts.")

        return True

    except Exception as error:

        print(
            f"❌ Neizdevās saglabāt statusu: "
            f"{type(error).__name__}: {error}"
        )

        if temp_path:

            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass

        return False


# ============================================================
# TIKTOK CLIENT
# ============================================================

def create_client(username):

    return TikTokLiveClient(
        unique_id=username
    )


# ============================================================
# TIKTOK CLIENT AIZVĒRŠANA
# ============================================================

async def close_client(client):

    if client is None:
        return

    try:

        web_client = getattr(
            client,
            "web",
            None
        )

        close_method = getattr(
            web_client,
            "close",
            None
        )

        if close_method:

            result = close_method()

            if asyncio.iscoroutine(result):
                await result

    except Exception:
        pass


# ============================================================
# TIKTOK LIVE PĀRBAUDE
# ============================================================

async def check_user_live(username):

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"👤 @{username}")
    print("🔎 Pārbaudu LIVE statusu...")

    last_error = None

    for attempt in range(
        1,
        TIKTOK_RETRIES + 1
    ):

        client = None

        try:

            client = create_client(
                username
            )

            is_live = await asyncio.wait_for(
                client.is_live(),
                timeout=TIKTOK_TIMEOUT
            )

            if is_live:

                print(
                    f"🔴 @{username} → LIVE"
                )

                return True

            print(
                f"⚫ @{username} → OFFLINE"
            )

            return False

        except Exception as error:

            last_error = error

            print(
                f"⚠️ TikTok kļūda "
                f"({attempt}/{TIKTOK_RETRIES})"
            )

            print(
                f"   {type(error).__name__}: {error}"
            )

            if attempt < TIKTOK_RETRIES:

                print(
                    f"   ⏳ Atkārtošu pēc "
                    f"{TIKTOK_RETRY_DELAY}s..."
                )

                await asyncio.sleep(
                    TIKTOK_RETRY_DELAY
                )

        finally:

            await close_client(
                client
            )

    print(
        f"❌ @{username}: LIVE statusu nevarēja droši noteikt."
    )

    if last_error:

        print(
            f"   Pēdējā kļūda: "
            f"{type(last_error).__name__}: {last_error}"
        )

    print(
        "🛡️ Iepriekšējais statuss netiek mainīts."
    )

    return None


# ============================================================
# TIKTOK PROFILA BILDES IEGŪŠANA
# ============================================================

async def get_avatar(username):

    print(
        f"🖼️ Iegūstu @{username} TikTok profila bildi..."
    )

    client = None

    try:

        client = create_client(
            username
        )

        avatar_url = await asyncio.wait_for(
            client.get_avatar_url(),
            timeout=TIKTOK_TIMEOUT
        )

        if avatar_url:

            print(
                "✅ TikTok profila bilde atrasta."
            )

            return avatar_url

        print(
            "⚠️ TikTok neatgrieza profila bildi."
        )

    except Exception as error:

        print(
            f"⚠️ Neizdevās iegūt @{username} profila bildi:"
        )

        print(
            f"   {type(error).__name__}: {error}"
        )

    finally:

        await close_client(
            client
        )

    return None


# ============================================================
# DISCORD LIVE PAZIŅOJUMS
# ============================================================

def send_discord_notification(
    username,
    avatar_url
):

    if not DISCORD_WEBHOOK_URL:

        print(
            "❌ DISCORD_WEBHOOK_URL nav atrasts!"
        )

        return False


    encoded_username = quote(
        username
    )

    profile_url = (
        f"https://www.tiktok.com/@{encoded_username}"
    )

    live_url = (
        f"https://www.tiktok.com/@{encoded_username}/live"
    )


    # --------------------------------------------------------
    # PROFILA BILDES
    # --------------------------------------------------------

    image_data = {}

    if avatar_url:

        image_data = {
            "image": {
                "url": avatar_url
            }
        }


    # --------------------------------------------------------
    # DISCORD EMBED
    # --------------------------------------------------------

    embed = {

        "title": "🔴 TIKTOK LIVE",

        "description": (
            "### 🚜 Farming Vidzeme\n\n"
            f"**@{username}** tikko sāka tiešraidi!\n\n"
            "🟢 **STATUSS**  `LIVE NOW`"
        ),

        "url": live_url,

        "color": DISCORD_COLOR,

        "thumbnail": (
            {
                "url": avatar_url
            }
            if avatar_url
            else None
        ),

        "fields": [

            {
                "name": "👤 TikTok konts",
                "value": (
                    f"**[@{username}]"
                    f"({profile_url})**"
                ),
                "inline": True
            },

            {
                "name": "🔴 Tiešraide",
                "value": "`● LIVE`",
                "inline": True
            },

            {
                "name": "🎥 Skatīties",
                "value": (
                    f"[**ATVĒRT TIKTOK LIVE →**]"
                    f"({live_url})"
                ),
                "inline": False
            }

        ],

        "footer": {
            "text": (
                "🌾 Farming Vidzeme • "
                "TikTok LIVE Monitor"
            )
        },

        "timestamp": datetime.now(
            timezone.utc
        ).isoformat()
    }


    # Ja bilde nav pieejama, thumbnail neieliekam
    if not avatar_url:

        embed.pop(
            "thumbnail",
            None
        )


    # Lielais attēls
    if image_data:

        embed.update(
            image_data
        )


    # --------------------------------------------------------
    # DISCORD PAYLOAD
    # --------------------------------------------------------

    payload = {

        "username": BOT_NAME,

        "embeds": [
            embed
        ],

        "allowed_mentions": {
            "parse": []
        }
    }


    # --------------------------------------------------------
    # NOSŪTĪŠANA
    # --------------------------------------------------------

    try:

        print(
            "📨 Sūtu LIVE paziņojumu uz Discord..."
        )

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=DISCORD_TIMEOUT
        )

        print(
            f"📡 Discord HTTP: "
            f"{response.status_code}"
        )


        if 200 <= response.status_code < 300:

            print(
                "✅ Discord LIVE paziņojums nosūtīts!"
            )

            return True


        print(
            "❌ Discord webhook kļūda:"
        )

        print(
            response.text[:2000]
        )

        return False


    except requests.RequestException as error:

        print(
            "❌ Discord savienojuma kļūda:"
        )

        print(
            f"   {type(error).__name__}: {error}"
        )

        return False


# ============================================================
# VIENA KONTA APSTRĀDE
# ============================================================

async def process_user(
    username,
    previous_status
):

    current_status = await check_user_live(
        username
    )


    # ========================================================
    # TIKTOK KĻŪDA
    # ========================================================

    if current_status is None:

        # Ļoti svarīgi:
        # kļūdas gadījumā iepriekšējo statusu nemainām.

        return previous_status


    # ========================================================
    # OFFLINE
    # ========================================================

    if current_status is False:

        # OFFLINE NETIEK SŪTĪTS NEVIENS DISCORD PAZIŅOJUMS.

        if previous_status:

            print(
                f"🛑 @{username} vairs nav LIVE."
            )

        return False


    # ========================================================
    # LIVE, BET JAU BIJA LIVE
    # ========================================================

    if current_status is True:

        if previous_status:

            print(
                f"🔴 @{username} joprojām ir LIVE."
            )

            print(
                "🔕 Discord paziņojums netiek sūtīts."
            )

            return True


        # ====================================================
        # TIKAI ŠEIT NOTIEK PAZIŅOJUMS
        #
        # OFFLINE → LIVE
        # ====================================================

        print()
        print(
            "🚨 ====================================="
        )

        print(
            f"🚨 JAUNS LIVE: @{username}"
        )

        print(
            "🚨 ====================================="
        )


        # ----------------------------------------------------
        # Iegūst TikTok profila bildi
        # ----------------------------------------------------

        avatar_url = await get_avatar(
            username
        )


        # ----------------------------------------------------
        # Sūta Discord
        # ----------------------------------------------------

        sent = send_discord_notification(
            username=username,
            avatar_url=avatar_url
        )


        # ----------------------------------------------------
        # Tikai veiksmīga Discord nosūtīšana
        # ----------------------------------------------------

        if sent:

            print(
                f"✅ @{username}: paziņojums nosūtīts."
            )

            return True


        # ----------------------------------------------------
        # Discord neizdevās
        # ----------------------------------------------------

        print(
            f"⚠️ @{username}: Discord paziņojums neizdevās."
        )

        print(
            "🔁 Nākamajā pārbaudē mēģinās vēlreiz."
        )

        return previous_status


    return previous_status


# ============================================================
# GALVENĀ FUNKCIJA
# ============================================================

async def main():

    print()
    print(
        "╔══════════════════════════════════════════════╗"
    )
    print(
        "║       🚜 FARMING VIDZEME BOT                 ║"
    )
    print(
        "║       📡 TIKTOK LIVE → DISCORD               ║"
    )
    print(
        "╚══════════════════════════════════════════════╝"
    )
    print()

    print(
        f"🕐 {timestamp()}"
    )

    print(
        f"👥 Konti: {len(USERS)}"
    )

    print(
        "🔕 OFFLINE konti Discordā NETIEK rādīti."
    )

    print()


    # ========================================================
    # WEBHOOK
    # ========================================================

    if DISCORD_WEBHOOK_URL:

        print(
            "✅ Discord webhook: OK"
        )

    else:

        print(
            "❌ Discord webhook: NAV IESTATĪTS"
        )


    # ========================================================
    # IEPRIEKŠĒJAIS STATUSS
    # ========================================================

    previous_status = load_status()


    # ========================================================
    # JAUNAIS STATUSS
    # ========================================================

    new_status = {}


    # ========================================================
    # PĀRBAUDA VISUS 3
    # ========================================================

    print()
    print(
        "🔎 Pārbaudu visus 3 TikTok kontus..."
    )
    print()


    for username in USERS:

        old_status = previous_status.get(
            username,
            False
        )

        result = await process_user(
            username,
            old_status
        )

        new_status[username] = result


        # Saglabā starprezultātu atmiņā.
        #
        # Tas nozīmē, ka katrs konts tiek apstrādāts
        # neatkarīgi no pārējiem.

    # ========================================================
    # SAGLABĀ STATUSU
    # ========================================================

    print()
    print(
        "💾 Saglabāju visu 3 kontu statusu..."
    )

    save_status(
        new_status
    )


    # ========================================================
    # BEIGAS
    # ========================================================

    print()
    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        "🏁 PĀRBAUDE PABEIGTA"
    )

    print(
        "🔕 OFFLINE kontiem nekas uz Discord netika sūtīts."
    )

    print(
        f"🕐 {timestamp()}"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 Bot apturēts."
        )

    except Exception as error:

        print(
            "💥 NEGAIDĪTA KĻŪDA:"
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        raise
