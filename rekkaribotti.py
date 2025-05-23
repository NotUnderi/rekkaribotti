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
import yaml

eest = pytz.timezone('Europe/Helsinki')

with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

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

our_cars = config['cars']["ignored_cars"]
ban_list = config['ban']['banned_users']
ban_check_timestamps = defaultdict(list)

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

if TOKEN is None:
    raise ValueError("No DISCORD_TOKEN found in environment variables")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')

pattern = re.compile(r'\b[a-zA-ZäöÄÖ]{1,3}-?\d{1,3}\b')
strictPattern = re.compile(r'\b[a-zA-ZäöÄÖ]{3}-?\d{3}\b')


def get_cached_rekkari():
    cur.execute("SELECT rekkari FROM cache")
    rekkarit = cur.fetchall()
    return [rekkari[0] for rekkari in rekkarit]
cached_rekkari_list = get_cached_rekkari()
print(cached_rekkari_list)
def get_all_ids():
    cur.execute("SELECT id FROM autot")
    ids = cur.fetchall()
    return [id[0] for id in ids]
id_list = get_all_ids()

def get_licenseplate(rekkari:str, id:int, large:bool, info:bool, full_message:str|None=None) -> str | dict:
    message = []

    if rekkari.group() in cached_rekkari_list:
        
        cur.execute("SELECT * FROM cache WHERE rekkari = ?", (rekkari.group(),))
        rekkariJson = dict(cur.fetchone())
        
    else:
        rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari.group()}?market=3&language=FI")
        if rekkariRequest.status_code == 200:
            rekkariJson = rekkariRequest.json()
            cur.execute("INSERT INTO cache (rekkari, vinNumber, manufacturer, modelName, description, registerDate, drive, fuel, cylinders, cylinderVolumeLiters, powerHp, powerKW) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (rekkari.group(),rekkariJson["vinNumber"], rekkariJson["manufacturer"], rekkariJson["modelName"], rekkariJson["description"], rekkariJson["registerDate"], rekkariJson["drive"], rekkariJson["fuel"], rekkariJson["cylinders"], rekkariJson["cylinderVolumeLiters"], rekkariJson["powerHp"], rekkariJson["powerKW"]))
            cars.commit()
            cached_rekkari_list.append(rekkari.group())
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

    message.append(rekkariJson["manufacturer"] + " " + rekkariJson["modelName"] + " " + rekkariJson["description"] + " " + rekkariJson["registerDate"][:4])
    message.append(f"Teho : **{rekkariJson['powerHp']} hv**")
    message.append(f"Sylinteritilavuus: **{rekkariJson['cylinderVolumeLiters']}**")
    message.append(f"Sylinterimäärä: **{rekkariJson['cylinders']}**")

    if large == True:
        message.append(f"Rekisteröintipäivä: **{rekkariJson['registerDate']}**")
        message.append(f"Vetotapa: **{rekkariJson['drive']}**")
        message.append(f"Polttoaine: **{rekkariJson['fuel']}**")
        message.append(f"VIN: **{rekkariJson['vinNumber']}**")
        if rekkariJson["autot_messages"]:
            message.append(f"**Viimeiset haut:**")
            for autot_message in rekkariJson["autot_messages"]:
                last_seen = datetime.datetime.fromisoformat(autot_message['time'])
                human_readable_time = last_seen.strftime("%d.%m.%Y %H:%M:%S")
                message.append(f"**{human_readable_time}**: {autot_message['message']}")
    message.append(f"Hakukertoja yhteensä:**{rekkariJson['total_mentions']}**")

    if id in id_list:
        cur.execute("SELECT teho FROM autot WHERE id = ?", (id,))
        author_power = cur.fetchone()[0]
        rekkari_power = rekkariJson["powerHp"]
        diff = (author_power / rekkari_power)
        message.append(f"Tehoero: **{diff:.2f}x**\nAutosi teho: {author_power} hv")
    if full_message is not None:
            cur.execute("INSERT INTO autot_messages (message, vinNumber, time) VALUES (?, ?, ?)",(full_message, rekkariJson["vinNumber"], datetime.datetime.now(eest)))
            cars.commit()
    return('\n'.join(message))
    


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.command()
async def help(ctx):
    message = []
    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return     
    message.append("**Komennot:**")
    message.append("!r <abc123> - Hae auton tiedot")
    message.append("!auto <abc123> - Aseta oma autosi")
    message.append("!mopo 123 - Kuinka moni auto ylittää annetun tehon")
    message.append("!autonteho 123 - Aseta oma autosi teho")
    message.append("!stats - Hae tilastotietoja")
    await ctx.send('\n'.join(message))


@bot.command()
async def hae(ctx):
    message = []
    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return 
    record_check(id)
    cur.execute("SELECT rekkari FROM cache WHERE rekkari LIKE ?", ('%'+ctx.message.content[5:]+'%',))
    rows = cur.fetchall()
    if not rows:
        message.append("Ei hakutuloksia rekkareista")
        await ctx.send('\n'.join(message))
        return
    message.append("**Hakutulokset rekkareista:**")
    for row in rows:
        message.append(row[0])
    #cur.execute("SELECT message,vinNumber FROM autot_messages WHERE message LIKE ? LIMIT 1", ('%'+ctx.message.content[5:]+'%',))
    #rows = cur.fetchall()
    #if not rows:
    #    message.append("Ei hakutuloksia viesteistä")
    #    await ctx.send('\n'.join(message))
    #    return
    #message.append("\n**Hakutulokset viesteistä:**")
    #for row in rows:
    #    cur.execute("SELECT rekkari FROM cache WHERE vinNumber = ?", (row[1],))
    #    rekkari = cur.fetchone()
    #    message.append(f"**{rekkari[0]}**")
    #    message.append(row[0])

    #In it's current form searching a license plate returns a ton of results from messages because every single !r abc123 or abc123 mention saves a message as "abc123"
    await ctx.send('\n'.join(message))

@bot.command()
async def stats(ctx):
    message = []
    count=0

    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return
    record_check(ctx.author.id)

    cur.execute("SELECT vinNumber,COUNT(*) FROM autot_messages GROUP BY vinNumber ORDER BY COUNT(*) DESC LIMIT 11")
    total_mentions = cur.fetchall()

    message.append("**Autoja yhteensä:** " + str(len(cached_rekkari_list)))
    message.append("\n")
    message.append("**Katsotuimmat:**") 
    for row in total_mentions:
        print(row['vinNumber'])
        cur.execute("SELECT rekkari, manufacturer, modelName FROM cache WHERE vinNumber = ?", (row['vinNumber'],))
        rekkari = cur.fetchone()
        if rekkari[0] not in our_cars:  # Skip cars in `our_cars`
            message.append(f"**{rekkari[0]}** {rekkari[1]} {rekkari[2]} Katselukerrat: {row['COUNT(*)']}")
            count += 1
        if count == 5:  # Stop once 5 cars are added
            break
    
    message.append("\n")
    message.append("**Tehokkaimmat**")
    cur.execute("SELECT rekkari, manufacturer, modelName, powerHp FROM cache ORDER BY powerHp DESC LIMIT 5")
    most_powerful = cur.fetchall()
    for row in most_powerful:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Teho: {row[3]} hv")
    message.append("\n")

    message.append("**Mopoimmat**")
    cur.execute("SELECT rekkari, manufacturer, modelName, powerHp FROM cache ORDER BY powerHp ASC LIMIT 5")
    least_powerful = cur.fetchall()
    for row in least_powerful:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Teho: {row[3]} hv")
    message.append("\n")

    cur.execute("SELECT manufacturer, COUNT(*) as c FROM cache GROUP BY manufacturer ORDER BY c DESC LIMIT 5")
    manufacturers = cur.fetchall()
    message.append("**Suosituimmat merkit:**")
    for row in manufacturers:
        message.append(f"**{row[0]}**: {row[1]} kpl")

    message.append("\n")
    message.append("**Suurimmat moottorit**")
    cur.execute("SELECT rekkari, manufacturer, modelName, cylinderVolumeLiters FROM cache ORDER BY cylinderVolumeLiters DESC LIMIT 5")
    most_liters = cur.fetchall()
    for row in most_liters:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Litrat: {row[3]}l")
    message.append("\n")

    message.append("**Eniten sylinterejä**")
    cur.execute("SELECT rekkari, manufacturer, modelName, cylinders FROM cache ORDER BY cylinders DESC LIMIT 5")
    most_cylinders = cur.fetchall()
    for row in most_cylinders:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Sylintereitä: {row[3]}")
    message.append("\n")

    
    message.append("**Tehon keskiarvo**")
    cur.execute("SELECT powerHp FROM cache")
    powers = cur.fetchall()
    p_l=[]
    for row in powers: p_l.append(row[0])
    print(p_l)
    avg=sum(p_l) / len(p_l)
    message.append(f"Kaikkien autojen tehojen keskiarvo on {avg}hv")
    median=p_l[round((len(p_l)/2))]
    message.append(f"Kaikkien autojen tehojen mediaani on {median}hv")
    
    await ctx.send('\n'.join(message))
@bot.command()
async def mopo(ctx):
    message= []
    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return
    try:
        teho = int(ctx.message.content[6:])
    except ValueError:
        await ctx.send("Anna teholukema numeroina")
        return
    except Exception as e:
        await ctx.send("Jokin meni pieleen")
        await ctx.send(e)
        return
    if teho < 10 or teho > 1000:
        await ctx.send("Anna järkevä teholukema")
        return
    
    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return 
    record_check(ctx.author.id)
    
    cur.execute("SELECT COUNT(*) FROM cache")
    total_cars = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cache WHERE powerHp > ?", (teho,))
    powerful_cars = cur.fetchone()[0]
    percentage = (powerful_cars / total_cars) * 100 if total_cars > 0 else 0
    message.append(f"**Yli {teho} hv autojen osuus kaikista autoista:** {percentage:.2f}%")
    
    message.append("\n")

    message.append(f"**Tehokkaampia autoja kuin {teho} hv:**")
    cur.execute("SELECT manufacturer, COUNT(*) as c FROM cache WHERE powerHp >= ? GROUP BY manufacturer ORDER BY c DESC LIMIT 5", (teho,))
    manufacturers = cur.fetchall()
    for row in manufacturers:
        message.append(f"**{row[0]}**: {row[1]} kpl")



    cur.execute("SELECT manufacturer, COUNT(*) FROM cache GROUP BY manufacturer")
    car_counts_by_make = cur.fetchall()

    cur.execute("SELECT manufacturer, COUNT(*) FROM cache WHERE powerHp > ? GROUP BY manufacturer", (teho,))
    powerful_cars_by_make = {row[0]: row[1] for row in cur.fetchall()}

    message.append("\n")
    message.append(f"**Yli {teho} hv autojen osuus per merkki:**")
    for make, count in car_counts_by_make:
        powerful_count = powerful_cars_by_make.get(make, 0)
        percentage = (powerful_count / count) * 100
        message.append(f"**{make}**: {percentage:.2f}%")
    
    await ctx.send('\n'.join(message))

    

    

@bot.command()
async def auto(ctx):
    rekkari = pattern.search(ctx.message.content)
    if is_banned(ctx.author.id):
        record_check(ctx.author.id)
        return
    record_check(ctx.author.id)
    if ctx.author.id == 117967143731068932: rekkari = pattern.search("zgt800")
    if ctx.author.id == 291874573870432256: rekkari = pattern.search("vei475")
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
    if is_banned(ctx.author.id):  
        record_check(ctx.author.id)
        return
    try:
        if ctx.author.id in ban_list:  
            await ctx.send("Kys :D autos on mopo")
            record_check(ctx.author.id)
            return        
            
        if ctx.author.id in id_list:
            new_power = int(ctx.message.content[11:])
            new_kw = new_power * 0.7457
            if new_power < 1:
                raise ValueError("Teho ei voi olla alle 1 hv")
            cur.execute("SELECT rekkari FROM autot WHERE id = ?", (ctx.message.author.id,))
            rekkari = cur.fetchone()
            cur.execute("UPDATE autot SET teho = ? WHERE id = ?", (new_power, ctx.message.author.id))
            cur.execute("UPDATE cache SET powerHp = ?, powerKW = ? WHERE rekkari = ?", (new_power, new_kw,rekkari[0]))
            cars.commit()
            await ctx.send(f"Teho päivitetty: {new_power} hv")
            return
        else:
            await ctx.send("Autoa ei löytynyt")
    except ValueError as e:
        await ctx.send("Anna uusi teholukema numeroina")
    except Exception as e:
        await ctx.send("Jokin meni pieleen")
        await ctx.send(e)


@bot.command()
async def r(ctx):
    if is_banned(ctx.author.id):
        record_check(ctx.author.id)
        return
    record_check(ctx.author.id)
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
        if is_banned(message.author.id):
            record_check(message.author.id)
            return
        record_check(message.author.id)
        if False :          #manually set to true if old plates exist and run once
            update_cached_rekkari()
            update_owned_rekkari()
        rekkari = strictPattern.search(normalize__rekkari(rekkari.group()))
        await message.channel.send(get_licenseplate(rekkari, message.author.id, False, False, message.author.name + ": " + message.content[:50]))

    await bot.process_commands(message)

def is_banned(id):
    #Check if the user in the ban_list has exceeded 10 license plate requests in the last 10 hours.
    if id not in ban_list:
        return False  # Only users in the ban_list are restricted

    current_time = datetime.datetime.now(eest)
    # Get the list of timestamps for the user
    timestamps = ban_check_timestamps[id]

    # Remove timestamps older than 10 hours
    ban_check_timestamps[id] = [t for t in timestamps if (current_time - t).total_seconds() < config['ban']['ban_time']]

    # Check if the user has made 10 or more checks in the last hour
    if len(ban_check_timestamps[id]) >= config['ban']['ban_count']:
        return True

    return False

def record_check(id):
    #Checks if a user is in the ban_list and records the time they made a request to ban_check_timestamps
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
