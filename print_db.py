import sqlite3

cars = sqlite3.connect('autot.db')

cars.row_factory = sqlite3.Row 
cur = cars.cursor()

print("Owned cars")
for i in range(5):
    print("\n")
cur.execute(f"SELECT rekkari FROM autot")
rows = cur.fetchall()

for row in rows:
    print(dict(row))  # Convert to dictionary and print
cur.execute(f"SELECT rekkari FROM cache")
rows = cur.fetchall()

print("Cached cars")
for i in range(5):
    print("\n")
for row in rows:
    print(dict(row))  # Convert to dictionary and print

cars.close()