import requests
import uuid
import os
secret = os.environ.get('Kora_Secret_Key')
pay_stack_secret = os.environ.get('pay_stack_secret')

#KORA PAY FUNCTIONS
def payment(amount, title, name):
    url = 'https://api.korapay.com/merchant/api/v1/charges/initialize'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {secret}'
    }
    data = {
        "amount": amount,
        "redirect_url": "http://127.0.0.1:8000/accounts/login",
        "currency": "GHS",
        "reference": str(uuid.uuid4()),
        "narration": f"Payment for {title}",
        "channels": [
            "mobile_money",
        ],
        "customer": {
            "name": name,
            "email": f"{name}@email.com",
        },
        "metadata": {
            "investment": title,
            'username': name
        },
        "notification_url": "http://127.0.0.1:8000/market/webhook/",
        "merchant_bears_cost": False
    }

    response = requests.post(url,headers=headers, json=data)

    if response.status_code == 200:
        return response.json()  # Returning the response in JSON format if successful
    else:
        print( {"error": response.text, "status_code": response.status_code})
        return False

def status_check(reference):
    url = f'https://api.korapay.com/merchant/api/v1/charges/{reference}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {secret}'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False

def send_money(amount, phone_number, operator, user_id):
    url = 'https://api.korapay.com/merchant/api/v1/transactions/disburse'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {secret}'
    }
    data = {
        "reference": str(uuid.uuid4()),
        "destination": 
        {
            "type": "mobile_money",
            "amount": amount,
            "currency": "GHS",
            "narration": "Test Transfer Payment",
            "mobile_money": 
            {
                "operator": operator,
                "mobile_number": phone_number
            },
            "customer": 
            {
                "name": "John Doe",
                "email": "johndoe@email.com"
            }
	    },
        "metadata": {
            "phone_number": phone_number,
            "user_id": user_id  
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False
    
def send_sms(message, number):
    url = "https://sms.arkesel.com/sms/api"
    params = {
        "action": "send-sms",
        "api_key": os.environ.get("ARK_API_KEY"),
        "to": number,
        "from": "TradeMatrix",
        "sms": message
    }
    # Send HTTP GET request
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        print(response.text)
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)

def check_momo(phone_number, operator):
    url = 'https://api.korapay.com/merchant/api/v1/misc/mobile-money/resolve'
    data = {
        "phoneNumber": phone_number,
        "mobileMoneyCode": operator,
        "currency": "GHS"
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False


#PAYSTACK FUNCTIONS
def paystack_payment(amount, title, name):
    url = 'https://api.paystack.co/transaction/initialize'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pay_stack_secret}'
    }
    print(headers)
    data = {
        "amount": amount*100,
        "email": f"{name}@email.com",
        "reference": str(uuid.uuid4()),
        "metadata": {
            "investment": title,
            'username': name
        },
        "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer", "eft"]
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False

def paystack_status_check(reference):
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pay_stack_secret}'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False

def paystack_send_money(amount, phone_number, user_id):
    url = 'https://api.paystack.co/transfer'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pay_stack_secret}'
    }
    data = {
        "source": "balance",
        "amount": amount*100,
        "recipient": phone_number,
        "reason": "Transfer Payment",
        "reference": str(uuid.uuid4()),
        "metadata": {
            "phone_number": phone_number,
            "user_id": user_id
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False 