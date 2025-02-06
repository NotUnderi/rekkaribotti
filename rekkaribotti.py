import os
import re
import requests
from dotenv import load_dotenv
import discord
from discord.ext import commands
import sqlite3

con = sqlite3.connect('autot.db')
cur = con.cursor()

  
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True

pattern = re.compile(r'\b[a-zA-Z]{1,3}-?\d{1,3}\b')
strictPattern = re.compile(r'\b[a-zA-Z]{3}-?\d{3}\b')

def get_all_ids():
    cur.execute("SELECT id FROM autot")
    ids = cur.fetchall()
    return [id[0] for id in ids]

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')
@bot.command()
async def auto(ctx):
    print(ctx.author.id)
    rekkari = pattern.search(ctx.message.content)
    if rekkari:
        try:
            rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
            rekkariJson = rekkariRequest.json()
            cur.execute("SELECT * FROM autot WHERE id = ?", (ctx.author.id,))
            print(ctx.author.id)
            if cur.fetchone():
                cur.execute("UPDATE autot SET auto = ?, teho = ? WHERE id = ?", (rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"], ctx.author.id))
                con.commit()
                await ctx.send("Auto päivitetty tietokannassa \n ")
                return
            auto = [ctx.author.id, rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"]]
            cur.execute("INSERT INTO autot VALUES( ?, ?, ?)",auto)
            await ctx.send(f"Auto {rekkariJson['manufacturer']} {rekkariJson['modelName']} lisätty tietokantaan")
            con.commit()
        except Exception as e:
            await ctx.send("Rekkaria ei löytynyt")
            await ctx.send(e)
    else:
        ctx.send("Virheellinen rekisterikilpi")
@bot.command()
async def autonteho(ctx):
    try:
        if ctx.author.id in get_all_ids():
            new_power = int(ctx.message.content[11:])
            cur.execute("UPDATE autot SET teho = ? WHERE id = ?", (new_power, ctx.author.id))
            con.commit()
            await ctx.send(f"Teho päivitetty: {new_power} hv")
            return
        else:
            await ctx.send("Autoa ei löytynyt")
    except Exception as e:
        await ctx.send("Anna uusi teholukema numeroina")
        await ctx.send(e)


@bot.command()
async def r(ctx):
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
    strictPattern = re.compile(r'\b[a-zA-Z]{3}-?\d{3}\b')
    rekkari = strictPattern.search(message.content)
    if rekkari:
        try:
            rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
            print(rekkariRequest)
            rekkariJson = rekkariRequest.json()
            await message.channel.send('\n'.join([f"{alala[key]}: **{rekkariJson.get(key, 'N/A')}**" for key in alala]))
            if message.author.id in get_all_ids():
                cur.execute("SELECT teho FROM autot WHERE id = ?", (message.author.id,))
                author_power = cur.fetchone()[0]
                rekkari_power = rekkariJson["powerHp"]
                percentage_difference = ((author_power - rekkari_power) / author_power) * 100
                await message.channel.send(f"Autosi teho: {author_power} hv\nRekkarin teho: {rekkari_power} hv\nTehoero: {percentage_difference:.2f}%")
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
