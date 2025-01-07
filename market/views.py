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
from accounts.models import Customer, Ref
from .utils import send_sms, check_momo, status_check, handle_payment, withdraw,paystack_payment, paystack_create_recipient, paystack_send_money, paystack_balance_check
from django.http import JsonResponse
from django.utils.decorators import method_decorator
import json
from django.views.decorators.csrf import csrf_exempt
import datetime
from datetime import datetime, timedelta
from django.utils import timezone  # Use Django's timezone utility
#pagination
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q

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
            # Check if the user has already invested in another firm
            existing_investments = Investment.objects.filter(user=user)
            if not existing_investments.exists():
                payment_response = paystack_payment(investment.amount, investment.title, user.username)
                if 'error' in payment_response:
                    return Response({"error": "Payment Initiation failed"}, status=status.HTTP_400_BAD_REQUEST)
                reference = payment_response['data']['reference']
                user.reference = reference
                user.save()
                Ref.objects.create(reference=reference, user=user)
                data = {
                    "payment_response": payment_response,
                }
                return Response(data, status=status.HTTP_200_OK)
            else:
                return Response({"error": "User has already invested in another firm"}, status=status.HTTP_400_BAD_REQUEST)
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
        if 'mtn' in operator.lower():
            opr = 'MTN'
        elif 'vodafone' in operator.lower():
            opr = 'VOD'
        elif 'airtel' in operator.lower():
            opr = 'ATL'      
        rcp = paystack_create_recipient(user.username, phone_number, opr)
        #withdarw = withdraw_optout(user,wallet, amount, operator, phone_number)
        if rcp:
            if not user.recepient_code:
                recipient_code = rcp['data']['recipient_code']
                user.recepient_code = recipient_code
                user.save()
            withdarw = withdraw(user, wallet, amount, operator, phone_number)
            if withdarw:
                try:
                    wit = withdarw['error']['message']
                    return Response({"message": wit}, status=status.HTTP_200_OK)
                except:
                    return Response({"message": "Withdrawal successful"}, status=status.HTTP_200_OK)
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Withdrawal failed"}, status=status.HTTP_400_BAD_REQUEST)
    #Get method to get avilable user amount for withdrawal
    def get(self, request, *args, **kwargs):
        user = request.user
        wallet = Wallet.objects.get(user=user)
        #investments = Investment.objects.filter(user__id=user.id)
        balance = paystack_balance_check()
        try:
            b = balance['data']['balance']/100
        except:
            return Response({"error": balance}, status=status.HTTP_400_BAD_REQUEST)
        data = []
        
        if wallet.deposit and wallet.balance > 0:
            data.append({
                f"amount1": wallet.balance
            })
            if not float(b) > wallet.balance:
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            return Response(data, status=status.HTTP_200_OK)
        return Response({"error": "No deposit available for withdrawal"}, status=status.HTTP_400_BAD_REQUEST)
    
@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # Parse the JSON body
            payload = json.loads(request.body.decode('utf-8'))

            # Here you can handle the notification (e.g., update your database, etc.)
            if payload.get('event') == 'transfer.success':
                rcp = payload['data']['recepient']['recipient_code']
                user = Customer.objects.get(recipient_code=rcp)
                phone_number = user.phone_number
                user_id = user.pk
                #Update Transaction
                transaction = Transaction.objects.filter(user=user, status='pending', type='withdrawal',amount=float(payload['data']['amount'])/100).first()
                transaction.status = 'completed'
                transaction.save()
            elif payload.get('event') == 'transfer.failed':
                rcp = payload['data']['recipient']['recepient_code']
                user = Customer.objects.get(recipient_code=rcp)
                user_id = user.pk
                phone_number = user.phone_number
                wallet = Wallet.objects.get(user=user_id)
                wallet.balance += float(payload['data']['amount'])/100
                wallet.save()
                send_sms("Your withdrawal failed. Your balance has been reverted.", phone_number)   
            elif payload.get('event') == 'charge.success':
                reference = payload['data']['reference']
                try:
                    user = Customer.objects.get(reference=reference)
                    user.verified = True
                    user.save()
                except Customer.DoesNotExist:
                    ref = Ref.objects.get(reference=reference)
                    user = ref.user
                amount = float(payload['data']['amount'])/100
                investment = Investment.objects.get(amount=amount)
                wallet,_ = Wallet.objects.get_or_create(user=user)
                # Update the wallet balance
                h = handle_payment(user, investment, wallet, amount)
                if not h:
                    return Response({"error": "Payment failed"}, status=400)
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
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')[:7]
    
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
            "earnings": round(queryset.amount_from_games,2)
        }
        data = serializer.data
        data.update(additional_data)
        return Response(data, status=status.HTTP_200_OK)

class IncreaseBalancePrediction(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PredictionSerializer
    
    def post(self, request, *args, **kwargs):
        amount = self.get_float_value(request.data.get('amount'), "amount")
        score = self.get_float_value(request.data.get('score'), "score")
        winnings = self.get_float_value(request.data.get('winnings'), "winnings")
        bet_type = request.data.get('type', None)
        
        if isinstance(amount, Response): return amount  # Error if amount was invalid
        if isinstance(score, Response): return score    # Error if score was invalid
        if isinstance(winnings, Response): return winnings  # Error if winnings were invalid

        wallet = Wallet.objects.get(user=request.user)

        # Handle score logic
        if score is not None:
            self.update_balance(wallet, score/10)
            wallet.amount_from_games += score/10
            wallet.save()
            return self.success_response(wallet, "Score Redeemed Successfully")
        
        # Handle increase or decrease of balance based on bet type
        if bet_type == "decrease" and amount is not None:
            if wallet.balance < amount:
                return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)
            self.update_balance(wallet, -amount)
            message = f"You Lost GHS {amount} on the bet"
            return self.success_response(wallet, message)
            # If winnings are present, increase the balance by the winnings amount
        elif winnings is not None and bet_type == "increase":
            self.update_balance(wallet, winnings)
            message = f"You Won GHS {winnings} on the bet"
            return self.success_response(wallet, message)
        
        # Return error if type is not 'decrease' or amount is missing
        return Response({"error": "Invalid type or missing amount"}, status=status.HTTP_400_BAD_REQUEST)

    def get_float_value(self, value, field_name):
        """Helper method to convert a string value to a float. Returns a Response if conversion fails."""
        if value is None:
            return None  # It's okay if the value is not provided
        try:
            return float(value)
        except ValueError:
            return Response({"error": f"Invalid {field_name} value"}, status=status.HTTP_400_BAD_REQUEST)
    
    def update_balance(self, wallet, amount):
        """Update the wallet balance and send WebSocket notification."""
        wallet.balance += min(amount,1200)
        wallet.amount_from_games += amount
        wallet.save()
        self.send_balance_update(wallet)
    
    def success_response(self, wallet, message):
        """Return a success response after balance update."""
        self.send_balance_update(wallet)
        return Response({
            "message": message,
            "new_balance": wallet.balance
        }, status=status.HTTP_200_OK)

    def send_balance_update(self, wallet):
        """Send the balance update via WebSocket."""
        channel_layer = get_channel_layer()
        balance_data = {
            "new_balance": wallet.balance,
            "earnings": wallet.balance - wallet.deposit
        }
        async_to_sync(channel_layer.group_send)(
            f"user_{wallet.user.id}",
            {
                "type": "send_balance_update",
                "new_balance": balance_data,
            }
        )

#Worker APIS
#Worker to increase balance in all active wallets according to number of users created in that day.
class IncreaseBalance(APIView): 
    def get(self, request, *args, **kwargs):
        start_of_day = datetime.combine(datetime.now().date(), datetime.min.time())
        end_of_day = datetime.combine(datetime.now().date(), datetime.max.time())
        
        number_of_users = Customer.objects.filter(date_joined__range=(start_of_day, end_of_day)).count()
        wallets = Wallet.objects.filter(user__verified=True)
        numbers = []
        for wallet in wallets:
            wallet.balance += 0.01 * number_of_users
            wallet.amount_from_games += 0.01 * number_of_users
            wallet.save()
            numbers.append(wallet.user.phone_number)
        send_sms(f"Congratulations! Your balance has been increased by GHS {0.01 * number_of_users} Today. This daily bonus is as a result of the number of users we got today. Thank you for your hardwork.", numbers)
        return Response({"message": "Balances increased successfully"}, status=status.HTTP_200_OK)

class AlertUsersonCompletedWithdrawal(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Requested_Withdraw.objects.filter(settled=False, messaged=False)
        for wallet in wallets:
            user = wallet.user
            w = Wallet.objects.get(user=user)
            send = paystack_send_money(wallet.amount, wallet.phone_number, user.pk, user.recepient_code)
            if send:
                wallet.settled = True
                w.amount_from_games += wallet.amount
                w.balance -= wallet.amount
                w.save()
                wallet.save()
                send_sms(f"Dear {user.username},\nCongratulations, your withdrawal of GHS {wallet.amount} has been processed successfully. Thank you for your patience.", user.phone_number)
            wallet.messaged = True
            wallet.save()
        return Response({"message": "Alerts sent successfully"}, status=status.HTTP_200_OK)

class SetGameTodayFalse(APIView):
    def get(self, request, *args, **kwargs):
        games = Game.objects.all()
        for game in games:
            game.today = False
            game.save()
        return Response({"message": "Games set to today=False successfully"}, status=status.HTTP_200_OK)

class RevertWithdrawals(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Requested_Withdraw.objects.filter(settled=False, created_at__range=(datetime.now()-timedelta(days=1), datetime.now()))
        for wallet in wallets:
            w = Wallet.objects.get(user=wallet.user)
            w.balance += wallet.amount
            w.save()
            message = f"Dear {wallet.user.username},\nYour withdrawal of GHS {wallet.amount} has been reverted. Please contact support for more information."
            send_sms(message, wallet.user.phone_number)
            print(f"Reverted GHS {wallet.amount} for {wallet.user.username}")
            wallet.settled = True
            wallet.messaged = True
            wallet.save()
        return Response({"message": "Withdrawals reverted successfully"}, status=status.HTTP_200_OK)
#List Top Earners
class TopEarners(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Wallet.objects.filter(
            Q(user__email__isnull=True) | Q(user__email='')
        ).order_by('-amount_from_games')[:5]
        
        data = []
        for wallet in wallets:
            data.append({
                "username": wallet.user.username,
                "balance": wallet.amount_from_games,
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
        wallet = Wallet.objects.get(user=request.user)
        game_name = request.data.get('name')

        if not game_name:
            return Response({"message": "Game Name is Empty"}, status=status.HTTP_400_BAD_REQUEST)

        game,_ = Game.objects.get_or_create(
            name=game_name, user=request.user,
        )
        if game.today:
            return Response({"message": "Game already initiated today"}, status=status.HTTP_400_BAD_REQUEST)
        if wallet.balance < 10:
            return Response({"message": "Insufficient funds to play game"}, status=status.HTTP_400_BAD_REQUEST)
        if wallet.deposit < 10:
            return Response({"message": "Insufficient deposit to play game"}, status=status.HTTP_400_BAD_REQUEST)
        if not wallet.eligible:
            return Response({"message": "Wallet not eligible to play game"}, status=status.HTTP_400_BAD_REQUEST)
        game.today = True
        game.created_at = timezone.now()
        game.active = True
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
        now = timezone.now()  # Get current time with timezone awareness

        # Filter the games belonging to the user and the specific names
        games = Game.objects.filter(user=user, name__in=['Math', 'Prediction'])
        game_status = {}

        for game in games:
            # Set game inactive if it's been created more than 2 hours ago
            if game.created_at and game.created_at + timedelta(hours=2) < now:
                game.active = False
                game.save()

            # Build the game status dictionary
            game_status[game.name] = {
                "active": game.active,
                "timestamp": game.created_at
            }

            # Remove the timestamp if the game is not active
            if not game.active:
                game_status[game.name].pop("timestamp", None)

        return Response(game_status, status=status.HTTP_200_OK)

class TopEarnersGc(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Wallet.objects.filter(
            user__email__isnull=False,  # Ensure email is not null
            user__email__gt=''  # Ensure email is not empty string
        ).order_by('-amount_from_games')[:5]
        
        data = []
        for wallet in wallets:
            data.append({
                "username": wallet.user.username,
                "balance": wallet.amount_from_games,
                "deposit": wallet.deposit,
            })
        return Response(data, status=status.HTTP_200_OK)