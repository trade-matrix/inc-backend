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
from .utils import send_money, send_sms, check_momo, payment, status_check
from django.http import JsonResponse
from django.utils.decorators import method_decorator
import json
from django.views.decorators.csrf import csrf_exempt
import datetime
from datetime import datetime, timedelta
from django.utils import timezone  # Use Django's timezone utility
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
            payment_response = payment(investment.amount, investment.title, user.username)
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
                reference = request.user.reference
                user = Customer.objects.get(reference=reference)
                user.verified = True
                user.save()
                response = status_check(reference)
                if not status_check:
                    return Response({"message":"Huge Error"})
                else:
                    if response['data']['status'] == 'success':
                        investment = Investment.objects.get(title=response['data']['metadata']['investment'])
                        wallet,_ = Wallet.objects.get_or_create(user=user)
                        # Update the wallet balance
                        if not user.referred_by:
                            wallet.balance += ((float(response['data']['amount_paid'])*(investment.interest)) + float(response['data']['amount_paid']))
                            wallet.deposit += float(response['data']['amount_paid'])  # For example, adding a deposit
                            # Update the wallet balance
                            wallet.active = True
                            wallet.eligible = True
                            wallet.date_made_eligible = datetime.now()
                            wallet.save()
                            # Create a transaction record
                            transaction = Transaction.objects.create(user=user, amount=float(response['data']['amount_paid']), status='completed', type='deposit')
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
                            wallet.balance += ((float(response['data']['amount_paid'])*(investment.interest)) + float(response['data']['amount_paid']))*0.85
                            wallet.deposit += float(response['data']['amount_paid'])  # For example, adding a deposit
                            # Update the wallet balance
                            wallet.active = True
                            wallet.eligible = True
                            wallet.date_made_eligible = datetime.now()
                            wallet.save()
                            # Create a transaction record
                            transaction = Transaction.objects.create(user=user, amount=float(response['data']['amount_paid']), status='completed', type='deposit')
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
                            referrer_wallet.balance += (float(response['data']['amount_paid'])*investment.interest*0.15)
                            referrer_wallet.save()
                            transaction = Transaction.objects.create(user=user.referred_by, amount=(float(response['data']['amount_paid'])*investment.interest*0.15), status='completed', type='referal', reffered=user.username)
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
                    else:
                        return Response({"message": "Payment failed"}, status=status.HTTP_400_BAD_REQUEST)

class WithdrawfromWallet(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = Withdraw
    def post(self, request, *args, **kwargs):
        user = request.user
        wallet = Wallet.objects.get(user=user)
        amount = request.data.get('amount')
        operator = request.data.get('operator')
        phone_number = request.data.get('phone_number')
        if wallet.balance >= float(amount):
            result = send_money(amount, phone_number, operator, user.id)
            if not result:
                Requested_Withdraw.objects.create(user=user, amount=amount, phone_number=phone_number, operator=operator)
                send_sms("Your withdrawal has been initiated successfully. However, it will be processed manually. Please be patient.", user.phone_number)
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
                #Send sms to notify admins
                send_sms(f"Dear Admin,\n{user.username} has initiated a withdrawal of GHS {amount}. Please process it manually.", "0599971083")
                return Response({"message": "Withdrawal successful"}, status=status.HTTP_200_OK)
            send_sms("Your withdrawal has been initiated successfully.", user.phone_number)
            user.withdrawal_reference = result.get('data').get('reference')
            user.save()
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
class WebhookView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # Parse the JSON body
            payload = json.loads(request.body.decode('utf-8'))

            # Here you can handle the notification (e.g., update your database, etc.)
            if payload.get('event') == 'transfer.success':
                reference = payload['data']['reference']
                user = Customer.objects.get(withdrawal_reference=reference)
                phone_number = user.phone_number
                user_id = user.pk
                investments = Investment.objects.filter(user__id=user.id)
                wallet = Wallet.objects.get(user=user_id)
                wallet.active = False
                wallet.balance = 0
                wallet.deposit = 0
                wallet.save()
                # Send balance update to the WebSocket consumer
                balance_data ={
                    "new_balance": wallet.balance,
                    "earnings": 0
                }
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}",  # Unique group for each user
                    {
                        "type": "send_balance_update",
                        "new_balance": balance_data,
                    }
                )
                for investment in investments:
                    investment.user.remove(user_id)
                    investment.save()
                send_sms("Your withdrawal was successful", phone_number)
            elif payload.get('event') == 'transfer.failed':
                reference = payload['data']['reference']
                user = Customer.objects.get(withdrawal_reference=reference)
                user_id = user.pk
                phone_number = user.phone_number
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
                print(reference)
                try:
                    user = Customer.objects.get(reference=reference)
                    user.verified = True
                    user.save()
                except Customer.DoesNotExist:
                    return Response({"error": "User not found"}, status=404)
                amount = float(payload['data']['amount'])-float(payload['data']['fee'])
                investment = Investment.objects.get(amount=amount)
                wallet,_ = Wallet.objects.get_or_create(user=user)
                # Update the wallet balance
                if not user.referred_by:
                    wallet.balance += (amount*(investment.interest)) + amount
                    wallet.deposit += amount  # For example, adding a deposit
                    # Update the wallet balance
                    wallet.active = True
                    wallet.eligible = True
                    wallet.date_made_eligible = datetime.now()
                    wallet.save()
                    # Create a transaction record
                    transaction = Transaction.objects.create(user=user, amount=amount, status='completed', type='deposit')
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
                    wallet.balance += ((amount*(investment.interest)) + amount)*0.85
                    wallet.deposit += amount  # For example, adding a deposit
                    # Update the wallet balance
                    wallet.active = True
                    wallet.eligible = True
                    wallet.date_made_eligible = datetime.now()
                    wallet.save()
                    # Create a transaction record
                    transaction = Transaction.objects.create(user=user, amount=amount, status='completed', type='deposit')
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
                    referrer_wallet.balance += (amount*investment.interest)*0.15
                    referrer_wallet.save()
                    transaction = Transaction.objects.create(user=user.referred_by, amount=(amount*investment.interest)*0.15, status='completed', type='referal', reffered=user.username)
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
webhook_view = WebhookView.as_view()

class CheckUserMomo(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = CheckMomoSerializer
    def post(self, request, *args, **kwargs):
        phone_number = request.data.get('phone_number')
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
        try:
            score = request.data.get('score')
        except:
            pass
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
        if score:
            wallet.balance += float(score)/10
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

class SetGameTodayFalse(APIView):
    def get(self, request, *args, **kwargs):
        games = Game.objects.all()
        for game in games:
            game.today = False
            game.save()
        return Response({"message": "Games set to today=False successfully"}, status=status.HTTP_200_OK)
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
        try:
            game_name = request.data.get('name')
            if game_name == '':
                return Response({"message": "Game Name is Empty"}, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response({"message": "Invalid game name"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            game = Game.objects.get(name=game_name, user=request.user)
            if game.today:
                return Response({"message": "Game already initiated today"}, status=status.HTTP_400_BAD_REQUEST)
            game.created_at = datetime.now()
        except Game.DoesNotExist:
            game = Game.objects.create(name=game_name, user=request.user, active=True, today=True, created_at=datetime.now())
        
        game.save()

        data = {
            "message": "Game Created",
            "timestamp": game.created_at,
            "name": game.name,
            "active": game.active
        }
        return Response(data, status=status.HTTP_200_OK)
    
    def get(self, request, *args, **kwargs):
        user = request.user
        math_game, _ = Game.objects.get_or_create(user=user, name='Math')
        prediction_game, _ = Game.objects.get_or_create(user=user, name='Prediction')

        # Compare timezone-aware datetime objects
        now = timezone.now()  # Get the current time with timezone awareness

        if math_game.created_at:
            if math_game.created_at + timedelta(hours=2) < now:
                math_game.active = False
            else:
                math_game.active = True
            math_game.save()

        if prediction_game.created_at:
            if prediction_game.created_at + timedelta(hours=2) < now:
                prediction_game.active = False
            else:
                prediction_game.active = True
            prediction_game.save()

        # Prepare response data
        data = {
            "Math": math_game.active,
            "Prediction": prediction_game.active
        }

        # Add timestamps to the response
        if math_game.created_at:
            data['Math_timestamp'] = math_game.created_at
        if prediction_game.created_at:
            data['Prediction_timestamp'] = prediction_game.created_at

        return Response(data, status=status.HTTP_200_OK)
