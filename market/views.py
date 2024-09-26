from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework import permissions
from .models import Investment
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Wallet, Operator, Transaction, Comment, Requested_Withdraw, Game
from .serializers import InvestmentSerializer, RequesttoInvest, PredictionSerializer, Withdraw, CheckMomoSerializer, TransactionSerializer, WalletSerializer, CommentSerializer, GameSerializer
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.response import Response
from accounts.models import Customer
from .utils import paystack_send_money, send_sms, check_momo, paystack_payment, paystack_status_check
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
import json
from django.views.decorators.csrf import csrf_exempt
import datetime
from datetime import datetime, timedelta
#pagination
from rest_framework.pagination import PageNumberPagination

class InvestmentListView(generics.ListAPIView):
    queryset = Investment.objects.all()
    serializer_class = InvestmentSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        return Investment.objects.all()
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

class UserInvest(APIView):
    queryset = Investment.objects.all()
    serializer_class = RequesttoInvest
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def post(self, request, *args, **kwargs):
        pk = request.data.get('id')
        investment = Investment.objects.get(pk=pk)
        if not request.user in investment.user.all():
            user = request.user
            payment_response = paystack_payment(investment.amount, investment.title, user.username)
            if not payment_response:
                return Response({"error": "Payment Initiation failed"}, status=status.HTTP_400_BAD_REQUEST)
            reference = payment_response['data']['reference']
            user.reference = reference
            user.save()
            data = {
                "payment_response": payment_response,
            }
            return Response(data, status=status.HTTP_200_OK)
        return Response({"error": "User has Already Invested In this firm"}, status=status.HTTP_400_BAD_REQUEST)

class VerifyPayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def get(self, request, *args, **kwargs):
        user = request.user
        reference = user.reference
        status_chec = paystack_status_check(reference)
        if status_chec['data']['status'] == 'success':
            user.verified = True
            user.save()
            investment = Investment.objects.get(title=status_chec['data']['metadata']['investment'])
            wallet,_ = Wallet.objects.get_or_create(user=user)
            
            # Update the wallet balance
            wallet.balance += (float(status_chec['data']['amount'])*(investment.interest)) + float(status_chec['data']['amount'])
            wallet.deposit = float(status_chec['data']['amount'])  # For example, adding a deposit
            wallet.save()
            # Create a transaction record
            transaction = Transaction.objects.create(user=user, amount=float(status_chec['data']['amount']), status='completed', type='deposit')
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
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",  # Unique group for each user
                {
                    "type": "send_balance_update",
                    "new_balance": wallet.balance,
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
            if user.referred_by:
                referrer_wallet,_ = Wallet.objects.get_or_create(user=user.referred_by)
                referrer_wallet.balance += float(status_chec['data']['amount'])*investment.interest*0.15
                referrer_wallet.save()
                transaction = Transaction.objects.create(user=user.referred_by, amount=float(status_chec['data']['amount'])*investment.interest*0.15, status='completed', type='referal')
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.referred_by.id}",
                    {
                        "type": "send_balance_update",
                        "new_balance": referrer_wallet.balance,
                    }
                )
                send_sms(f"Dear customer,\nCongratulations your investment has been made successfuly. However, you are eligible to receive only 85% of your returns, as you were referred by {user.referred_by.username}. Refer more people to increase your earnings. You may withdraw your deposit within the next 24 hours. After this period, withdrawals will be paused until the target is reached.", user.phone_number)
                send_sms(f"Congratulations! You just earned 15% of {user.username}'s investment.\nYour total balance is now GHS {referrer_wallet.balance}", user.referred_by.phone_number)
                return Response({"message": "Payment successful"}, status=status.HTTP_200_OK)
            send_sms(f"Congratulations! Your investment has been successful. You can withdraw your returns after the target is reached. You may withdraw your deposit within the next 24 hours. After this period, withdrawals will be paused until the target is reached.", user.phone_number)
            return Response({"message": "Payment successful"}, status=status.HTTP_200_OK)
        if not status_chec:
            return Response({"error": "Invalid reference"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status_chec, status=status.HTTP_200_OK)

class WithdrawfromWallet(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = Withdraw
    def post(self, request, *args, **kwargs):
        user = request.user
        wallet = Wallet.objects.get(user=user)
        amount = request.data.get('amount')
        #operator = request.data.get('operator')
        phone_number = request.data.get('phone_number')
        if wallet.balance >= float(amount):
            result = paystack_send_money(amount, phone_number, user.id)
            if not result:
                withdraw = Requested_Withdraw.objects.create(user=user, amount=amount, phone_number=phone_number)
                send_sms("Your withdrawal has been initiated successfully. However, it will be processed manually. Please be patient.", user.phone_number)
                #Send sms to notify admins
                send_sms(f"Dear Admin,\n{user.username} has initiated a withdrawal of GHS {amount}. Please process it manually.", "0599971083")
            send_sms("Your withdrawal has been initiated successfully.", user.phone_number)
            wallet.balance -= float(amount)
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
            return Response({"message": "Withdrawal successful"}, status=status.HTTP_200_OK)
        return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    def post(self, request, *args, **kwargs):
        try:
            # Parse the JSON body
            payload = json.loads(request.body.decode('utf-8'))

            # Here you can handle the notification (e.g., update your database, etc.)
            if payload.get('event') == 'transfer.success':
                phone_number = payload['metadata']['phone_number']
                user_id = payload['metadata']['user_id']
                investment = Investment.objects.get(title=payload['metadata']['investment'])
                wallet = Wallet.objects.get(user=user_id)
                wallet.active = False
                wallet.balance = 0
                wallet.deposit = 0
                wallet.save()
                # Send balance update to the WebSocket consumer
                balance_data ={
                    "new_balance": wallet.balance,
                    "earnings": wallet.balance - wallet.deposit
                }
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}",  # Unique group for each user
                    {
                        "type": "send_balance_update",
                        "new_balance": balance_data,
                    }
                )
                investment.user.remove(user_id)
                investment.save()
                send_sms("Your withdrawal was successful", phone_number)
            elif payload.get('event') == 'transfer.failed':
                phone_number = payload['metadata']['phone_number']
                user_id = payload['metadata']['user_id']
                wallet = Wallet.objects.get(user=user_id)
                wallet.balance += float(payload['data']['amount'])
                wallet.save()

                # Send balance update to the WebSocket consumer
                channel_layer = get_channel_layer()
                balance_data ={
                    "new_balance": wallet.balance,
                    "earnings": wallet.balance - wallet.deposit
                }
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}",  # Unique group for each user
                    {
                        "type": "send_balance_update",
                        "new_balance": balance_data,
                    }
                )
                send_sms("Your withdrawal failed. Your balance has been reverted.", phone_number)   
            elif payload.get('event') == 'charge.success':
                reference = payload['data']['reference']
                user = Customer.objects.get(reference=reference)
                user.verified = True
                user.save()
                investment = Investment.objects.get(title=payload['data']['metadata']['investment'])
                wallet,_ = Wallet.objects.get_or_create(user=user)
                if wallet.active:
                    return JsonResponse({"error": "User has already invested"}, status=200)
                # Update the wallet balance
                if not user.referred_by:
                    wallet.balance += ((float(payload['data']['amount'])*(investment.interest)) + float(payload['data']['amount']))/100
                    wallet.deposit = float(payload['data']['amount'])/100  # For example, adding a deposit
                    # Update the wallet balance
                    wallet.active = True
                    wallet.eligible = True
                    wallet.date_made_eligible = datetime.now()
                    wallet.save()
                    # Create a transaction record
                    transaction = Transaction.objects.create(user=user, amount=float(payload['data']['amount'])/100, status='completed', type='deposit')
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
                    wallet.balance += ((float(payload['data']['amount'])*(investment.interest)) + float(payload['data']['amount']))*0.85/100
                    wallet.deposit = float(payload['data']['amount'])/100  # For example, adding a deposit
                    # Update the wallet balance
                    wallet.active = True
                    wallet.eligible = True
                    wallet.date_made_eligible = datetime.now()
                    wallet.save()
                    # Create a transaction record
                    transaction = Transaction.objects.create(user=user, amount=float(payload['data']['amount'])/100, status='completed', type='deposit')
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
                    referrer_wallet.balance += (float(payload['data']['amount'])*investment.interest*0.15)/100
                    referrer_wallet.save()
                    transaction = Transaction.objects.create(user=user.referred_by, amount=(float(payload['data']['amount'])*investment.interest*0.15)/100, status='completed', type='referal', reffered=user.username)
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

                    send_sms(f"Dear customer,\nCongratulations your investment has been made successfuly. However, you are eligible to receive only 85% of your returns, as you were referred by {user.referred_by.username}. Refer more people to increase your earnings. You may withdraw your deposit within the next 24 hours. After this period, withdrawals will be paused until the target is reached.", user.phone_number)
                    send_sms(f"Congratulations! You just earned 15% of {user.username}'s investment.\nYour total balance is now GHS {referrer_wallet.balance}", user.referred_by.phone_number)
                    return Response({"message": "Payment successful"}, status=200)
                send_sms(f"Congratulations! Your investment has been made successful. You can withdraw your returns after the target is reached. You may withdraw your deposit within the next 24 hours. After this period, withdrawals will be paused until the target is reached.", user.phone_number)
                return Response({"message": "Payment successful"}, status=200)

            # Respond with a success message
            return JsonResponse({"message": "Webhook received successfully"}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
# Create an instance of the view
webhook_view = WebhookView.as_view()

class CheckUserMomo(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = CheckMomoSerializer
    def post(self, request, *args, **kwargs):
        phone_number = request.user.phone_number
        operator = request.data.get('operator')
        operator_code = Operator.objects.get(name=operator).code
        check = check_momo(phone_number, operator_code)
        if not check:
            return Response({"error": "Invalid phone number or operator code"}, status=status.HTTP_400_BAD_REQUEST)
        data = {
            "data": check['data']
        }
        return Response(data, status=status.HTTP_200_OK)

class TransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

class UserWalletView(generics.ListAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
    def get_queryset(self):
        return Wallet.objects.get(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = WalletSerializer(queryset)
        #Additional data which segments total balnce into 6 groups with increasing amounts
        additional_data = {
            "amount1": round(queryset.balance/6,2),
            "amount2": round(queryset.balance/3,2),
            "amount3": round(queryset.balance/2,2),
            "amount4": round(queryset.balance/1.5,2),
            "amount5": round(queryset.balance/1.2,2),
            "earnings": queryset.balance - queryset.deposit
        }
        data = serializer.data
        data.update(additional_data)
        return Response(data, status=status.HTTP_200_OK)

class IncreaseBalancePrediction(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PredictionSerializer
    def post(self, request, *args, **kwargs):
        amount = request.data.get('amount')
        type = request.data.get('type')
        wallet = Wallet.objects.get(user=request.user)
        if type == "increase":
            wallet.balance += float(amount)
            wallet.save()
            # Send balance update to the WebSocket consumer
            channel_layer = get_channel_layer()
            balance_data ={
                "new_balance": wallet.balance,
                "earnings": wallet.balance - wallet.deposit
            }
            async_to_sync(channel_layer.group_send)(
                f"user_{request.user.id}",  # Unique group for each user
                {
                    "type": "send_balance_update",
                    "new_balance": balance_data,
                }
            )
        elif type == "decrease":
            wallet.balance -= float(amount)
            wallet.save()
            # Send balance update to the WebSocket consumer
            channel_layer = get_channel_layer()
            balance_data ={
                "new_balance": wallet.balance,
                "earnings": wallet.balance - wallet.deposit
            }
            async_to_sync(channel_layer.group_send)(
                f"user_{request.user.id}",  # Unique group for each user
                {
                    "type": "send_balance_update",
                    "new_balance": balance_data,
                }
            )
            return Response({"message": "Balances decreased successfully"}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid type"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Balances increased successfully"}, status=status.HTTP_200_OK)
#Worker APIS
# worker to increase balance in all active wallets according to number of users created in that day.
class IncreaseBalance(APIView):
    def get(self, request, *args, **kwargs):
        start_of_day = datetime.combine(datetime.now().date(), datetime.min.time())
        end_of_day = datetime.combine(datetime.now().date(), datetime.max.time())
        
        number_of_users = Customer.objects.filter(date_joined__range=(start_of_day, end_of_day)).count()
        wallets = Wallet.objects.filter(active=True)
        for wallet in wallets:
            wallet.balance += 0.01 * number_of_users
            wallet.save()
            send_sms(f"Congratulations! Your balance has been increased by GHS {0.01 * number_of_users} Today.", wallet.user.phone_number)
        return Response({"message": "Balances increased successfully"}, status=status.HTTP_200_OK)

class RemoveWalletEligibility(APIView):
    def get(self, request, *args, **kwargs):
        start_of_day = datetime.combine(datetime.now().date(), datetime.min.time())
        end_of_day = datetime.combine(datetime.now().date(), datetime.max.time())
        wallets = Wallet.objects.filter(active=True, eligible=True, date_made_eligible__range=(start_of_day, end_of_day))
        for wallet in wallets:
            wallet.eligible = False
            wallet.save()
        return Response({"message": "Wallets made ineligible successfully"}, status=status.HTTP_200_OK)
#List Top Earners
class TopEarners(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Wallet.objects.all().order_by('-balance')[:5]
        data = []
        for wallet in wallets:
            data.append({
                "username": wallet.user.username,
                "balance": wallet.balance,
                "deposit": wallet.deposit
            })
        return Response(data, status=status.HTTP_200_OK)

#User Comments
class CommentView(generics.ListCreateAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    pagination_class = PageNumberPagination

    
    def get_queryset(self):
        return Comment.objects.all().order_by('-created_at')[:5]
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GameView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = GameSerializer
    def post(self, request, *args, **kwargs):
        game_name = request.data.get('name')
        try:
            game = Game.objects.get(name=game_name, user=request.user)
            game.created_at = datetime.now()
        except Game.DoesNotExist:
            game = Game.objects.create(name=game_name, user=request.user, active=True, created_at=datetime.now())
        
        game.save()

        data = {
            "message": "Game Created",
            "timestamp": game.created_at,
            "name": game.name,
            "active": game.active
        }
        return Response(data, status=status.HTTP_200_OK)
    
    def get(self, request, *args, **kwargs):
        game_name = request.data.get('name')
        game = Game.objects.get(user=request.user, name=game_name)
        if game.created_at + timedelta(hours=2) < datetime.now():
            game.active = False
        else:
            game.active = True
        
        data ={
            "name": game.name,
            "active": game.active,
            "created_at": game.created_at
        }
        return Response(data, status=status.HTTP_200_OK)