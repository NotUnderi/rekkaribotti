import sys,os
import re
import requests
from dotenv import load_dotenv
import discord
from discord.ext import commands
import sqlite3
import datetime
from collections import defaultdict
import pytz

eest = pytz.timezone('Europe/Helsinki')

cars = sqlite3.connect('autot.db')
cars.row_factory = sqlite3.Row
cur = cars.cursor()

cur.execute("CREATE TABLE IF NOT EXISTS autot (id INTEGER PRIMARY KEY, auto TEXT, teho INTEGER, rekkari TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS autot_messages (id INTEGER PRIMARY KEY, message TEXT, vinNumber TEXT, time TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS cache (rekkari TEXT, vinNumber PRIMARY KEY, manufacturer TEXT, modelName TEXT, description TEXT, registerDate TEXT, drive TEXT, fuel TEXT, cylinders INTEGER, cylinderVolumeLiters INTEGER, powerHp INTEGER, powerKW INTEGER)")
cars.commit()

cur.execute("SELECT * FROM cache")

rows = cur.fetchall()
for row in rows:
    print(row)

ban_list = [291874573870432256,117967143731068932]
ban_check_timestamps = defaultdict(list)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

pattern = re.compile(r'\b[a-zA-ZäöÄÖ]{1,3}-?\d{1,3}\b')
strictPattern = re.compile(r'\b[a-zA-ZäöÄÖ]{3}-?\d{3}\b')

def get_cached_vin():
    cur.execute("SELECT vinNumber FROM cache")
    VINs = cur.fetchall()
    return [vinNumber[0] for vinNumber in VINs]
cached_vin_list = get_cached_vin()

def get_cached_rekkari():
    cur.execute("SELECT rekkari FROM cache")
    rekkarit = cur.fetchall()
    return [rekkari[0] for rekkari in rekkarit]
cached_rekkari_list = get_cached_rekkari()

def get_all_ids():
    cur.execute("SELECT id FROM autot")
    ids = cur.fetchall()
    return [id[0] for id in ids]
id_list = get_all_ids()

def get_licenseplate(rekkari:str, id:int, large:bool, info:bool, full_message:str|None=None) -> str | dict:
    message = []

    if is_banned(id):  
        record_check(id)
        return "Homonesto aktivoitu"
    record_check(id)

    if rekkari.group() in cached_rekkari_list:
        
        cur.execute("SELECT * FROM cache WHERE rekkari = ?", (rekkari.group(),))
        rekkariJson = dict(cur.fetchone())
        if full_message is not None:
            cur.execute("INSERT INTO autot_messages (message, vinNumber, time) VALUES (?, ?, ?)",(full_message, rekkariJson["vinNumber"], datetime.datetime.now(eest)))
            cars.commit()
    else:
        rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
        if rekkariRequest.status_code == 200:
            rekkariJson = rekkariRequest.json()
            if rekkariJson["vinNumber"] in cached_vin_list:
                cur.execute("SELECT * FROM cache WHERE vinNumber = ?", (rekkariJson["vinNumber"],))
                rekkariJson = dict(cur.fetchone())
                if full_message is not None:
                    cur.execute("INSERT INTO autot_messages (message, vinNumber, time) VALUES (?, ?, ?)",(full_message, rekkariJson["vinNumber"], datetime.datetime.now(eest)))
                cars.commit()
            else:
                cur.execute("INSERT INTO cache (rekkari, vinNumber, manufacturer, modelName, description, registerDate, drive, fuel, cylinders, cylinderVolumeLiters, PowerHp, PowerKW) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (rekkari.group(),rekkariJson["vinNumber"], rekkariJson["manufacturer"], rekkariJson["modelName"], rekkariJson["description"], rekkariJson["registerDate"], rekkariJson["drive"], rekkariJson["fuel"], rekkariJson["cylinders"], rekkariJson["cylinderVolumeLiters"], rekkariJson["powerHp"], rekkariJson["powerKW"]))
                cars.commit()
                cached_vin_list.append(rekkariJson["vinNumber"])
        else:
            message.append("Rekkaria ei löytynyt")
            message.append("Palvelin antoi vastauksen: " + str(rekkariRequest.status_code))
            return('\n'.join(message))
    cur.execute("SELECT time, message FROM autot_messages WHERE vinNumber = ? ORDER BY time DESC LIMIT 5", (rekkariJson["vinNumber"],))
    autot_messages = [dict(x) for x in cur.fetchall()]
    rekkariJson["autot_messages"] = autot_messages
    cur.execute("SELECT COUNT(*) FROM autot_messages WHERE vinNumber = ?", (rekkariJson["vinNumber"],))
    rekkariJson['total_mentions'] = cur.fetchone()['COUNT(*)']
    if info : return rekkariJson

    message.append(rekkariJson["manufacturer"] + " " + rekkariJson["modelName"] + " " + rekkariJson["description"])
    message.append(f"Teho : **{rekkariJson['powerHp']} hv**")
    message.append(f"Sylinteritilavuus: **{rekkariJson['cylinderVolumeLiters']}**")
    message.append(f"Sylinterimäärä: **{rekkariJson['cylinders']}**")
    if large == True:
        message.append(f"Rekisteröintipäivä: **{rekkariJson['registerDate']}**")
        message.append(f"Vetotapa: **{rekkariJson['drive']}**")
        message.append(f"Polttoaine: **{rekkariJson['fuel']}**")
        message.append(f"VIN: **{rekkariJson['vinNumber']}**")
        if rekkariJson["autot_messages"]:
            message.append(f"Hakukertoja yhteensä:**{rekkariJson['total_mentions']}**")
            message.append(f"**Viimeiset haut:**")
            for autot_message in rekkariJson["autot_messages"]:
                last_seen = datetime.datetime.fromisoformat(autot_message['time'])
                human_readable_time = last_seen.strftime("%d.%m.%Y %H:%M:%S")
                message.append(f"**{human_readable_time}**: {autot_message['message']}")

    if id in id_list:
        cur.execute("SELECT teho FROM autot WHERE id = ?", (id,))
        author_power = cur.fetchone()[0]
        rekkari_power = rekkariJson["powerHp"]
        diff = (author_power / rekkari_power)
        message.append(f"Rekkarin teho: **{rekkari_power} hv**\nTehoero: **{diff:.2f}x**\nAutosi teho: {author_power} hv")
    return('\n'.join(message))
    


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
    if id == 117967143731068932: rekkari = pattern.search("zgt800")
    if id == 291874573870432256: rekkari = pattern.search("vei475")
    if rekkari:
        try:
            rekkari = pattern.search(normalize__rekkari(rekkari.group()))
            rekkariJson = get_licenseplate(rekkari, ctx.author.id, False, True, "[Asetettu omaksi autoksi]")
            cur.execute("SELECT * FROM autot WHERE id = ?", (ctx.author.id,))
            print(ctx.author.id)
            if cur.fetchone():
                cur.execute("UPDATE autot SET auto = ?, teho = ?, rekkari =? WHERE id = ?", (rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"],rekkari.group(), ctx.author.id))
                cars.commit()
                await ctx.send("Auto päivitetty tietokannassa \n ")
                return
            auto = [ctx.author.id, rekkariJson["manufacturer"] + "" + rekkariJson["modelName"], rekkariJson["powerHp"], rekkari.group()]
            cur.execute("INSERT INTO autot VALUES( ?, ?, ?, ?)",auto)
            await ctx.send(f"Auto {rekkariJson['manufacturer']} {rekkariJson['modelName']} lisätty tietokantaan")
            cars.commit()
            id_list.append(ctx.author.id)
        except Exception as e:
            await ctx.send("Rekkaria ei löytynyt")
            await ctx.send(e)
    else:
        ctx.send("Virheellinen rekisterikilpi")


@bot.command()
async def autonteho(ctx):
    try:
        if ctx.author.id in ban_list:  
            await ctx.send("Kys :D autos on mopo")
            record_check(ctx.author.id)
            return        
            
        if ctx.author.id in id_list:
            new_power = int(ctx.message.content[11:])
            cur.execute("UPDATE autot SET teho = ? WHERE id = ?", (new_power, ctx.message.author.id))
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
        rekkari = pattern.search(normalize__rekkari(rekkari.group()))
        await ctx.send(get_licenseplate(rekkari,ctx.author.id, True, False,ctx.message.author.name + " haki tiedot"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    strictPattern = re.compile(r'\b[a-zA-Z]{3}-?\d{3}\b')
    rekkari = strictPattern.search(message.content)
    if rekkari and not message.content.startswith('!'):
            if True :          #manually set to true if old plates exist and run once
                update_cached_rekkari()
                update_owned_rekkari()
            rekkari = strictPattern.search(normalize__rekkari(rekkari.group()))
            await message.channel.send(get_licenseplate(rekkari, message.author.id, False, False, message.author.name + ": " + message.content[:50]))

    await bot.process_commands(message)

def is_banned(id):
    """Check if the user in the ban_list has exceeded 10 license plate requests in the last hour."""
    if id not in ban_list:
        return False  # Only users in the ban_list are restricted

    current_time = datetime.datetime.now(eest)
    # Get the list of timestamps for the user
    timestamps = ban_check_timestamps[id]

    # Remove timestamps older than 1 hour
    ban_check_timestamps[id] = [t for t in timestamps if (current_time - t).total_seconds() < 36000]

    # Check if the user has made 10 or more checks in the last hour
    if len(ban_check_timestamps[id]) >= 10:
        return True

    return False

def record_check(id):
    """Record a license plate check for users in the ban_list."""
    if id in ban_list:
        current_time = datetime.datetime.now(eest)
        ban_check_timestamps[id].append(current_time)

def normalize__rekkari(rekkari:str) -> str:
    rekkari = rekkari.upper()
    if re.compile(r'\b-\b').search(rekkari) != None:
        return rekkari
    rekkari = re.sub(r'([A-Za-z]+)(\d+)', r'\1-\2', rekkari)
    return rekkari

def update_cached_rekkari():
    cur.execute(f"SELECT vinNumber, rekkari FROM cache")
    rows = cur.fetchall()
    print(rows)
    for row in rows:
        row_dict = dict(row)  # Convert sqlite3.Row to a dictionary
        record_id = row_dict["vinNumber"]
        plate = row_dict["rekkari"]

        if plate and isinstance(plate, str):
            normalized_plate = normalize__rekkari(plate)
            if plate != normalized_plate:
                cur.execute(f"UPDATE cache SET rekkari = ? WHERE vinNumber = ?", (normalized_plate, record_id))
        
    cars.commit()
def update_owned_rekkari():
    cur.execute(f"SELECT id, rekkari FROM autot")
    rows = cur.fetchall()
    print(rows)
    for row in rows:
        row_dict = dict(row) 
        record_id = row_dict["id"]
        plate = row_dict["rekkari"]

        if plate and isinstance(plate, str):
            normalized_plate = normalize__rekkari(plate)
            if plate != normalized_plate:
                cur.execute(f"UPDATE autot SET rekkari = ? WHERE id = ?", (normalized_plate, record_id))
        
    cars.commit()

bot.run(TOKEN)
