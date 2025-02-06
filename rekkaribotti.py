import os
import re
import requests
from dotenv import load_dotenv
import discord
from discord.ext import commands


                         
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    pattern = re.compile(r'\b[a-zA-Z]{2,3}-?\d{2,3}\b')
    rekkari = pattern.search(message.content)
    alala = ["manufacturer","modelName","description","registerDate","drive","fuel","cylinders","cylinderVolumeLiters","powerHp","powerKW"]
    if rekkari:
        try:
            rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
            print(rekkariRequest)
            rekkariJson = rekkariRequest.json()
            await message.channel.send('\n'.join([f"{key}: {rekkariJson.get(key, 'N/A')}" for key in alala]))
            print(rekkariJson["manufacturer"])
        except Exception:
            await message.channel.send("Rekkaria ei löytynyt")

    await bot.process_commands(message)

bot.run(TOKEN)