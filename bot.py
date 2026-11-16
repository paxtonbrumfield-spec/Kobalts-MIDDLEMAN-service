
import os
import asyncio
import sqlite3
import aiohttp
import discord

from datetime import datetime, timezone
from dotenv import load_dotenv
from discord.ext import commands, tasks

load_dotenv()

# =========================
# CONFIGURATION
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

DATABASE = "payments.db"

ADDRESSES = {
    "btc": "bc1q4dhd9hyeha383jsupvq9qwsmwpfj0d7lskllr0",
    "ltc": "LLyz7ZfbzxZMS59DWJFbViaehcLY7ec3MB",
    "sol": "5YgDLvXFui2gMUGwEVcTLj3k43oWSn2EZwbXDJTwefps",
    "usdt": "0x2DaEA564D6169D3366DB944D232479073802464B",
}

USDT_CONTRACT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

TOS = """# KOBALTS MIDDLEMAN TOS!!

If money is being sent through crypto you must wait for the money to confirm before releasing the account. If the money is not confirmed and you release and anything happens, it is your responsibility and you are completely liable.

All trades have a **$2 fee** unless the value is over **$100**.

The account must be on an Outlook or other email-changeable account (first mail or other small secure emails are acceptable).

After funds have been sent to my address, please **screenshot it and send me the transaction ID**.
"""

# =========================
# DATABASE
# =========================

def init_database():
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                coin TEXT NOT NULL,
                txid TEXT NOT NULL,
                amount TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (coin, txid)
            )
        """)

def get_payment(coin, txid):
    with sqlite3.connect(DATABASE) as db:
        return db.execute(
            "SELECT amount, status FROM payments WHERE coin=? AND txid=?",
            (coin, txid)
        ).fetchone()

async def record_payment(coin, txid, amount, status):
    previous = get_payment(coin, txid)

    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            INSERT INTO payments (coin, txid, amount, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(coin, txid)
            DO UPDATE SET status=excluded.status
        """, (coin, txid, str(amount), status))

    if previous is None:
        await notify(
            f"**{coin.upper()} Payment Detected**\n"
            f"Amount: `{amount} {coin.upper()}`\n"
            f"Status: **{status}**\n"
            f"TX: `{txid}`"
        )

    elif previous[1] != "Confirmed" and status == "Confirmed":
        await notify(
            f"**{coin.upper()} PAYMENT CONFIRMED**\n"
            f"Amount: `{amount} {coin.upper()}`\n"
            f"Status: **Confirmed**\n"
            f"TX: `{txid}`"
        )

# =========================
# DISCORD BOT
# =========================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

async def notify(message):
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)

        if channel is None:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)

        await channel.send(message)

    except Exception as e:
        print("Notification error:", e)

def make_embed(coin, address):
    embed = discord.Embed(
        title=f"Kobalts Middleman — {coin.upper()}",
        description=TOS,
        color=0x00ff88,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name=f"{coin.upper()} Address",
        value=f"`{address}`",
        inline=False
    )

    embed.add_field(
        name="Instructions",
        value=(
            "1. Send the exact amount + $2 fee (if under $100)\n"
            "2. Wait for confirmations\n"
            "3. Screenshot the transaction and send the **TXID** here"
        ),
        inline=False
    )

    embed.set_footer(
        text="Kobalts Middleman • Always wait for confirmations"
    )

    return embed

# =========================
# SLASH COMMANDS
# =========================

@bot.tree.command(name="btc", description="Post BTC address + TOS")
async def btc_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=make_embed("btc", ADDRESSES["btc"])
    )

@bot.tree.command(name="ltc", description="Post LTC address + TOS")
async def ltc_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=make_embed("ltc", ADDRESSES["ltc"])
    )

@bot.tree.command(name="sol", description="Post SOL address + TOS")
async def sol_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=make_embed("sol", ADDRESSES["sol"])
    )

@bot.tree.command(name="usdt", description="Post USDT ERC-20 address + TOS")
async def usdt_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        embed=make_embed("usdt", ADDRESSES["usdt"])
    )

@bot.tree.command(name="vouch", description="Create a customer vouch")
async def vouch_cmd(
    interaction: discord.Interaction,
    message: str
):
    safe_message = message.replace("```", "'''")

    await interaction.response.send_message(
        f"**Please copy and paste this vouch:**\n\n"
        f"```{safe_message}```"
    )

# =========================
# BITCOIN MONITOR
# =========================

async def check_btc(session):
    url = f"https://mempool.space/api/address/{ADDRESSES['btc']}/txs"

    async with session.get(url) as resp:
        if resp.status != 200:
            return

        txs = await resp.json()

    for tx in txs[:25]:
        txid = tx["txid"]
        received = 0

        for output in tx.get("vout", []):
            if output.get("scriptpubkey_address") == ADDRESSES["btc"]:
                received += output.get("value", 0)

        if received <= 0:
            continue

        status = (
            "Confirmed"
            if tx.get("status", {}).get("confirmed")
            else "Pending"
        )

        await record_payment(
            "btc",
            txid,
            f"{received / 100000000:.8f}",
            status
        )

# =========================
# LITECOIN MONITOR
# =========================

async def check_ltc(session):
    url = (
        f"https://api.blockcypher.com/v1/ltc/main/addrs/"
        f"{ADDRESSES['ltc']}/full?limit=25"
    )

    async with session.get(url) as resp:
        if resp.status != 200:
            return

        data = await resp.json()

    for tx in data.get("txs", []):
        txid = tx["hash"]
        received = 0

        for output in tx.get("outputs", []):
            if ADDRESSES["ltc"] in output.get("addresses", []):
                received += output.get("value", 0)

        if received <= 0:
            continue

        status = (
            "Confirmed"
            if tx.get("confirmations", 0) > 0
            else "Pending"
        )

        await record_payment(
            "ltc",
            txid,
            f"{received / 100000000:.8f}",
            status
        )

# =========================
# SOLANA MONITOR
# =========================

async def check_sol(session):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [
            ADDRESSES["sol"],
            {"limit": 20, "commitment": "confirmed"}
        ]
    }

    async with session.post(
        "https://api.mainnet-beta.solana.com",
        json=payload
    ) as resp:
        if resp.status != 200:
            return

        data = await resp.json()

    for item in data.get("result", []):
        signature = item["signature"]

        if item.get("err") is not None:
            continue

        tx_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }

        async with session.post(
            "https://api.mainnet-beta.solana.com",
            json=tx_payload
        ) as resp:
            if resp.status != 200:
                continue

            tx_data = await resp.json()

        tx = tx_data.get("result")

        if not tx or not tx.get("meta"):
            continue

        message = tx.get("transaction", {}).get("message", {})
        keys = message.get("accountKeys", [])

        address_index = next(
            (
                i for i, key in enumerate(keys)
                if (
                    key.get("pubkey")
                    if isinstance(key, dict)
                    else key
                ) == ADDRESSES["sol"]
            ),
            None
        )

        if address_index is None:
            continue

        meta = tx["meta"]

        if meta.get("err") is not None:
            continue

        pre = meta.get("preBalances", [])
        post = meta.get("postBalances", [])

        if address_index >= len(pre) or address_index >= len(post):
            continue

        difference = post[address_index] - pre[address_index]

        if difference <= 0:
            continue

        status = (
            "Confirmed"
            if item.get("confirmationStatus") in ("confirmed", "finalized")
            else "Pending"
        )

        await record_payment(
            "sol",
            signature,
            f"{difference / 1000000000:.9f}",
            status
        )

# =========================
# USDT ERC-20 MONITOR
# =========================

async def check_usdt(session):
    if not ETHERSCAN_API_KEY:
        return

    params = {
        "chainid": "1",
        "module": "account",
        "action": "tokentx",
        "contractaddress": USDT_CONTRACT,
        "address": ADDRESSES["usdt"],
        "page": "1",
        "offset": "50",
        "sort": "desc",
        "apikey": ETHERSCAN_API_KEY
    }

    async with session.get(
        "https://api.etherscan.io/v2/api",
        params=params
    ) as resp:
        if resp.status != 200:
            return

        data = await resp.json()

    if data.get("status") != "1":
        return

    for tx in data.get("result", []):
        if tx.get("to", "").lower() != ADDRESSES["usdt"].lower():
            continue

        if int(tx.get("isError", "0")) != 0:
            continue

        decimals = int(tx.get("tokenDecimal", "6"))
        amount = int(tx["value"]) / (10 ** decimals)

        if amount <= 0:
            continue

        status = (
            "Confirmed"
            if int(tx.get("confirmations", "0")) > 0
            else "Pending"
        )

        await record_payment(
            "usdt",
            tx["hash"],
            f"{amount:.6f}",
            status
        )

# =========================
# PAYMENT CHECK LOOP
# =========================

@tasks.loop(minutes=2)
async def check_payments():
    timeout = aiohttp.ClientTimeout(total=25)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        checks = [
            ("BTC", check_btc),
            ("LTC", check_ltc),
            ("SOL", check_sol),
            ("USDT", check_usdt)
        ]

        for name, checker in checks:
            try:
                await checker(session)
            except Exception as e:
                print(f"{name} payment check error:", e)

@check_payments.before_loop
async def before_payment_check():
    await bot.wait_until_ready()

# =========================
# BOT EVENTS
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print("Sync error:", e)

    if not check_payments.is_running():
        check_payments.start()

# =========================
# START BOT
# =========================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing from your .env file.")

    init_database()
    bot.run(TOKEN)
