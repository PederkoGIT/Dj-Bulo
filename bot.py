#!/usr/bin/env python3

import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import sqlite3
import yt_dlp
import asyncio
from collections import deque
import random
import time


async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)

fruits = [":tangerine:", ":lemon:", ":watermelon:", ":grapes:", ":cherries:", ":pineapple:"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

profanity = ["asdasdasdk"]

def create_user_table():
    connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS "users_per_guild" (
            "user_id"	INTEGER,
            "warning_count"	INTEGER,
            "guild_id"	INTEGER,
            PRIMARY KEY("user_id","guild_id")
        )
    """)

    connection.commit()
    connection.close()

create_user_table()

def increase_and_get_warnings(user_id: int, guild_id: int):
    connection = sqlite3.connect(f"{BASE_DIR}\\user_warnings.db")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT warning_count 
        FROM users_per_guild
        WHERE (user_id = ?) AND (guild_id = ?);
    """, (user_id, guild_id))

    result = cursor.fetchone()

    if result == None:
        cursor.execute("""
            INSERT INTO users_per_guild(user_id, warning_count, guild_id)
            VALUES (?, 1, ?);
        """, (user_id, guild_id))
        
        connection.commit()
        connection.close()

        return 1

    cursor.execute("""
        UPDATE users_per_guild
        SET warning_count = ?
        WHERE (user_id = ?) AND (guild_id = ?);
    """, (result[0] + 1, user_id, guild_id))

    connection.commit()
    connection.close()
    
    return result[0] + 1






load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("TEST_ID")

SONG_QUEUES = {}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, activity=discord.Activity(type=discord.ActivityType.listening, name="tvoje songy 🎺"))

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is online!")


'''
@bot.event
async def on_message(msg):
    if msg.author.id != bot.user.id:
        for word in profanity:
            if word.lower() in msg.content.lower():
                num_warnings = increase_and_get_warnings(user_id=msg.author.id, guild_id=msg.guild.id)
                
                if num_warnings >= 3:
                    until = utcnow() + timedelta(seconds=20)
                    await msg.author.timeout(until, reason="Timed out for 20 seconds")
                    await msg.channel.send(f"{msg.author.mention} has been timed out for 20 seconds.")
                else:
                    await msg.channel.send(f"Warnings: {num_warnings}/3 {msg.author.mention}")
                    await msg.delete()

    await bot.process_commands(msg)
'''

class MusicControlView(discord.ui.View):
    def __init__(self, voice_client):
        super().__init__(timeout=None)
        self.voice_client = voice_client

    @discord.ui.button(label="SKIP ⏭️", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.voice or interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.response.send_message("Nemôžeš skipovať")
            return

        if self.voice_client.is_playing():
            self.voice_client.stop()
            await interaction.response.send_message("Skipnuté.", delete_after=5)

            button.disabled = True
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.send_message("Nehrám nič.")

    @discord.ui.button(label="PAUSE/PLAY ⏯️", style=discord.ButtonStyle.secondary)
    async def play_pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("Pauznuté", delete_after=3)
        elif self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("Hrám ďalej", delete_after=3)
        else:
            await interaction.response.send_message("Nič nehrá.", ephemeral=True)



@bot.tree.command(name="skip", description="Preskoč songu")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipnuté.", delete_after=5)
    else:
        await interaction.response.send_message("Nehrám nič.")


@bot.tree.command(name="pause", description="Pauzni songu.")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        return await interaction.response.send_message("Nie som nikde pripojený..")

    if not voice_client.is_playing():
        return await interaction.response.send_message("Nič nehrá more.")
    
    voice_client.pause()
    await interaction.response.send_message("Blástenie pozastavené!")


@bot.tree.command(name="resume", description="Pokračuj v blástení.")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        return await interaction.response.send_message("Nie som nikde pripojený.")

    if not voice_client.is_paused():
        return await interaction.response.send_message("Nie som zastavený")
    
    voice_client.resume()
    await interaction.response.send_message("Blástim ďalej!")


@bot.tree.command(name="stop", description="Zastav blástenie a zruš queue")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        await interaction.followup.send("Nie som nikde pripojený.")
        return

    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()

    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    await interaction.followup.send("Vypnuté a odpojené!")

    await voice_client.disconnect()

@bot.tree.command(name="queue", description="Zobraz queue")
async def queue(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in SONG_QUEUES and SONG_QUEUES[guild_id_str]:
        i = 1
        msg = ""
        for url, title in SONG_QUEUES[guild_id_str]:
            msg += f"**{i}. {title}**\n"
            i += 1
        await interaction.response.send_message(msg)
    else:
        await interaction.response.send_message("Queue je prázdna.")

@bot.tree.command(name="play", description="Zahrám song alebo ho pridám do queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()

    voice_channel = None
    try:
        voice_channel = interaction.user.voice.channel
    
    except:
        await interaction.followup.send("Nejsi v roomke, geňo.")
        return
        

    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect(timeout=20.0, reconnect=True)
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    while not voice_client.is_connected() and count < 10:
        await asyncio.sleep(0.5)
        count += 1

    if not voice_client.is_connected():
        await interaction.followup.send("Pablo sa nevie napojiť sadge")
        return

    ydl_options = {
        "format": "bestaudio[ext=webm][asr=48000]/bestaudio/best",
        "noplaylist": True,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "cookiefile": "cookies.txt"
    }

    query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])

    if not tracks:
        await interaction.followup.send("Hovno som našiel.")
        return

    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")

    guild_id = str(interaction.guild_id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()

    SONG_QUEUES[guild_id].append((audio_url, title))

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Pridané do queue: **{title}**")
    else:
        try:
            await interaction.delete_original_response()
        except:
            pass
        await play_next_song(voice_client, guild_id, interaction.channel)


async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }

        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="ffmpeg")

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)

        voice_client.play(source, after=after_play)

        view = MusicControlView(voice_client)

        asyncio.create_task(channel.send(f"Práve blástim: **{title}**", view=view))
    else:
        await asyncio.sleep(120)

        if voice_client.is_connected():
            if not SONG_QUEUES[guild_id] and not voice_client.is_playing():
                await voice_client.disconnect()
                await channel.send("Odchádzam!")
                SONG_QUEUES[guild_id] = deque()



@bot.tree.command(name="slot", description="Točka ovocka")
async def slot(interaction: discord.Interaction):
    await interaction.response.defer()
    first = random.randrange(0, 6)
    second = random.randrange(0, 6)
    third = random.randrange(0, 6)

    msg = await interaction.followup.send("**Točím**", wait=True)
    await asyncio.sleep(0.5)

    for i in range(6):
        new_fruits = f"{fruits[random.randrange(0, 6)]} {fruits[random.randrange(0, 6)]} {fruits[random.randrange(0, 6)]}"

        await msg.edit(content=new_fruits)
        await asyncio.sleep(0.25)

    for i in range(6):
        new_fruits = f"{fruits[first]} {fruits[random.randrange(0, 6)]} {fruits[random.randrange(0, 6)]}"

        await msg.edit(content=new_fruits)
        await asyncio.sleep(0.25)

    for i in range(6):
        new_fruits = f"{fruits[first]} {fruits[second]} {fruits[random.randrange(0, 6)]}"

        await msg.edit(content=new_fruits)
        await asyncio.sleep(0.25)

    new_fruits = f"{fruits[first]} {fruits[second]} {fruits[third]}"

    await msg.edit(content=new_fruits)

    if first == second == third:
        if first == 0:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 10 goonov!!")
        elif first == 1:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 50 goonov!!")
        elif first == 2:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 100 goonov!!")
        elif first == 3:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 250 goonov!!")
        elif first == 4:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 500 goonov!!")
        elif first == 5:
            await interaction.followup.send(f"{interaction.user.mention} Vyhrávaš 1000 goonov!!")
    else:
        await interaction.followup.send(f"{interaction.user.mention} Vyhral/a si prd")

bot.run(TOKEN)
