import requests
import uuid
import os
from accounts.models import Customer
from .models import Requested_Withdraw,Transaction,Investment, Wallet, Profit
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from datetime import datetime
from .promo import message_decider
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

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
        "redirect_url": "https://trade-matrix.net/admin/default/",
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
        "notification_url": "https://api-dkqs.onrender.com/market/webhook/",
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

#Not a Kora Pay Function    
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

def update_user(email,sub, context, template):
    from_email = "support@goldencash.live"
    to_email = email
    subject = sub
    text_content = context
    html_content = render_to_string(template)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, 'text/html')
    msg.send()

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

def paystack_create_recipient(name, account_number, bank_code):
    url = 'https://api.paystack.co/transferrecipient'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pay_stack_secret}'
    }
    data = {
        "type": "mobile_money",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "GHS"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        return response.json()
    else:
        print({"error": response.text, "status_code": response.status_code})
        return False

def paystack_send_money(amount, phone_number, user_id, recipient_code):
    url = 'https://api.paystack.co/transfer'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {pay_stack_secret}'
    }
    data = {
        "source": "balance",
        "amount": amount*100,
        "recipient": recipient_code,
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

def paystack_balance_check():
    url = 'https://api.paystack.co/balance'
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

#Important functions
def withdraw_optout(user,wallet, amount, operator, phone_number):
    if wallet.deposit >= float(amount):
        Requested_Withdraw.objects.create(user=user, amount=amount, phone_number=phone_number, operator=operator)
        send_sms("Your withdrawal has been initiated successfully. However, it will take a while to be processed. Please be patient.", user.phone_number)
        wallet.deposit -= float(amount)
        if wallet.amount_from_games:
            wallet.balance -= (float(amount)*3 + wallet.amount_from_games)
        else:
            wallet.balance -= float(amount)*3
        wallet.balance = max(wallet.balance, 0)
        wallet.amount_from_games = 0
        wallet.save()
        # Send balance update to the WebSocket consumer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",  # Unique group for each user
            {
                "type": "send_balance_update",
                "new_balance": wallet.balance,
            }
        )
        #Send sms to notify admins
        send_sms(f"Dear Admin,\n{user.username} has initiated a withdrawal of GHS {amount}. Please process it manually.", "0599971083")
        
        #Create a transaction record
        Transaction.objects.create(user=user, amount=amount, status='pending', type='withdrawal', image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/transaction.png')
        investment = Investment.objects.get(amount=amount)
        investment.user.remove(user)
        investment.save()
        user_active_investments = Investment.objects.filter(user__id=user.id).count()
        if user_active_investments == 0:
            wallet.balance = 0
            wallet.active = False
            wallet.eligible = False
            wallet.save()
        return True
    else:
        return False

def withdraw(user, wallet, amount, operator, phone_number):
    if wallet.balance >= float(amount):
        send = paystack_send_money(float(amount), phone_number, user.id, user.recepient_code)
        if not send:
            Requested_Withdraw.objects.create(user=user, amount=amount, phone_number=phone_number, operator=operator)
            send_sms("Your withdrawal has been initiated successfully. However, it will take a while to be processed. Please be patient.", user.phone_number)
            amin_phone = "0599971083"
            send_sms(f"Dear Admin,\n{user.username} has initiated a withdrawal of GHS {amount}. Please process it manually.", amin_phone)
            return True
        else:
            send_sms("Your withdrawal has been processed successfully. Refer more to earn more.", user.phone_number)
            update_user(user.email, "Congratulations", "Congratulations! Your withdrawal has been processed successfully.", "withdraw_s.html")
        wallet.balance -= float(amount)
        wallet.balance = max(wallet.balance, 0)
        wallet.amount_from_games += float(amount)
        wallet.save()
        try:
            requested_withdraw = Requested_Withdraw.objects.get(user=user, amount=amount, phone_number=phone_number, operator=operator)
            if not requested_withdraw.settled:
                requested_withdraw.settled = True
                requested_withdraw.save()
        except Requested_Withdraw.DoesNotExist:
            pass
        # Send balance update to the WebSocket consumer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",  # Unique group for each user
            {
                "type": "send_balance_update",
                "new_balance": wallet.balance,
            }
        )
        #Create a transaction record
        Transaction.objects.create(user=user, amount=amount, status='pending', type='withdrawal', image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/transaction.png')
        return True 
    else:
        return False

def check_referrer_status(wallet, amount, reffered_wallet):
    if amount > 30:
        profit,_ = Profit.objects.get_or_create(name='gc')
    else:
        profit,_ = Profit.objects.get_or_create(name='profit')
    wallet.balance += (amount/2)
    profit.amount_today += amount/2
    profit.total_amount += amount/2
    wallet.save()
    profit.save()
    return True

def handle_payment(user, investment, wallet, amount):
    if not user.referred_by:
        wallet.deposit += amount  # For example, adding a deposit
        # Update the wallet balance
        wallet.active = True
        wallet.eligible = True
        wallet.date_made_eligible = datetime.now()
        wallet.save()
        # Create a transaction record
        transaction = Transaction.objects.create(user=user, amount=amount, status='completed', type='deposit', image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/transaction.png')
        # Serialize the transaction into JSON-serializable data
        transaction_data = {
            'id': transaction.id,
            'user': transaction.user.id,  # Assuming you're using the user's ID
            'amount': transaction.amount,
            'status': transaction.status,
            'type': transaction.type,
            'created_at': transaction.created_at.isoformat()  # Convert datetime to ISO format
        }

        # Send the serialized transaction to the WebSocket consumer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_user_transaction",
                "transaction": transaction_data  # Send the serialized data
            }
        )

        # Send balance update to the WebSocket consumer
        balance_data ={
            "new_balance": wallet.balance,
            "earnings": wallet.balance - wallet.deposit
        }
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",  # Unique group for each user
            {
                "type": "send_balance_update",
                "new_balance": balance_data,
            }
        )
        investment.user.add(user)
        investment.save()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_user_verified",
            }
        )
    elif user.referred_by:
        wallet.deposit += amount  # For example, adding a deposit
        # Update the wallet balance
        if amount == 15:
            wallet.tier = 1
        elif amount == 20:
            wallet.tier = 2
        elif amount == 30:
            wallet.tier = 3
        wallet.active = True
        wallet.eligible = True
        wallet.date_made_eligible = datetime.now()
        wallet.deposit_used = True
        wallet.save()
        # Create a transaction record
        transaction = Transaction.objects.create(user=user, amount=amount, status='completed', type='deposit', image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/transaction.png')
        # Serialize the transaction into JSON-serializable data
        transaction_data = {
            'id': transaction.id,
            'user': transaction.user.id,  # Assuming you're using the user's ID
            'amount': transaction.amount,
            'status': transaction.status,
            'type': transaction.type,
            'created_at': transaction.created_at.isoformat()  # Convert datetime to ISO format
        }

        # Send the serialized transaction to the WebSocket consumer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_user_transaction",
                "transaction": transaction_data  # Send the serialized data
            }
        )

        # Send balance update to the WebSocket consumer
        balance_data ={
            "new_balance": wallet.balance,
            "earnings": wallet.balance - wallet.deposit
        }
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",  # Unique group for each user
            {
                "type": "send_balance_update",
                "new_balance": balance_data,
            }
        )
        investment.user.add(user)
        investment.save()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_user_verified",
            }
        )
        referrer_wallet,_ = Wallet.objects.get_or_create(user=user.referred_by)
        if referrer_wallet.user.verified:
            check = check_referrer_status(referrer_wallet, amount, wallet)
            if not check:
                return True
            try:
                transaction = Transaction.objects.get(user=user.referred_by, status='pending', type='referal', reffered=user.username)
                transaction.status = 'completed'
                transaction.amount = (amount*investment.interest)*0.5
                transaction.save()
            except Transaction.DoesNotExist:
                transaction = Transaction.objects.create(user=user.referred_by, amount=(amount*investment.interest)*0.5, status='completed', type='referal', reffered=user.username)
            # Send balance update to the WebSocket consumer
            balance_data ={
                "new_balance": referrer_wallet.balance,
                "earnings": referrer_wallet.balance - referrer_wallet.deposit
            }
            async_to_sync(channel_layer.group_send)(
                f"user_{user.referred_by.id}",
                {
                    "type": "send_balance_update",
                    "new_balance": balance_data,
                }
            )
            #Send Transsaction to WebSocket
            transaction_data = {
                'id': transaction.id,
                'user': transaction.user,  # Assuming you're using the user's ID
                'amount': transaction.amount,
                'status': transaction.status,
                'type': transaction.type,
                'reffered': transaction.reffered,
                'created_at': transaction.created_at.isoformat()  # Convert datetime to ISO format
            }
            async_to_sync(channel_layer.group_send)(
                f"user_{user.referred_by.id}",
                {
                    'type': 'send_user_transaction',
                    'transaction': transaction_data
                }
            )

            send_sms(f"Dear customer,\nCongratulations, your deposit has been processed successfuly. Refer people to increase your earnings.", user.phone_number)
            update_user(user.email, "Congratulations", "Congratulations! Your deposit has been processed successfully.", "payment.html")
            send_sms(f"Congratulations! You just earned from {user.username}'s deposit.\nYour total balance is now GHS {referrer_wallet.balance}", user.referred_by.phone_number)
            update_user(user.referred_by.email, "Congratulations", f"Congratulations! You just earned from {user.username}'s deposit.", "referal.html")
        return True
    send_sms(f"Congratulations! Your deposit has been processed successfully. Refer people to increase your earnings.", user.phone_number)
    update_user(user.email, "Congratulations", "Congratulations! Your deposit has been processed successfully.", "payment.html")
    return True

#Workers
def worker():
   
    customers = Customer.objects.all()
    
    for customer in customers:
        try:
            message = message_decider('news', customer, 10)
            send_sms(message, customer.phone_number)
            print(f'Sent message to {customer.username}')
        except Exception as e:
            print(f'Error sending message to {customer.phone_number}: {e}')

def send_promo_sms(user):
    message = message_decider('news', user, 10)
    send_sms(message, user.phone_number)
    print(f'Sent message to {user.phone_number}')

