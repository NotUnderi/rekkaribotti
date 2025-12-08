import requests
from itertools import product
import time

letters = [chr(i) for i in range(ord('A'), ord('Z')+1)]
digits = [f"{i:03d}" for i in range(1000)]

count = 0
start = time.time()
last_report = start


def get_licenseplate(licenseplate):
    try:
        request = requests.get(f"https://reko2.biltema.com/VehicleInformation/licensePlate/{licenseplate}?market=3&language=FI")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for license plate {licenseplate.group()}: {e}")
        return None
    if request.status_code == 200:
        dataJson = request.json()
        return dataJson
for L3 in letters:
        for num in digits:
            count += 1
            if count % 10 == 0:
                now = time.time()
                elapsed = now - start
                rate = count / elapsed
                print(f"Processed: {count:,} plates | {rate:,.0f} plates/sec")
                last_report = now

            lp = (f"IO{L3}-{num}")
            print(f"Processing license plate: {lp}")
            try:
                data = get_licenseplate(lp)
                if data is None:
                    continue
            except Exception as e:
                print(f"Error processing license plate {lp}: {e}")
                continue
            if "Passat Variant" in data['modelName']:
                print(f"{lp}: {data['modelName']}")

end = time.time()
total_time = end - start
avg_rate = count / total_time
print(f"Total plates: {count:,}")
print(f"Total time: {total_time:.2f}s")
print(f"Average speed: {rate:,.0f} plates/sec")