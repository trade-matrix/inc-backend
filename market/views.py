from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework import permissions
from .models import Investment, Pool, PoolParticipant
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Wallet, Operator, Transaction, Comment, Requested_Withdraw, Game
from .serializers import InvestmentSerializer, RequesttoInvest, PredictionSerializer, Withdraw, CheckMomoSerializer, TransactionSerializer, WalletSerializer, CommentSerializer, GameSerializer
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.response import Response
from accounts.models import Customer, Ref
from .utils import send_sms, check_momo, status_check, handle_payment, withdraw,paystack_payment, paystack_create_recipient, paystack_send_money, paystack_balance_check,update_user, add_to_pool, add_to_deposit, distribute_pool_earnings
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from accounts.utils import send_otp
import json
from django.views.decorators.csrf import csrf_exempt
import datetime
from datetime import datetime, timedelta
from django.utils import timezone  # Use Django's timezone utility
#pagination
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
import logging
import random
from decimal import Decimal
from django.db.models import F # Not used currently, but keep for potential atomic updates

MULTIPLIER_A = 2.0
MULTIPLIER_B = 1.5
MULTIPLIER_C = 1.0

logger = logging.getLogger(__name__)

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

class CreatePaymentLink(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
    def post(self, request, *args, **kwargs):
        user = request.user
        amount = float(request.data.get('amount'))
        type = request.data.get('type')
        email = user.email
        phone_number = user.phone_number
        payment_response = paystack_payment(amount, email, phone_number, type)
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
            # Check if balance is a successful response with the expected structure
            if isinstance(balance, dict) and balance.get('status') and balance.get('message') == "Balances retrieved":
                b = balance['data'][0]['balance']/100
            else:
                return Response({"error": "Could not retrieve balance"}, status=status.HTTP_400_BAD_REQUEST)
        except:
            return Response({"error": "Could not retrieve balance"}, status=status.HTTP_400_BAD_REQUEST)
        data = []
        
        if wallet.deposit and wallet.balance > 0:
            data.append({
                f"amount1": wallet.withdrawable
            })
            if not float(b) > wallet.withdrawable:
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            return Response(data, status=status.HTTP_200_OK)
        return Response({"error": "No deposit available for withdrawal"}, status=status.HTTP_400_BAD_REQUEST)
    
@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            # Parse the JSON body
            payload = json.loads(request.body.decode('utf-8'))
            #Check if the event is a charge.success
            if payload.get('event') == 'charge.success':
                reference = payload['data']['reference']
                type = payload['data']['metadata']['type']
                if type == 'registration':
                    try:
                        # Try to get user directly or through reference
                        try:
                            user = Customer.objects.get(reference=reference)
                        except Customer.DoesNotExist:
                            try:
                                ref = Ref.objects.get(reference=reference)
                                user = ref.user
                            except Ref.DoesNotExist:
                                return JsonResponse({"error": "Referral not found"}, status=404)
                        
                        # Update user status
                        user.paid = True
                        user.verified = True
                        user.is_active = True
                        user.save()
                        #Create and update user's wallet
                        wallet,_ = Wallet.objects.get_or_create(user=user)
                        wallet.deposit += 200
                        wallet.balance += 100
                        wallet.save()
                        # Send OTP
                        send_otp(user.phone_number, user.username)
                        
                        # Handle referral bonus
                        if user.referred_by:
                            referrer = user.referred_by
                            if not referrer.affiliate:
                                referrer.affiliate = True
                                referrer.save()
                            referrer_wallet = Wallet.objects.get(user=referrer)
                            referrer_wallet.withdrawable += 100
                            referrer_wallet.balance += 100
                            referrer_wallet.save()
                            Transaction.objects.create(user=referrer, amount=100, status='completed', type='referal', reffered=user.username)

                        # Handle vendor bonus
                        if user.vendor:
                            vendor = user.vendor
                            vendor_wallet = Wallet.objects.get(user=vendor.user)
                            vendor_wallet.balance += 20
                            vendor_wallet.withdrawable += 20
                            vendor_wallet.save()
                            
                    except Exception as e:
                        logger.error(f"Registration webhook error: {str(e)}")
                        return JsonResponse({"error": str(e)}, status=500)
                elif type == 'deposit':
                    # Use the reference from the webhook payload
                    reference = payload['data']['reference']
                    try:
                        # Find the Ref object using the reference
                        ref = Ref.objects.get(reference=reference)
                        user = ref.user
                    except Ref.DoesNotExist:
                        # Log the reference that wasn't found for debugging
                        logger.error(f"Webhook error: Ref object not found for reference {reference}")
                        return JsonResponse({"error": "User reference not found"}, status=404)
                    except Exception as e:
                        # Catch any other unexpected errors during user lookup
                        logger.error(f"Webhook error during user lookup for reference {reference}: {str(e)}")
                        return JsonResponse({"error": "Failed to process deposit webhook"}, status=500)

                    # Proceed with deposit logic only if user was found
                    amount = float(payload['data']['amount'])/100
                    # Ensure wallet exists or create it
                    wallet, created = Wallet.objects.get_or_create(user=user)
                    # Update wallet balance
                    wallet.deposit += amount # Ensure Decimal type
                    wallet.balance += amount
                    wallet.withdrawable += amount
                    wallet.save()
                    # Record transaction
                    Transaction.objects.create(user=user, amount=Decimal(str(amount)), status='completed', type='deposit')


                    return Response({"message": "Deposit successful"}, status=200)
            
            # Return success for other events
            return JsonResponse({"message": "Webhook received"}, status=200)
            
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({"error": "Server error"}, status=500)
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
            if user.platform == 'TM':
                w = Wallet.objects.get(user=user)
                send = paystack_send_money(wallet.amount, wallet.phone_number, user.pk, user.recepient_code)
                if send:
                    wallet.settled = True
                    w.amount_from_games += wallet.amount
                    w.balance -= wallet.amount
                    w.save()
                    wallet.save()
                    send_sms(f"Dear {user.username},\nCongratulations, your withdrawal of GHS {wallet.amount} has been processed successfully. Thank you for your patience.", user.phone_number)
                    update_user(user.email, "Congratulations", "Congratulations! Your withdrawal has been processed successfully.", "withdraw_s.html")
                wallet.messaged = True
                wallet.save()
        return Response({"message": "Alerts sent successfully"}, status=status.HTTP_200_OK)

class AlertUsersonCompletedWithdrawalGC(APIView):
    def get(self, request, *args, **kwargs):
        wallets = Requested_Withdraw.objects.filter(settled=False, messaged=False)
        for wallet in wallets:
            user = wallet.user
            if user.platform == 'GC':
                w = Wallet.objects.get(user=user)
                send = paystack_send_money(wallet.amount, wallet.phone_number, user.pk, user.recepient_code)
                if send:
                    wallet.settled = True
                    w.amount_from_games += wallet.amount
                    w.balance -= wallet.amount
                    w.save()
                    wallet.save()
                    send_sms(f"Dear {user.username},\nCongratulations, your withdrawal of GHS {wallet.amount} has been processed successfully. Thank you for your patience.", user.phone_number)
                    update_user(user.email, "Congratulations", "Congratulations! Your withdrawal has been processed successfully.", "withdraw_s.html")
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
    # serializer_class = GameSerializer # Removed as we handle validation manually

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return Response({"error": "User wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        selection_data = request.data.get('selection') # Expecting a list/array like [1, 5, 10, 25, 30]
        amount_str = request.data.get('amount')

        # --- Input Validation ---
        if not amount_str:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

        if not selection_data or not isinstance(selection_data, list):
             return Response({"error": "Selection must be a list of 5 numbers"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Convert selection to integers and validate length/uniqueness/range
            selection = [int(s) for s in selection_data]
            if len(selection) != 5:
                raise ValueError("Selection must contain exactly 5 numbers")
            if len(set(selection)) != 5:
                raise ValueError("Selection must contain unique numbers")
            # Define valid number range (e.g., 1 to 50)
            MIN_NUMBER = 0
            MAX_NUMBER = 100 # Define your desired max number here
            if not all(MIN_NUMBER <= num <= MAX_NUMBER for num in selection):
                 raise ValueError(f"Numbers must be between {MIN_NUMBER} and {MAX_NUMBER}")
        except (ValueError, TypeError) as e:
            return Response({"error": f"Invalid selection: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        # --- Check Balance ---
        if wallet.balance < amount:
            return Response({"error": "Insufficient funds to play game"}, status=status.HTTP_400_BAD_REQUEST)

        # --- Deduct Bet Amount (Initial) ---
        # We save the wallet state later after calculating potential winnings
        wallet.balance -= amount

        # Create debit transaction record
        Transaction.objects.create(
            user=user,
            amount=-amount, # Negative for debit
            status='completed',
            type='game_bet',
            description=f"Lucky Draw bet ({', '.join(map(str, selection))})"
        )

        # --- Track Daily Entries ---
        today_min = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_max = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        # Count games created today globally before this one
        daily_entries_count = Game.objects.filter(
            name='Lucky Draw', # Filter specifically for this game type if needed
            created_at__range=(today_min, today_max)
        ).count()

        # --- Game Logic ---
        matches = 0
        multiplier = Decimal('0.0')
        winning_numbers = []
        possible_numbers = list(range(MIN_NUMBER, MAX_NUMBER + 1))

        # Incentive Check: First 10 entries get a guaranteed 2x win (3 matches)
        force_win = daily_entries_count < 10

        if force_win:
            matches = 3
            multiplier = Decimal('2.0')
            # Force 3 matches:
            correct_choices = random.sample(selection, 3)
            incorrect_choices_needed = 2
            incorrect_choices = []
            numbers_not_in_selection = [n for n in possible_numbers if n not in selection]

            # Ensure we can find enough unique numbers outside the user's selection
            potential_incorrect = [n for n in possible_numbers if n not in correct_choices]
            if len(potential_incorrect) >= incorrect_choices_needed:
                 incorrect_choices = random.sample(potential_incorrect, incorrect_choices_needed)
                 # Ensure the chosen incorrect numbers are not also in the correct_choices (should be guaranteed by the list comprehension)
                 # and also not in the original user selection if possible
                 temp_incorrect = []
                 candidates = [n for n in potential_incorrect if n not in selection]
                 if len(candidates) >= incorrect_choices_needed:
                     temp_incorrect = random.sample(candidates, incorrect_choices_needed)
                 else: # Not enough numbers outside selection, fill with remaining unique possibilities
                     temp_incorrect = random.sample(potential_incorrect, incorrect_choices_needed)
                 incorrect_choices = temp_incorrect

            else:
                 # Extremely unlikely edge case: Cannot find 2 unique numbers not in correct_choices. Log error?
                 # For now, fallback to standard random numbers? Or maybe guarantee win differently?
                 # Fallback: just generate 5 random numbers and hope for the best (or handle error)
                 logger.warning(f"Could not reliably force 3 matches for user {user.id}. Not enough unique numbers.")
                 # Let's still try to construct *some* winning numbers
                 winning_numbers = random.sample(possible_numbers, 5) # Fallback, might not give 3 matches
                 matches = len(set(selection) & set(winning_numbers)) # Recalculate matches
                 # Re-evaluate multiplier based on actual fallback matches
                 if matches == 3: multiplier = Decimal('2.0')
                 elif matches == 4: multiplier = Decimal('4.0')
                 elif matches == 5: multiplier = Decimal('5.0')
                 else: multiplier = Decimal('0.0')


            if not winning_numbers: # If fallback wasn't triggered
                winning_numbers = correct_choices + incorrect_choices
                random.shuffle(winning_numbers)

            message = f"Lucky Draw First {daily_entries_count + 1}/10 Bonus! You matched {matches} numbers." # Indicate bonus attempt


        else: # Normal Logic
            # Generate winning numbers guaranteed NOT to be in the user's selection
            numbers_not_in_selection = [n for n in possible_numbers if n not in selection]
            
            # Check if there are enough unique numbers available outside the user's selection
            if len(numbers_not_in_selection) < 5:
                # This is an edge case, shouldn't happen if MAX_NUMBER - MIN_NUMBER + 1 is reasonably larger than 5
                # Log an error and potentially return an error response or use a fallback strategy
                logger.error(f"Cannot generate 5 unique winning numbers different from user {user.id}'s selection: {selection}. Available: {numbers_not_in_selection}")
                # Fallback: Generate completely random numbers (might accidentally match, but it's a fallback)
                winning_numbers = random.sample(possible_numbers, 5)
                matches = len(set(selection) & set(winning_numbers))
            else:
                winning_numbers = random.sample(numbers_not_in_selection, 5)
                matches = 0 # By definition, matches will be 0

            # Since we forced no matches in the normal case (unless fallback occurred):
            if matches == 0:
                 multiplier = Decimal('0.0')
                 message = f"Sorry, you matched {matches} numbers. Better luck next time!"
            # Handle the unlikely fallback case where matches might occur
            elif matches == 3: 
                 multiplier = Decimal('2.0')
                 message = f"Good job! You matched 3 numbers! (Fallback)"
            elif matches == 4: 
                 multiplier = Decimal('4.0')
                 message = f"Excellent! You matched 4 numbers! (Fallback)"
            elif matches == 5: 
                 multiplier = Decimal('5.0')
                 message = f"Wow! You matched all 5 numbers! (Fallback)"
            # else: # This line is now technically covered by matches == 0 above
            #     multiplier = Decimal('0.0')
            #     message = f"Sorry, you matched {matches} numbers. Better luck next time!"

        # --- Calculate Winnings & Update Wallet ---
        winnings = amount * multiplier
        won_game = winnings > 0 # Determine if the user won

        if winnings > 0:
            wallet.balance += winnings
            wallet.amount_from_games = (wallet.amount_from_games or Decimal('0.0')) + winnings # Ensure amount_from_games is not None
            # Create credit transaction record
            Transaction.objects.create(
                user=user,
                amount=winnings,
                status='completed',
                type='game_win',
                description=f"Lucky Draw win ({matches} matches)"
            )

        # --- Save Final Wallet State and Game Record ---
        try:
            # Ensure amount_from_games is Decimal before saving
            if wallet.amount_from_games is None:
                 wallet.amount_from_games = Decimal('0.0')
            wallet.save()
        except Exception as e:
            logger.error(f"Error saving wallet for user {user.id} after game: {e}")
            # Consider reverting the bet transaction or handling the error appropriately
            return Response({"error": "Failed to update wallet."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


        game = Game.objects.create(
            user=request.user,
            name='Lucky Draw', # Game name
            selection=json.dumps(selection), # Store selection as JSON string
            winning_numbers=json.dumps(winning_numbers), # Store winning numbers as JSON string
            amount_bet=amount,
            matches=matches,
            winnings=winnings,
            active=False # Game instance represents a completed game
        )

        # --- Send Final Balance Update via WebSocket ---
        # (Assuming send_balance_update logic is available or defined elsewhere)
        try:
            channel_layer = get_channel_layer()
            balance_data = {
                "new_balance": float(wallet.balance),
                "earnings": float(wallet.amount_from_games)
            }
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "send_balance_update",
                    "new_balance": balance_data,
                }
            )
        except Exception as e:
             logger.error(f"Error sending balance update via WebSocket for user {user.id}: {e}")
             # Continue execution, but log the error

        # --- Construct Response ---
        response_data = {
            "message": message,
            "user_selection": selection,
            "winning_numbers": winning_numbers,
            "matches": matches,
            "amount_bet": float(amount),
            "winnings": float(winnings),
            "new_balance": float(wallet.balance),
            "timestamp": game.created_at.isoformat(),
            "won": won_game # Add the won status here
        }
        return Response(response_data, status=status.HTTP_200_OK)

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

class UserPoolGroupStatus(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
    def get(self, request, *args, **kwargs):
        user = request.user
        
        # Find the pool that the user is in
        try:
            # Get the user's pool participation
            pool_participant = PoolParticipant.objects.filter(user=user).first()
            
            if not pool_participant:
                return Response({"error": "You are not currently in any pool"}, status=status.HTTP_404_NOT_FOUND)
                
            pool = pool_participant.pool
            
            # Get all participants sorted by join date (as in distribute_pool_earnings)
            participants = PoolParticipant.objects.filter(pool=pool).order_by('joined_at')
            num_users = participants.count()
            
            # Find the position of the current user
            user_position = 0
            for i, participant in enumerate(participants):
                if participant.user.id == user.id:
                    user_position = i
                    break
            
            # Determine the groups based on the same logic in distribute_pool_earnings
            if num_users < 10:
                group_a_count = 1
                group_b_count = 1 if num_users > 1 else 0
                group_c_count = num_users - group_a_count - group_b_count
            else:
                group_a_count = int(num_users * 0.10)
                group_b_count = int(num_users * 0.20)
                group_c_count = num_users - group_a_count - group_b_count
            
            # Determine current group and next group
            current_group = ""
            next_group = ""
            users_needed = 0
            
            if user_position < group_a_count:
                current_group = "A"
                next_group = None  # Already in the highest group
                users_needed = 0
            elif user_position < (group_a_count + group_b_count):
                current_group = "B"
                next_group = "A"
                # Calculate users needed to expand group A enough to include this user
                if num_users >= 10:
                    # For 10+ users, group A is 10% of users
                    # Calculate how many total users needed for this user to be in top 10%
                    current_position = user_position + 1  # 1-based position
                    users_needed = max(0, int(current_position / 0.10) - num_users)
                else:
                    # For <10 users, group A is just 1 person
                    users_needed = user_position  # Need enough users so that user_position becomes 0
            else:
                current_group = "C"
                # Determine if next achievable group is A or B
                if user_position < group_a_count + group_b_count + (num_users * 0.10):
                    next_group = "B"
                    # Calculate how many users needed to expand group B enough to include this user
                    if num_users >= 10:
                        # Current position within Group C
                        position_in_c = user_position - (group_a_count + group_b_count) + 1
                        # Need enough new users to push user into group B
                        new_total = num_users
                        while True:
                            # Calculate new group sizes
                            new_group_a = int(new_total * 0.10)
                            new_group_b = int(new_total * 0.20)
                            # Check if user would be in group B
                            if user_position < new_group_a + new_group_b:
                                break
                            new_total += 1
                        users_needed = new_total - num_users
                    else:
                        # For <10 users, just need to be in top 2 positions
                        users_needed = user_position - 1
                else:
                    next_group = "B"  # Very far down, aim for B first
                    # Similar calculation to above
                    if num_users >= 10:
                        # Current position within Group C
                        position_in_c = user_position - (group_a_count + group_b_count) + 1
                        # Need enough new users to push user into group B
                        new_total = num_users
                        while True:
                            # Calculate new group sizes
                            new_group_a = int(new_total * 0.10)
                            new_group_b = int(new_total * 0.20)
                            # Check if user would be in group B
                            if user_position < new_group_a + new_group_b:
                                break
                            new_total += 1
                        users_needed = new_total - num_users
                    else:
                        # For <10 users, just need to be in top 2 positions
                        users_needed = user_position - 1
            
            # Get the multiplier for the current group
            multiplier = 0
            if current_group == "A":
                multiplier = MULTIPLIER_A
            elif current_group == "B":
                multiplier = MULTIPLIER_B
            else:
                multiplier = MULTIPLIER_C
                
            response_data = {
                "pool_id": pool.id,
                "total_participants": num_users,
                "user_position": user_position + 1,  # 1-indexed position for display
                "current_group": current_group,
                "current_multiplier": multiplier,
                "next_group": next_group,
                "users_needed_for_promotion": users_needed,
                "deposit_amount": pool_participant.deposit_amount
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting user pool status: {str(e)}")
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DistributePoolEarnings(APIView):
    def get(self, request, *args, **kwargs):
        pools = Pool.objects.all()
        for pool in pools:
            distribute_pool_earnings(pool.id)
        return Response({"message": "Pools distributed successfully"}, status=status.HTTP_200_OK)

