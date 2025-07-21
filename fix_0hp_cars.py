#This script turns all 0 hp cars to 1 hp cars in the database.
#This is because division by 0 is not allowed and Biltema defaults to 0 hp on some cars, especially USDM cars.
import sqlite3

cars = sqlite3.connect('autot.db')

cars.row_factory = sqlite3.Row 
cur = cars.cursor()


cur.execute(f"SELECT vinNumber, powerHp FROM cache WHERE powerHp < 2")
rows = cur.fetchall()

for row in rows:
       print(f"Updating {row['vinNumber']} powerHp from {row['powerHp']} to 1")
       cur.execute("UPDATE cache SET powerHp = 1 WHERE vinNumber = ?", (row['vinNumber'],))
       cars.commit()


cars.close()