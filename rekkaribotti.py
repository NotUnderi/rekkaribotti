import sys,os
import re
import requests
from dotenv import load_dotenv
import sqlite3
import datetime
from collections import defaultdict
import pytz
import yaml
from http import HTTPStatus
from ismo_sound import get_sound
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler,MessageHandler,   filters
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
import asyncio
import logging
import html

eest = pytz.timezone('Europe/Helsinki')
biltema_db_change = datetime.datetime.fromisoformat("2025-09-08 09:00:00.000000+03:00")
today = datetime.date.today()
DB_NAME = "autot_new.db"


with open("config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

def init_db(db_path: str) -> sqlite3.Connection:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    cur_new = db.cursor()
    cur_new.execute("CREATE TABLE IF NOT EXISTS manufacturer (name TEXT PRIMARY KEY)")
    cur_new.execute("CREATE TABLE IF NOT EXISTS model (modelName TEXT PRIMARY KEY, description TEXT)")
    cur_new.execute("""
    CREATE TABLE IF NOT EXISTS vehicle (
        vinNumber TEXT PRIMARY KEY,
        licensePlate TEXT,
        manufacturer TEXT,
        modelName TEXT,
        fuel TEXT,
        drive TEXT,
        registerDate TEXT,
        cylinders INTEGER,
        cylinderVolumeLiters REAL,
        powerHp INTEGER,
        powerKW INTEGER,
        FOREIGN KEY(manufacturer) REFERENCES manufacturer(name),
        FOREIGN KEY(modelName) REFERENCES model(modelName),
        FOREIGN KEY(fuel) REFERENCES fuel_type(name),
        FOREIGN KEY(drive) REFERENCES drive_type(name)
    )
    """)
    cur_new.execute("CREATE TABLE IF NOT EXISTS drive_type (name TEXT PRIMARY KEY)")
    cur_new.execute("CREATE TABLE IF NOT EXISTS fuel_type (name TEXT PRIMARY KEY)")
    cur_new.execute("""
    CREATE TABLE IF NOT EXISTS message (
        id INTEGER PRIMARY KEY,
        message TEXT,
        vinNumber TEXT,
        time TEXT,
        FOREIGN KEY(vinNumber) REFERENCES vehicle(vinNumber)
    )
    """)
    return db

db_new = init_db(DB_NAME)
cur_new = db_new.cursor()

db_new.commit()

our_cars = config['cars']["ignored_cars"]


load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

pattern = re.compile(r'\b[a-zA-ZäöÄÖ]{1,3}-?\d{1,3}\b')
strictPattern = re.compile(r'\b[a-zA-ZäöÄÖ]{3}-?\d{3}\b')



logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.INFO)


def _get_nested(d: dict, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default
def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default  

def get_licenseplate(licenseplate:str) -> str | dict:
    """
    Fetches license plate information from the database or Biltema API.
    :param licenseplate: Licence plate number.
    :return: License plate information as a string or dictionary.
    :raises: requests.exceptions.RequestException if the API request fails.
    """
    cur_new.execute(
        """
        SELECT vehicle.*, model.description
        FROM vehicle
        LEFT JOIN model ON model.modelName = vehicle.modelName
        WHERE vehicle.licensePlate = ?
        """,
        (licenseplate.group(),),
    )
    existing_vehicle = cur_new.fetchone()
    if existing_vehicle is not None:
        dataJson = dict(existing_vehicle)
    else:
        request = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{licenseplate.group()}?market=3&language=FI")
        if request.status_code == 200:
            raw = request.json()

            # Normalize into the schema keys used elsewhere
            dataJson = {
                "manufacturer": raw.get("manufacturer", ""),
                "modelName": raw.get("modelName", ""),
                "description": raw.get("description", ""),
                "vinNumber": _get_nested(raw, "vehicleInfo", "vin") or "",
                "registerDate": _get_nested(raw, "vehicleInfo", "registerDate")
                                or _get_nested(raw, "vehicleInfo", "registrationDat")
                                or "",
                "drive": _get_nested(raw, "gearboxSection", "drive") or "",
                "fuel": _get_nested(raw, "fuelSection", "fuel") or "",
                "cylinders": _safe_int(_get_nested(raw, "engineSection", "engineConfiguration", "cylinders")),
                "cylinderVolumeLiters": _safe_float(_get_nested(raw, "engineSection", "engineConfiguration", "cylinderVolumeLiters")),
                "powerHp": _safe_int(_get_nested(raw, "engineSection", "engingeSpecification", "powerHp") or 1),
                "powerKW": _safe_int(_get_nested(raw, "engineSection", "engingeSpecification", "powerKW")),
            }

            if dataJson["powerHp"] < 1:
                dataJson["powerHp"] = 1

            cur_new.execute("INSERT OR IGNORE INTO manufacturer (name) VALUES(?)", (dataJson["manufacturer"],))
            cur_new.execute("INSERT OR IGNORE INTO model (modelName, description) VALUES(?, ?)", (dataJson["modelName"], dataJson["description"]))
            if dataJson["drive"]:
                cur_new.execute("INSERT OR IGNORE INTO drive_type (name) VALUES(?)", (dataJson["drive"],))
            if dataJson["fuel"]:
                cur_new.execute("INSERT OR IGNORE INTO fuel_type (name) VALUES(?)", (dataJson["fuel"],))
            cur_new.execute(
                "INSERT INTO vehicle (vinNumber, licensePlate, manufacturer, modelName, fuel, drive, registerDate, cylinders, cylinderVolumeLiters, powerHp, powerKW) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    dataJson["vinNumber"],
                    licenseplate.group(),
                    dataJson["manufacturer"],
                    dataJson["modelName"],
                    dataJson["fuel"],
                    dataJson["drive"],
                    dataJson["registerDate"],
                    dataJson["cylinders"],
                    dataJson["cylinderVolumeLiters"],
                    dataJson["powerHp"],
                    dataJson["powerKW"],
                ),
            )
            db_new.commit()
        else:
            raise requests.exceptions.RequestException(f"HTTP: {request.status_code}\n{HTTPStatus(request.status_code).phrase}")
    return dataJson

def generate_message(licenseplate:str, new_message, large:bool) -> str | dict:
    """
    Generates a message based on the license plate information.
    :param licenseplate: Licence plate number.
    :param new_message: New message text.
    :param large: Should the response include extra data (search log etc.)
    """
    message = []
    try:
        dataJson = get_licenseplate(licenseplate)
    except Exception as e:
        return f"Error fetching data for license plate {licenseplate.group()}: {e}"
    
    cur_new.execute("SELECT time, message FROM message WHERE vinNumber = ? ORDER BY time DESC LIMIT 5", (dataJson["vinNumber"],))    
    messages = cur_new.fetchall()

    cur_new.execute("SELECT COUNT(*) FROM message WHERE vinNumber = ?", (dataJson["vinNumber"],)) # We fetch total mention count separately since cannot do len() on above query due to "LIMIT 5"    
    total_mentions = cur_new.fetchone()['COUNT(*)']

    cur_new.execute("SELECT time, message FROM message WHERE vinNumber = ? ORDER BY time ASC LIMIT 1",(dataJson["vinNumber"],))
    first_seen = cur_new.fetchone()
    if first_seen is not None:
        first_seen_time = datetime.datetime.fromisoformat(first_seen['time'])
        if (first_seen_time<biltema_db_change):
            message.append(dataJson["manufacturer"] + " " + dataJson["modelName"] + " " + dataJson["description"])
        else:
            message.append(dataJson["description"])
    else:
        message.append(dataJson["description"])
    
    h = html.escape
    power_hp = _safe_int(dataJson.get("powerHp"), 1)
    message.append(f"Teho : <b>{h(str(power_hp))} hevosvoimaa</b>")
    message.append(f"Sylinteritilavuus: <b>{h(str(dataJson.get('cylinderVolumeLiters', '')))}</b> litraa")
    message.append(f"Sylinterimäärä: <b>{h(str(dataJson.get('cylinders', '')))}</b>")

    if large:
        message.append(f"Rekisteröintipäivä: <b>{h(str(dataJson.get('registerDate', '')))}</b>")
        message.append(f"Vetotapa: <b>{h(str(dataJson.get('drive', '')))}</b>")
        message.append(f"Polttoaine: <b>{h(str(dataJson.get('fuel', '')))}</b>")
        message.append(f"VIN: <b>{h(str(dataJson.get('vinNumber', '')))}</b>")
        if messages:
            message.append(f"<b>Viimeiset haut:</b>")
            for msg in messages:
                last_seen = datetime.datetime.fromisoformat(msg['time'])
                human_readable_time = last_seen.strftime("%d.%m.%Y %H:%M:%S")
                safe_msg = h(msg["message"])
                message.append(f"<b>{human_readable_time}</b>: {safe_msg}")
    message.append(f"Hakukertoja yhteensä:<b>{str(total_mentions)}</b>")

    if new_message is not None:
        cur_new.execute("INSERT INTO message (message, vinNumber, time) VALUES (?, ?, ?)",
                    (new_message, dataJson["vinNumber"], datetime.datetime.now(eest)))
        db_new.commit()
    return('\n'.join(message))
    

'''
async def on_ready():
    print(f'Logged in as {bot.user}')


async def help(ctx):
    message = []
    message.append("**Komennot:**")
    message.append("!r <abc123> - Hae auton tiedot")
    message.append("!mopo 123 - Kuinka moni auto ylittää annetun tehon")
    message.append("!stats - Hae tilastotietoja")
    await ctx.send('\n'.join(message))


async def hae(ctx):
    message = []

    cur_new.execute("SELECT licensePlate, modelName FROM vehicle WHERE modelName LIKE ?", ('%'+ctx.message.content[5:]+'%',))
    rows = cur_new.fetchall()
    if rows:
        message.append("**Hakutulokset malleista:**")
        message.append("Hakutuloksien määrä: " + str(len(rows)))
        for row in rows:
            message.append(row[1] + " " + row[0])
    else:
        message.append("Ei hakutuloksia malleista")
    cur_new.execute("SELECT licensePlate FROM vehicle WHERE licensePlate LIKE ?", ('%'+ctx.message.content[5:]+'%',))
    rows = cur_new.fetchall()
    if not rows:
        message.append("Ei hakutuloksia rekkareista")
        await ctx.send('\n'.join(message))
        return
    message.append("**Hakutulokset rekkareista:**")
    for row in rows:
        message.append(row[0])

    message_chunks = split_message_by_newlines('\n'.join(message))
    print(message_chunks)
    print(len(message_chunks))
    for chunk in message_chunks:
        await ctx.send(chunk)
        
async def stats(ctx):
    message = []
    count=0


    cur_new.execute("SELECT COUNT(*) as c FROM vehicle ORDER BY c DESC LIMIT 11")
    total_views = cur_new.fetchall()
    cur_new.execute("SELECT vinNumber, COUNT(*) FROM message GROUP BY vinNumber ORDER BY COUNT(*) DESC")
    total_mentions = cur_new.fetchall()

    message.append("**Autoja yhteensä:** " + str(len(total_views)))
    message.append("\n")
    message.append("**Katsotuimmat:**") 
    for row in total_mentions:
        print(row['vinNumber'])
        cur_new.execute("SELECT licensePlate, manufacturer, modelName FROM vehicle WHERE vinNumber = ?", (row['vinNumber'],))
        rekkari = cur_new.fetchone()
        if rekkari[0] not in our_cars:  # Skip cars in `our_cars`
            message.append(f"**{rekkari[0]}** {rekkari[1]} {rekkari[2]} Katselukerrat: {row['COUNT(*)']}")
            count += 1
        if count == 5:  # Stop once 5 cars are added
            break
    
    message.append("\n")
    message.append("**Tehokkaimmat**")
    cur_new.execute("SELECT licensePlate, manufacturer, modelName, powerHp FROM vehicle ORDER BY powerHp DESC LIMIT 5")
    most_powerful = cur_new.fetchall()
    for row in most_powerful:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Teho: {row[3]} hv")
    message.append("\n")

    message.append("**Mopoimmat**")
    cur_new.execute("SELECT licensePlate, manufacturer, modelName, powerHp FROM vehicle WHERE powerHp > 1 ORDER BY powerHp ASC LIMIT 5")
    least_powerful = cur_new.fetchall()
    for row in least_powerful:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Teho: {row[3]} hv")
    message.append("\n")

    cur_new.execute("SELECT manufacturer, COUNT(*) as c FROM vehicle GROUP BY manufacturer ORDER BY c DESC LIMIT 5")
    manufacturers = cur_new.fetchall()
    message.append("**Suosituimmat merkit:**")
    for row in manufacturers:
        message.append(f"**{row[0]}**: {row[1]} kpl")
    message.append("\n")

    cur_new.execute("SELECT modelName, COUNT(*) as c FROM vehicle GROUP BY modelName ORDER BY c DESC LIMIT 5")
    popular_models = cur_new.fetchall()
    message.append("**Suosituimmat mallit:**")
    for row in popular_models:
        message.append(f"**{row[0]}**: {row[1]} kpl")
    message.append("\n")

    message.append("**Harvinaisimmat merkit:**")
    cur_new.execute("SELECT manufacturer, COUNT(*) as c FROM vehicle GROUP BY manufacturer ORDER BY c ASC LIMIT 5")
    rarest_manufacturers = cur_new.fetchall()
    for row in rarest_manufacturers:
        message.append(f"**{row[0]}**: {row[1]} kpl")
    message.append("\n")

    message.append("**Suurimmat moottorit**")
    cur_new.execute("SELECT licensePlate, manufacturer, modelName, cylinderVolumeLiters FROM vehicle ORDER BY cylinderVolumeLiters DESC LIMIT 5")
    most_liters = cur_new.fetchall()
    for row in most_liters:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Litrat: {row[3]}l")
    message.append("\n")

    message.append("**Eniten sylinterejä**")
    cur_new.execute("SELECT licensePlate, manufacturer, modelName, cylinders FROM vehicle ORDER BY cylinders DESC LIMIT 5")
    most_cylinders = cur_new.fetchall()
    for row in most_cylinders:
        message.append(f"**{row[0]}** {row[1]} {row[2]} Sylintereitä: {row[3]}")
    message.append("\n")

    
    message.append("**Tehon keskiarvo**")
    cur_new.execute("SELECT powerHp FROM vehicle ORDER BY powerHp DESC")
    powers = cur_new.fetchall()
    p_l=[]
    for row in powers: p_l.append(row[0])
    print(p_l)
    avg=sum(p_l) / len(p_l)
    message.append(f"Kaikkien autojen tehojen keskiarvo on {avg}hv")
    median=p_l[round((len(p_l)/2))]
    message.append(f"Kaikkien autojen tehojen mediaani on {median}hv")
    
    message = '\n'.join(message)
    if len(message) >= 2000:
        lines = message.splitlines()
        await ctx.send('\n'.join(lines[:len(lines)//2]))
        await ctx.send('\n'.join(lines[len(lines)//2:]))
    await ctx.send(message)

@bot.command()
async def mopo(ctx):
    message = []

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

    # Fetch total cars and powerful cars
    cur_new.execute("SELECT COUNT(*) FROM vehicle")
    total_cars = cur_new.fetchone()[0]

    cur_new.execute("SELECT COUNT(*) FROM vehicle WHERE powerHp > ?", (teho,))
    powerful_cars = cur_new.fetchone()[0]
    percentage = (powerful_cars / total_cars) * 100 if total_cars > 0 else 0
    message.append(f"**Yli {teho} hv autojen osuus kaikista autoista:** {percentage:.2f}%")
    message.append("\n")

    # Fetch powerful cars by manufacturer
    message.append(f"**Tehokkaampia autoja kuin {teho} hv:**")
    cur_new.execute("SELECT manufacturer, COUNT(*) as c FROM vehicle WHERE powerHp >= ? GROUP BY manufacturer ORDER BY c DESC LIMIT 5", (teho,))
    manufacturers = cur_new.fetchall()
    for row in manufacturers:
        message.append(f"**{row[0]}**: {row[1]} kpl")

    # Fetch powerful cars percentage by manufacturer
    cur_new.execute("SELECT manufacturer, COUNT(*) FROM vehicle GROUP BY manufacturer")
    car_counts_by_make = cur_new.fetchall()

    cur_new.execute("SELECT manufacturer, COUNT(*) FROM vehicle WHERE powerHp > ? GROUP BY manufacturer", (teho,))
    powerful_cars_by_make = {row[0]: row[1] for row in cur_new.fetchall()}

    message.append("\n")
    message.append(f"**Yli {teho} hv autojen osuus per merkki:**")
    for make, count in car_counts_by_make:
        powerful_count = powerful_cars_by_make.get(make, 0)
        percentage = (powerful_count / count) * 100
        message.append(f"**{make}**: {percentage:.2f}%")

    # Split and send the message in chunks
    message_chunks = split_message_by_newlines('\n'.join(message))
    for chunk in message_chunks:
        await ctx.send(chunk)

@bot.command()
async def r(ctx):
    licenseplate = pattern.search(ctx.message.content)
    if licenseplate:
        licenseplate = pattern.search(normalize__licenseplate(licenseplate.group()))
        await ctx.send(generate_message(licenseplate, ctx.message, True))

@bot.command()
async def puhu(ctx):
    licenseplate = pattern.search(ctx.message.content)
    if licenseplate:
        licenseplate = pattern.search(normalize__licenseplate(licenseplate.group()))
        msg = generate_message(licenseplate, ctx.message, False)
        try:
            print(msg)
            sound = get_sound(msg)
        except Exception as e:
            await ctx.send("Ismonator ei toiminut. \n" + str(e))
            return
        await ctx.send(msg)
        await ctx.send(file=discord.File(sound))
        '''

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    licenseplate = pattern.search(text)
    if licenseplate and text.startswith('!r'):
        licenseplate = pattern.search(normalize__licenseplate(licenseplate.group()))
        msg = generate_message(licenseplate, update.message.from_user.first_name + ": " + text, True)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode=ParseMode.HTML,
            text=msg
        )
    elif licenseplate and not text.startswith('!'):
        licenseplate = strictPattern.search(normalize__licenseplate(licenseplate.group()))
        msg = generate_message(licenseplate, update.message.from_user.first_name + ": " + text, False)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            parse_mode=ParseMode.HTML,
            text=msg
        )

def normalize__licenseplate(licenseplate:str) -> str:
    licenseplate = licenseplate.upper()
    if re.compile(r'\b-\b').search(licenseplate) != None:
        return licenseplate
    licenseplate = re.sub(r'([A-Za-zäöÄÖ]+)(\d+)', r'\1-\2', licenseplate)
    return licenseplate
def split_message_by_newlines(text, max_len=1900):
    lines = text.split("\n")
    chunks = []
    current = []

    current_len = 0

    for line in lines:
        line_len = len(line) + 1 

        if current_len + line_len > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    # Append last chunk
    if current:
        chunks.append("\n".join(current))

    return chunks
if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    on_message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), on_message)
    application.add_handler(on_message_handler)
    application.run_polling()