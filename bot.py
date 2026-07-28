import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import yt_dlp
import asyncio

# --- Configuration & Memory ---
DB_FILE = "subscribers.json"
CONFIG_FILE = "config.json"

def get_bot_token():
    """Checks for a saved token, or asks the user for one and saves it."""
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
    token = input("Please enter your Discord Bot Token: ").strip()
    
    with open(CONFIG_FILE, "w") as file:
        json.dump({"token": token}, file)
        
    print("Token saved securely in config.json! Starting bot...")
    return token

# --- Database Setup ---
def load_subscribers():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as file:
            return json.load(file)
    return []

def save_subscribers(subs):
    with open(DB_FILE, "w") as file:
        json.dump(subs, file)

# --- Dynamic YouTube Scanner ---
def get_random_song():
    """Scans YouTube dynamically for a random song."""
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
                    
                    return f"New song: {title} by {artist} {url}"
        except Exception as e:
            print(f"Error scanning YouTube: {e}")
            
    return "New song: Never Gonna Give You Up by Rick Astley https://www.youtube.com/watch?v=dQw4w9WgXcQ"

async def get_random_song_async():
    """Runs the YouTube search in a background thread so the bot doesn't freeze."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_random_song)

# --- Bot Setup ---
# Message Content Intent is completely removed since slash commands don't need it!
intents = discord.Intents.default()
# We use when_mentioned to fulfill the required argument without using a text prefix like "!"
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

# --- Button UI ---
class SubscriptionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Daily Music 🎵", style=discord.ButtonStyle.green, custom_id="musical_popsicle_sub_btn")
    async def subscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        subs = load_subscribers()
        user_id = interaction.user.id

        if user_id in subs:
            await interaction.response.send_message("You are already subscribed to MusicalPopsicle!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        subs.append(user_id)
        save_subscribers(subs)

        try:
            await interaction.user.send("Welcome To MusicalPopsicle! You will be sent music daily starting today.")
            
            first_song = await get_random_song_async()
            await interaction.user.send(first_song)
            
            await interaction.followup.send("You've been successfully signed up! Check your DMs.", ephemeral=True)
            
        except discord.Forbidden:
            subs.remove(user_id)
            save_subscribers(subs)
            await interaction.followup.send("I couldn't DM you! Please enable Direct Messages for this server and try again.", ephemeral=True)

# --- Bot Events & Slash Commands ---
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

# --- Background Task ---
@tasks.loop(hours=24)
async def daily_music_delivery():
    subs = load_subscribers()
    if not subs:
        return 

    print("Scanning YouTube for today's song...")
    song_message = await get_random_song_async()
    print(f"Sending today's track: {song_message}")

    for user_id in subs:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(song_message)
        except discord.Forbidden:
            print(f"Could not send to user {user_id}. DMs are likely disabled.")
        except Exception as e:
            print(f"An error occurred sending to {user_id}: {e}")

@daily_music_delivery.before_loop
async def before_delivery():
    await bot.wait_until_ready()

# --- Run the Bot ---
if __name__ == "__main__":
    TOKEN = get_bot_token()
    bot.run(TOKEN)