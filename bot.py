
import os
import sqlite3
import aiohttp
import discord

from datetime import datetime, timezone
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands

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
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# NOTIFICATIONS
# =========================

async def notify(message):
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)

        if channel is None:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)

        await channel.send(message)

    except Exception as e:
        print("Notification error:", e)


# =========================
# EMBEDS
# =========================

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
# COMMAND CONTEXT SETTINGS
# =========================

def dm_contexts():
    return app_commands.allowed_contexts(
        guilds=True,
        dms=True,
        private_channels=True
    )


def install_types():
    return app_commands.allowed_installs(
        guilds=True,
        users=True
    )


# =========================
# PRIVATE COMMAND GROUP
# =========================

private_group = app_commands.Group(
    name="private",
    description="Private commands"
)


@private_group.command(
    name="type",
    description="Send information only you can see"
)
@dm_contexts()
@install_types()
async def private_type(
    interaction: discord.Interaction,
    message: str
):

    await interaction.response.send_message(
        f"🔒 **YOUR PRIVATE INFORMATION**\n\n{message}",
        ephemeral=True
    )


bot.tree.add_command(private_group)


# =========================
# RELEASE INFORMATION
# =========================

@bot.tree.command(
    name="release_information",
    description="Release information publicly in the chat"
)
@dm_contexts()
@install_types()
async def release_information(
    interaction: discord.Interaction,
    message: str
):

    await interaction.response.send_message(
        f"📢 **RELEASED INFORMATION**\n\n{message}",
        allowed_mentions=discord.AllowedMentions.none()
    )


# =========================
# BTC COMMAND
# =========================

@bot.tree.command(
    name="btc",
    description="Post BTC address + TOS"
)
@dm_contexts()
@install_types()
async def btc_cmd(interaction: discord.Interaction):

    await interaction.response.send_message(
        embed=make_embed("btc", ADDRESSES["btc"])
    )


# =========================
# LTC COMMAND
# =========================

@bot.tree.command(
    name="ltc",
    description="Post LTC address + TOS"
)
@dm_contexts()
@install_types()
async def ltc_cmd(interaction: discord.Interaction):

    await interaction.response.send_message(
        embed=make_embed("ltc", ADDRESSES["ltc"])
    )


# =========================
# SOL COMMAND
# =========================

@bot.tree.command(
    name="sol",
    description="Post SOL address + TOS"
)
@dm_contexts()
@install_types()
async def sol_cmd(interaction: discord.Interaction):

    await interaction.response.send_message(
        embed=make_embed("sol", ADDRESSES["sol"])
    )


# =========================
# USDT COMMAND
# =========================

@bot.tree.command(
    name="usdt",
    description="Post USDT ERC-20 address + TOS"
)
@dm_contexts()
@install_types()
async def usdt_cmd(interaction: discord.Interaction):

    await interaction.response.send_message(
        embed=make_embed("usdt", ADDRESSES["usdt"])
    )


# =========================
# VOUCH COMMAND
# =========================

@bot.tree.command(
    name="vouch",
    description="Create a customer vouch"
)
@dm_contexts()
@install_types()
async def vouch_cmd(
    interaction: discord.Interaction,
    message: str
):

    safe_message = message.replace("```", "'''")

    await interaction.response.send_message(
        "**Please copy and paste this vouch:**\n\n"
        f"```{safe_message}```"
    )


# =========================
# TOS COMMAND
# =========================

@bot.tree.command(
    name="tos",
    description="Display the Terms of Service"
)
@dm_contexts()
@install_types()
async def tos_cmd(interaction: discord.Interaction):

    await interaction.response.send_message(TOS)


# =========================
# DEAL CONFIRMATION BUTTON
# =========================

class ConfirmView(discord.ui.View):

    def __init__(self, creator, eligible_users):
        super().__init__(timeout=3600)

        self.creator = creator
        self.eligible_users = set(eligible_users)
        self.confirmed = set()
        self.message = None

    @discord.ui.button(
        label="Confirm (0/2)",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        user_id = interaction.user.id

        # Only other eligible members can confirm
        if user_id not in self.eligible_users:

            await interaction.response.send_message(
                "❌ You are not eligible to confirm this deal.",
                ephemeral=True
            )
            return

        # Prevent duplicate confirmations
        if user_id in self.confirmed:

            await interaction.response.send_message(
                "You have already confirmed this deal.",
                ephemeral=True
            )
            return

        self.confirmed.add(user_id)

        count = len(self.confirmed)

        if count >= 2:

            button.label = "Both Confirmed"
            button.disabled = True

            await interaction.response.edit_message(
                content=(
                    "✅ **DEAL FULLY CONFIRMED!**\n\n"
                    f"Created by: {self.creator.mention}\n\n"
                    "**Both participants confirmed:**\n"
                    + "\n".join(
                        f"✅ <@{uid}>" for uid in self.confirmed
                    )
                ),
                view=self
            )

            self.stop()

        else:

            button.label = f"Confirm ({count}/2)"

            await interaction.response.edit_message(
                content=(
                    "📋 **DEAL CONFIRMATION**\n\n"
                    f"Created by: {self.creator.mention}\n\n"
                    f"✅ {interaction.user.mention} confirmed.\n"
                    "Waiting for one more person to confirm."
                ),
                view=self
            )

    async def on_timeout(self):

        for item in self.children:
            item.disabled = True

        if self.message:

            try:
                await self.message.edit(view=self)

            except discord.HTTPException:
                pass


# =========================
# CONFIRM COMMAND
# =========================

@bot.tree.command(
    name="confirm",
    description="Have two other people confirm the deal"
)
@dm_contexts()
@install_types()
async def confirm_cmd(
    interaction: discord.Interaction,
    deal_information: str
):

    eligible_users = set()

    # SERVER CHANNEL
    if interaction.guild:

        try:
            members = [
                member async for member
                in interaction.guild.fetch_members(limit=None)
            ]

        except discord.HTTPException:
            members = interaction.guild.members

        for member in members:

            if member.id == interaction.user.id:
                continue

            if member.bot:
                continue

            if not interaction.channel.permissions_for(member).view_channel:
                continue

            if not interaction.channel.permissions_for(member).send_messages:
                continue

            eligible_users.add(member.id)

    # GROUP DM
    else:

        recipients = getattr(
            interaction.channel,
            "recipients",
            []
        )

        # Also support regular one-to-one DMs
        recipient = getattr(
            interaction.channel,
            "recipient",
            None
        )

        if recipient:
            recipients = list(recipients) + [recipient]

        for member in recipients:

            if member.id == interaction.user.id:
                continue

            if member.bot:
                continue

            eligible_users.add(member.id)

    # Require two other people
    if len(eligible_users) < 2:

        await interaction.response.send_message(
            "❌ There must be at least two other people "
            "in this chat to start a confirmation.",
            ephemeral=True
        )
        return

    view = ConfirmView(
        interaction.user,
        eligible_users
    )

    await interaction.response.send_message(
        "📋 **DEAL CONFIRMATION**\n\n"
        f"**Created by:** {interaction.user.mention}\n\n"
        f"**Deal Information:**\n{deal_information}\n\n"
        "Two other people in this chat must review "
        "the information and press the button below.\n\n"
        "⚠️ The person who created this confirmation "
        "cannot confirm it.",
        view=view,
        allowed_mentions=discord.AllowedMentions.none()
    )

    view.message = await interaction.original_response()


# =========================
# BITCOIN MONITOR
# =========================

async def check_btc(session):

    url = (
        f"https://mempool.space/api/address/"
        f"{ADDRESSES['btc']}/txs"
    )

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
        raise RuntimeError(
            "DISCORD_TOKEN is missing from your .env file."
        )

    init_database()
    bot.run(TOKEN)
    
