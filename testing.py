import requests
import datetime
#biltema_db_change = datetime.date.fromisoformat("2025-09-08")
#print(datetime.datetime.today() > biltema_db_change)
print(datetime.datetime.today())
rekkari="zgt800"
rekkariRequest = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{rekkari}?market=3&language=FI")
print(rekkariRequest.json())