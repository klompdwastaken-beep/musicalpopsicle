import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import yt_dlp
import asyncio
import datetime
import zoneinfo

# --- Configuration & Memory ---
DB_FILE = "subscribers.json"
CONFIG_FILE = "config.json"

# Updated to use your exact custom emoji ID
EXPLICIT_EMOJI = "<:explicit:1531710946332905614>" 

COMMON_SONGS = [
    {"title": "Agora Hills", "artist": "Doja Cat", "url": "https://www.youtube.com/watch?v=z8XyD-4E1lM", "explicit": True},
    {"title": "Beat It", "artist": "Michael Jackson", "url": "https://www.youtube.com/watch?v=oRdxUFDoQe0", "explicit": False}
]

# A helper to let users type simple names instead of the strict IANA format
TZ_ALIASES = {
    "chicago": "America/Chicago",
    "cst": "America/Chicago",
    "cdt": "America/Chicago",
    "new york": "America/New_York",
    "est": "America/New_York",
    "edt": "America/New_York",
    "los angeles": "America/Los_Angeles",
    "pst": "America/Los_Angeles",
    "pdt": "America/Los_Angeles",
    "denver": "America/Denver",
    "mst": "America/Denver",
    "mdt": "America/Denver",
    "london": "Europe/London",
    "gmt": "Europe/London",
    "bst": "Europe/London",
    "utc": "UTC"
}

def resolve_timezone(tz_input):
    """Converts common names like 'Chicago' to 'America/Chicago'."""
    tz_lower = tz_input.lower().strip()
    return TZ_ALIASES.get(tz_lower, tz_input.strip())

def get_bot_token():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as file:
            try:
                data = json.load(file)
                if data.get("token"):
                    return data["token"]
            except json.JSONDecodeError:
                pass 
                
    print("========================================")
    print("🍦 Welcome to MusicalPopsicle Setup! 🍦")
    print("========================================")
    token = input("Enter your Discord Bot Token: ").strip()
    
    with open(CONFIG_FILE, "w") as file:
        json.dump({"token": token}, file)
        
    print("Token saved securely in config.json! Starting bot...")
    return token

# --- Database Setup ---
def load_subscribers():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as file:
            try:
                data = json.load(file)
                if isinstance(data, list):
                    return {str(uid): {"timezone": "UTC"} for uid in data}
                return data
            except json.JSONDecodeError:
                return {}
    return {}

def save_subscribers(subs):
    with open(DB_FILE, "w") as file:
        json.dump(subs, file, indent=2)

# --- Dynamic YouTube Scanner & Common Songs ---
def get_random_song():
    """Scans YouTube dynamically or picks a common song."""
    
    # Exactly 13% chance to pick a pre-defined common song
    if random.random() < 0.13:
        song = random.choice(COMMON_SONGS)
        prefix = f"{EXPLICIT_EMOJI} " if song.get("explicit") else ""
        return f"{prefix}New song: {song['title']} by {song['artist']} {song['url']}"

    # 87% chance to run a dynamic search
    words = ["love", "night", "sun", "moon", "star", "city", "heart", "rain", "fire", "light", 
             "dream", "time", "world", "street", "mind", "soul", "dance", "wild", "free", "summer"]
    genres = ["pop", "rock", "indie", "r&b", "synthwave", "electronic", "lofi", "jazz", "acoustic"]
    
    query = f"{random.choice(words)} {random.choice(genres)} official music video"
    
    ydl_opts = {
        'quiet': True,
        'extract_flat': True, 
        'noplaylist': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch20:{query}", download=False)
            
            if 'entries' in result and result['entries']:
                entries = [e for e in result['entries'] if e]
                if entries:
                    entry = random.choice(entries)
                    
                    url = entry.get('url')
                    if not url or not url.startswith('http'):
                        url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                        
                    title = entry.get('title', 'Unknown Title')
                    artist = entry.get('uploader', 'Unknown Artist')
                    
                    is_explicit = entry.get('age_limit') == 18 or "explicit" in title.lower()
                    prefix = f"{EXPLICIT_EMOJI} " if is_explicit else ""
                    
                    return f"{prefix}New song: {title} by {artist} {url}"
        except Exception as e:
            print(f"Error scanning YouTube: {e}")
            
    return "New song: Never Gonna Give You Up by Rick Astley https://www.youtube.com/watch?v=dQw4w9WgXcQ"

async def get_random_song_async():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_random_song)

# --- Timezone Registration Form (Modal) ---
class TimezoneRegistrationModal(discord.ui.Modal, title="MusicalPopsicle Timezone Setup"):
    tz_input = discord.ui.TextInput(
        label="Enter Your Timezone",
        placeholder="e.g. Chicago, CST, America/Chicago, London...",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Resolve the timezone through our alias helper
        tz_str = resolve_timezone(self.tz_input.value)

        try:
            zoneinfo.ZoneInfo(tz_str)
        except Exception:
            await interaction.response.send_message(
                f"I couldn't recognize `{self.tz_input.value}`. Try a major city like `Chicago`, a zone like `CST`, or an IANA name like `America/Chicago`.", 
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        subs = load_subscribers()
        subs[user_id] = {"timezone": tz_str}
        save_subscribers(subs)

        try:
            await interaction.user.send("Welcome To MusicalPopsicle! You will be sent music daily starting today.")
            await interaction.response.send_message(f"Successfully signed up! Your timezone is set to `{tz_str}`. Check your DMs.", ephemeral=True)
        except discord.Forbidden:
            del subs[user_id]
            save_subscribers(subs)
            await interaction.response.send_message(
                "I couldn't DM you! Enable Direct Messages for this server and try again.", 
                ephemeral=True
            )

# --- Bot Setup ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

# --- Button UI ---
class SubscriptionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Daily Music 🎵", style=discord.ButtonStyle.green, custom_id="musical_popsicle_sub_btn")
    async def subscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        subs = load_subscribers()
        user_id = str(interaction.user.id)

        if user_id in subs:
            await interaction.response.send_message("You are already subscribed to MusicalPopsicle!", ephemeral=True)
            return

        await interaction.response.send_modal(TimezoneRegistrationModal())

# --- Bot Events & Commands ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    bot.add_view(SubscriptionView()) 
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    
    if not daily_music_delivery.is_running():
        daily_music_delivery.start()

@bot.tree.command(name="setup", description="Spawns the MusicalPopsicle sign-up button in this channel.")
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Welcome to MusicalPopsicle! 🍦", 
        description="Click the button below to receive a newly discovered YouTube song delivered right to your DMs every single day.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=SubscriptionView())

@bot.tree.command(name="unsubscribe", description="Unsubscribe from daily MusicalPopsicle song deliveries.")
async def unsubscribe(interaction: discord.Interaction):
    subs = load_subscribers()
    user_id = str(interaction.user.id)

    if user_id not in subs:
        await interaction.response.send_message("You aren't currently subscribed to MusicalPopsicle.", ephemeral=True)
        return

    del subs[user_id]
    save_subscribers(subs)
    await interaction.response.send_message("You have been unsubscribed from MusicalPopsicle. You won't receive daily music anymore.", ephemeral=True)

@bot.tree.command(name="settimezone", description="Update your timezone for daily MusicalPopsicle deliveries.")
@app_commands.describe(timezone="Your timezone (e.g., Chicago, CST, America/Chicago)")
async def settimezone(interaction: discord.Interaction, timezone: str):
    # Resolve the timezone through our alias helper
    tz_str = resolve_timezone(timezone)

    try:
        zoneinfo.ZoneInfo(tz_str)
    except Exception:
        await interaction.response.send_message(
            f"I couldn't recognize `{timezone}`. Try a major city like `Chicago`, a zone like `CST`, or an IANA name like `America/Chicago`.", 
            ephemeral=True
        )
        return

    subs = load_subscribers()
    user_id = str(interaction.user.id)

    if user_id not in subs:
        subs[user_id] = {"timezone": tz_str}
        save_subscribers(subs)
        
        try:
            await interaction.user.send("Welcome To MusicalPopsicle! You will be sent music daily starting today.")
            await interaction.response.send_message(f"Subscribed! Your timezone has been set to `{tz_str}`. You will receive daily songs at 12:00 PM local time.", ephemeral=True)
        except discord.Forbidden:
            del subs[user_id]
            save_subscribers(subs)
            await interaction.response.send_message("I couldn't DM you! Enable Direct Messages for this server and try again.", ephemeral=True)
    else:
        subs[user_id]["timezone"] = tz_str
        save_subscribers(subs)
        await interaction.response.send_message(f"Your timezone has been updated to `{tz_str}`! Daily songs will arrive at 12:00 PM local time.", ephemeral=True)

# --- Background Task ---
@tasks.loop(hours=1)
async def daily_music_delivery():
    subs = load_subscribers()
    if not subs:
        return 

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    song_message = None

    for user_id_str, user_data in list(subs.items()):
        tz_str = user_data.get("timezone", "UTC")
        try:
            user_tz = zoneinfo.ZoneInfo(tz_str)
            user_local_time = now_utc.astimezone(user_tz)

            if user_local_time.hour == 12:
                if song_message is None:
                    print("Scanning YouTube for today's song...")
                    song_message = await get_random_song_async()

                user = await bot.fetch_user(int(user_id_str))
                await user.send(song_message)
                print(f"Sent track to {user_id_str} ({tz_str})")
        except discord.Forbidden:
            print(f"Could not send to user {user_id_str}. DMs disabled.")
        except Exception as e:
            print(f"An error occurred sending to {user_id_str}: {e}")

@daily_music_delivery.before_loop
async def before_delivery():
    await bot.wait_until_ready()
    now = datetime.datetime.now(datetime.timezone.utc)
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    delay = (next_hour - now).total_seconds()
    print(f"Hourly delivery check scheduled. Waiting {int(delay)}s to align with the next hour mark.")
    await asyncio.sleep(delay)

# --- Run the Bot ---
if __name__ == "__main__":
    TOKEN = get_bot_token()
    bot.run(TOKEN)