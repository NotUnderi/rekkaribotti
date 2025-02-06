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

@bot.command()
async def r(ctx):
    pattern = re.compile(r'\b[a-zA-Z]{1,3}-?\d{1,3}\b')
    rekkari = pattern.search(ctx.message.content)
    if rekkari:
        try:
            rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
            rekkariJson = rekkariRequest.json()
            await ctx.send('\n'.join([f"{alala[key]}: **{rekkariJson.get(key, 'N/A')}**" for key in alala]))
            print(rekkariJson["manufacturer"])
        except Exception:
            await ctx.send("Rekkaria ei löytynyt")
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    strictPattern =  pattern = re.compile(r'\b[a-zA-Z]{3}-?\d{3}\b')
    rekkari = strictPattern.search(message.content)
    if rekkari:
        try:
            rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
            print(rekkariRequest)
            rekkariJson = rekkariRequest.json()
            await message.channel.send('\n'.join([f"{alala[key]}: **{rekkariJson.get(key, 'N/A')}**" for key in alala]))
            print(rekkariJson["manufacturer"])
        except Exception:
            print("Rekkaria ei löytynyt")

    await bot.process_commands(message)



alala = {
    "manufacturer": "Valmistaja",
    "modelName": "Malli",
    "description": "Kuvaus",
    "registerDate": "Rekisteröintipäivä",
    "drive": "Vetotapa",
    "fuel": "Polttoaine",
    "cylinders": "Sylinterit",
    "cylinderVolumeLiters": "Sylinteritilavuus",
    "powerHp": "Teho (hv)",
    "powerKW": "Teho (kW)"
}

bot.run(TOKEN)
