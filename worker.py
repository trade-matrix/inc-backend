import requests

def worker():
    try:
        response = requests.get('https://api-dkqs.onrender.com/market/alert/')
        print(response.json())
    except Exception as e:
        print(e)
        print('Failed to send alert')
