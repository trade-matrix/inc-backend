import requests

def worker():
    try:
        response = requests.get('http://127.0.0.1:8000/market/revert/')
        print(response.json())
    except Exception as e:
        print(e)
        print('Failed to send alert')

worker()