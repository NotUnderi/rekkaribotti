import os
import re
import requests
from dotenv import load_dotenv
import discord
from discord.ext import commands
import sqlite3

cars = sqlite3.connect('autot.db')
cur = cars.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS autot (id INTEGER PRIMARY KEY, auto TEXT, teho INTEGER, rekkari TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS cache (rekkari TEXT, vinNumber PRIMARY KEY, manufacturer TEXT, modelName TEXT, description TEXT, registerDate TEXT, drive TEXT, fuel TEXT, cylinders INTEGER, cylinderVolumeLiters INTEGER, PowerHp INTEGER, PowerKW INTEGER, seekCount INTEGER)")
cars.commit()

cur.execute("SELECT * FROM cache")
rows = cur.fetchall()
for row in rows:
    print(row)

ban_list = [291874573870432256,117967143731068932]

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

pattern = re.compile(r'\b[a-zA-ZäöÄÖ]{1,3}-?\d{1,3}\b')
strictPattern = re.compile(r'\b[a-zA-ZäöÄÖ]{3}-?\d{3}\b')

def get_cached_rekkari():
    cur.execute("SELECT rekkari FROM cache")
    rekkarit = cur.fetchall()
    return [rekkari[0] for rekkari in rekkarit]
cached_list = get_cached_rekkari()
print(cached_list)
def get_all_ids():
    cur.execute("SELECT id FROM autot")
    ids = cur.fetchall()
    return [id[0] for id in ids]
id_list = get_all_ids()

def get_licenseplate(rekkari, id, large):
    message = []
    if rekkari.group() in cached_list:
        
        cur.execute("SELECT * FROM cache WHERE rekkari = ?", (rekkari.group(),))
        rekkariJson = cur.fetchone()
        cur.execute("UPDATE cache SET seekCount = seekCount + 1 WHERE rekkari = ?", (rekkari.group(),))
        cars.commit()
   # else:
   #     try:
   #         rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
   #         rekkariJson = rekkariRequest.json()
   #         cur2.execute("INSERT INTO cache (rekkari, vinNumber, manufacturer, modelName, description, registerDate, drive, fuel, cylinders, cylinderVolumeLiters, PowerHp, PowerKW, seekCount) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (rekkari.group(),rekkariJson["vinNumber"], rekkariJson["manufacturer"], rekkariJson["modelName"], rekkariJson["description"], rekkariJson["registerDate"], rekkariJson["drive"], rekkariJson["fuel"], rekkariJson["cylinders"], rekkariJson["cylinderVolumeLiters"], rekkariJson["powerHp"], rekkariJson["powerKW"], 1))
   #         cache.commit()
   #         cached_list.append(rekkari.group())

#        except Exception as e:
 #           print(e)
        
    message.append(rekkariJson["Manufacturer"] + " " + rekkariJson["ModelName"] + " " + rekkariJson["description"])
    message.append(f"Teho : **{rekkariJson['powerHp']} hv**")
    message.append(f"Sylinteritilavuus: **{rekkariJson['cylinderVolumeLiters']}**")
    message.append(f"Sylinterimäärä: **{rekkariJson['cylinders']}**")
    if large == True:
        message.append(f"Rekisteröintipäivä: **{rekkariJson['registerDate']}**")
        message.append(f"Vetotapa: **{rekkariJson['drive']}**")
        message.append(f"Polttoaine: **{rekkariJson['fuel']}**")
        message.append(f"VIN: **{rekkariJson['vinNumber']}**")
        message.append(f"Hakuja: {rekkariJson['seekCount']}")

    if id in id_list:
        cur.execute("SELECT teho FROM autot WHERE id = ?", (message.author.id,))
        author_power = cur.fetchone()[0]
        rekkari_power = rekkariJson["powerHp"]
        diff = (author_power / rekkari_power)
        message.append(f"Autosi teho: {author_power} hv\nRekkarin teho: **{rekkari_power} hv**\nTehoero: **{diff:.2f}x**")
    return('\n'.join(message))
    


117967143731068932

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
            get_licenseplate(rekkari, ctx.author.id, False)
            rekkariJson = rekkariRequest.json()
            cur.execute("SELECT * FROM autot WHERE id = ?", (ctx.author.id,))
            print(ctx.author.id)
            if cur.fetchone():
                cur.execute("UPDATE autot SET auto = ?, teho = ? WHERE id = ?", (rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"], ctx.author.id))
                cars.commit()
                await ctx.send("Auto päivitetty tietokannassa \n ")
                return
            auto = [ctx.author.id, rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"]]
            cur.execute("INSERT INTO autot VALUES( ?, ?, ?)",auto)
            await ctx.send(f"Auto {rekkariJson['manufacturer']} {rekkariJson['modelName']} lisätty tietokantaan")
            cars.commit()
            id_list = get_all_ids()
        except Exception as e:
            await ctx.send("Rekkaria ei löytynyt")
            await ctx.send(e)
    else:
        ctx.send("Virheellinen rekisterikilpi")
@bot.command()
async def autonteho(ctx):
    try:
        if ctx.author.id in ban_list:
            await ctx.send("Kys nigga :D autos on mopo")
            return
        if ctx.author.id in id_list:
            new_power = int(ctx.message.content[11:])
            cur.execute("UPDATE autot SET teho = ? WHERE id = ?", (new_power, ctx.author.id))
            cars.commit()
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
            await ctx.send(get_licenseplate())
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
            await message.channel.send(get_licenseplate(rekkari, message.author.id, False))
        except Exception as e:
            print("Rekkaria ei löytynyt")
            print(e)

    await bot.process_commands(message)



bot.run(TOKEN)
