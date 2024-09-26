import requests
import time

while True:
    url = 'https://api-dkqs.onrender.com'
    response = requests.get(url)
    print(response.json())
    time.sleep(20)
