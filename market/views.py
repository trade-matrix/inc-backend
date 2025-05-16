from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework import permissions
from .models import Investment, Pool, PoolParticipant
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Wallet, Operator, Transaction, Comment, Requested_Withdraw, Game
from .serializers import InvestmentSerializer, RequesttoInvest, PredictionSerializer, Withdraw, CheckMomoSerializer, TransactionSerializer, WalletSerializer, CommentSerializer
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.response import Response
from accounts.models import Customer, Ref
from .utils import send_sms, check_momo, status_check, withdraw, paystack_payment, paystack_create_recipient, paystack_send_money, paystack_balance_check, update_user, distribute_pool_earnings
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
from django.db.models import F # Not used currently, but keep for potential atomic updates
from django.db import transaction # Import transaction
from decimal import Decimal  # Add this import for Decimal type

# Game constants (can be defined at class level or globally)
LUCKY_DRAW_MIN_NUMBER = 1
LUCKY_DRAW_MAX_NUMBER = 30
COLOR_PICKER_CHOICES = ['red', 'blue', 'green']
COIN_TOSS_CHOICES = ['heads', 'tails']
# Pool multiplier constants
MULTIPLIER_A = 3.0  # Add this constant for pool distribution
MULTIPLIER_B = 2.0  # Add this constant for pool distribution
MULTIPLIER_C = 1.0  # Add this constant for pool distribution

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
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            authenticated_user = Customer.objects.get(pk=request.data.get('user_id'))
        except:
            authenticated_user = None

        if authenticated_user:
            user = authenticated_user
        else:
            phone_from_payload = request.data.get('phone_number')
            if phone_from_payload and isinstance(phone_from_payload, str) and phone_from_payload.strip():
                try:
                    user = Customer.objects.get(phone_number=phone_from_payload.strip())
                except Customer.DoesNotExist:
                    logger.info(f"CreatePaymentLink: No customer found for phone number {phone_from_payload.strip()} when attempting to create payment link.")
                    return Response({"error": "User with the provided phone number not found."}, status=status.HTTP_404_NOT_FOUND)
                except Customer.MultipleObjectsReturned:
                    logger.error(f"CreatePaymentLink: Multiple users found for phone number {phone_from_payload.strip()}. This indicates a data inconsistency.")
                    return Response({"error": "A data inconsistency error occurred. Please contact support."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # Not authenticated and no phone number in payload to identify the user for the transaction.
                return Response({"error": "User authentication is required, or a phone number must be provided in the request data."}, status=status.HTTP_401_UNAUTHORIZED)
        
        # At this point, 'user' should be a valid Customer object.
        raw_amount = request.data.get('amount')
        try:
            amount = float(raw_amount)
            if amount <= 0:
                return Response({"error": "Amount must be a positive number."}, status=status.HTTP_400_BAD_REQUEST)
        except (ValueError, TypeError, AttributeError): # AttributeError if raw_amount is None
            return Response({"error": "Invalid or missing amount."}, status=status.HTTP_400_BAD_REQUEST)
        
        payment_type_from_request = request.data.get('type') 
        if not payment_type_from_request or not payment_type_from_request.strip():
            return Response({"error": "Type is required."}, status=status.HTTP_400_BAD_REQUEST)
        payment_type = payment_type_from_request.strip() # Use the stripped version

        email = user.email # Assuming user.email is always present for an authenticated user
        
        request_phone_number_raw = request.data.get('phone_number')
        request_phone_number_stripped = None
        if request_phone_number_raw and isinstance(request_phone_number_raw, str) and request_phone_number_raw.strip():
            request_phone_number_stripped = request_phone_number_raw.strip()

        if request_phone_number_stripped:
            # Phone number is in the request, use Paystack
            payment_response_obj = paystack_payment(amount, email, request_phone_number_stripped, payment_type)
            
            if not isinstance(payment_response_obj, dict):
                logger.error(f"Paystack payment returned non-dict: {payment_response_obj} for user {user.id} with phone {request_phone_number_stripped}")
                return Response({"error": "Payment initiation failed. Please try again later or contact support."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if payment_response_obj.get('status') is False or 'error' in payment_response_obj:
                error_message = payment_response_obj.get('message')
                if not error_message: # Fallback if 'message' is not there from Paystack
                    error_message = payment_response_obj.get('error', "Payment Initiation failed with payment provider.")
                logger.warning(f"Paystack payment failed for user {user.id} with phone {request_phone_number_stripped}: {error_message}. Response: {payment_response_obj}")
                return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)
            
            data_from_paystack = payment_response_obj.get('data')
            if not (data_from_paystack and isinstance(data_from_paystack, dict) and 'reference' in data_from_paystack):
                logger.error(f"Unexpected successful Paystack response structure for user {user.id} with phone {request_phone_number_stripped}: {payment_response_obj}")
                return Response({"error": "Payment processing failed after initiation. Please contact support."}, status=status.HTTP_400_BAD_REQUEST)

            reference = data_from_paystack['reference']
            user.reference = reference
            user.save()
            Ref.objects.create(reference=reference, user=user) # Assuming Ref model and import exist
            
            response_data_dict = {
                "payment_response": payment_response_obj,
            }
            return Response(response_data_dict, status=status.HTTP_200_OK)
        
        else: # Phone number is NOT in the request (or was empty/whitespace), construct the dynamic URL
            user_registered_phone = user.phone_number # Fallback to user's registered phone
            
            user_phone_for_url = None
            if user_registered_phone and isinstance(user_registered_phone, str) and user_registered_phone.strip():
                user_phone_for_url = user_registered_phone.strip()

            if not user_phone_for_url:
                 logger.warning(f"URL construction failed for user {user.id}: phone_number not in request and no valid registered phone.")
                 return Response({"error": "Phone number not provided in request and no valid registered phone number found for URL construction."}, status=status.HTTP_400_BAD_REQUEST)

            # Construct the URL as per your example, using the 'payment_type' variable which holds the value from request.data.get('type')
            dynamic_url = f"https://trade-matrix.com/momo/reroute/jiojioohkjbniuiujniun/{payment_type}/{amount}/{email}/{user_phone_for_url}"
            
            response_data_dict = {
                "payment_response": dynamic_url,
            }
            return Response(response_data_dict, status=status.HTTP_200_OK)

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
        
        if wallet.withdrawable > 0:
            data.append({
                f"amount1": wallet.withdrawable
            })
            if not float(b) > wallet.withdrawable:
                return Response(data, status=status.HTTP_400_BAD_REQUEST)
            return Response(data, status=status.HTTP_200_OK)
        return Response({"error": "No withdrawable balance available"}, status=status.HTTP_400_BAD_REQUEST)
    
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
                        wallet.deposit += 50
                        wallet.balance += 50
                        wallet.save()
                        # Send OTP
                        #send_otp(user.phone_number, user.username)
                        """
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
                        """   
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
                    wallet.withdrawable += amount*0.95
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
    authentication_classes = [TokenAuthentication, SessionAuthentication] # Assuming these are defined/imported

    # --- Helper functions for Lucky Draw number generation (existing) ---
    def _generate_matching_numbers(self, selection, possible_numbers, num_matches):
        """Generates winning numbers with a specific number of matches."""
        if num_matches > len(selection) or num_matches > 5 or num_matches < 0:
            num_matches = 0 

        if num_matches == 0:
             # For a forced loss (num_matches=0), let non_matching decide probabilistic near-misses
             return self._generate_non_matching_numbers(selection, possible_numbers)

        correct_choices = random.sample(selection, num_matches)
        incorrect_choices_needed = 5 - num_matches
        incorrect_choices = []
        potential_incorrect = [n for n in possible_numbers if n not in correct_choices and n not in selection]
        
        if len(potential_incorrect) >= incorrect_choices_needed:
            incorrect_choices = random.sample(potential_incorrect, incorrect_choices_needed)
        else:
            potential_incorrect_fallback = [n for n in possible_numbers if n not in correct_choices]
            if len(potential_incorrect_fallback) >= incorrect_choices_needed:
                 incorrect_choices = random.sample(potential_incorrect_fallback, incorrect_choices_needed)
            else:
                 logger.error(f"Cannot generate {incorrect_choices_needed} unique incorrect choices for lucky draw.")
                 return random.sample(possible_numbers, 5) # Fallback

        winning_numbers = correct_choices + incorrect_choices
        random.shuffle(winning_numbers)
        return winning_numbers

    def _generate_non_matching_numbers(self, selection, possible_numbers):
        """Generates winning numbers with a controlled, probabilistic number of matches (0, 1, or 2) for Lucky Draw losses."""
        match_counts = [2, 1, 0] # For Lucky Draw, a "loss" can still have some matches
        weights = [0.1, 0.2, 0.7] # Adjusted: 10% for 2, 20% for 1, 70% for 0 (more likely a clear loss)

        chosen_matches = random.choices(match_counts, weights=weights, k=1)[0]
        return self._generate_matching_numbers(selection, possible_numbers, num_matches=chosen_matches)

    # --- Game-Specific Validation Helpers ---
    def _validate_lucky_draw_input(self, request_data):
        selection_data = request_data.get('selection')
        if not selection_data or not isinstance(selection_data, list):
            return None, None, Response({"error": "Selection must be a list of 5 numbers"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            selection = [int(s) for s in selection_data]
            if len(selection) != 5 or len(set(selection)) != 5:
                raise ValueError("Selection must be 5 unique numbers")
            if not all(LUCKY_DRAW_MIN_NUMBER <= num <= LUCKY_DRAW_MAX_NUMBER for num in selection):
                raise ValueError(f"Numbers must be between {LUCKY_DRAW_MIN_NUMBER} and {LUCKY_DRAW_MAX_NUMBER}")
            possible_numbers = list(range(LUCKY_DRAW_MIN_NUMBER, LUCKY_DRAW_MAX_NUMBER + 1))
            return selection, possible_numbers, None
        except (ValueError, TypeError) as e:
            return None, None, Response({"error": f"Invalid selection for Lucky Draw: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    def _validate_color_picker_input(self, request_data):
        chosen_color = request_data.get('color')
        if not chosen_color or chosen_color not in COLOR_PICKER_CHOICES:
            return None, Response({"error": f"Invalid color. Choose from {', '.join(COLOR_PICKER_CHOICES)}"}, status=status.HTTP_400_BAD_REQUEST)
        return chosen_color, None

    def _validate_coin_toss_input(self, request_data):
        chosen_side = request_data.get('side')
        if not chosen_side or chosen_side not in COIN_TOSS_CHOICES:
            return None, Response({"error": f"Invalid side. Choose from {', '.join(COIN_TOSS_CHOICES)}"}, status=status.HTTP_400_BAD_REQUEST)
        return chosen_side, None

    # --- Game-Specific Outcome Generation Helpers ---
    def _generate_lucky_draw_outcome(self, selection, possible_numbers, num_matches_to_force):
        # num_matches_to_force: if strategy dictates win (e.g., 3 matches), or loss (e.g., 0 for probabilistic loss)
        winning_numbers = self._generate_matching_numbers(selection, possible_numbers, num_matches_to_force)
        actual_matches = len(set(selection).intersection(set(winning_numbers)))
        return actual_matches, winning_numbers

    def _generate_color_picker_outcome(self, chosen_color, force_win):
        if force_win:
            winning_color = chosen_color
        else:
            # Ensure it's a loss if force_win is False
            possible_losing_colors = [c for c in COLOR_PICKER_CHOICES if c != chosen_color]
            if not possible_losing_colors: # Should not happen with >1 color choices
                winning_color = random.choice(COLOR_PICKER_CHOICES) 
            else:
                winning_color = random.choice(possible_losing_colors)
        
        matches = 1 if chosen_color == winning_color else 0
        return matches, winning_color

    def _generate_coin_toss_outcome(self, chosen_side, force_win):
        if force_win:
            winning_side = chosen_side
        else:
            winning_side = random.choice([s for s in COIN_TOSS_CHOICES if s != chosen_side])
        matches = 1 if chosen_side == winning_side else 0
        return matches, winning_side

    # --- Core Game Strategy Logic ---
    def _determine_game_strategy_v2(self, user, wallet, amount_decimal, game_type_request):
        user_state_updates = {}
        
        # Special win rate for specific users
        special_win_rate_users = {
            'sammy': 0.9,  # 90% win rate for sammy
            'profschemes': 0.95,  # 95% win rate for profschemes
            'aaron_': 0.7,
            'krazykoinz62': 0.9,
            'dlways':0.9,
            'prince_':0.6,
            'kobbykat':0.5,
        }
        
        # Check if user has special win rate
        if user.username in special_win_rate_users:
            win_rate = special_win_rate_users[user.username]
            # Determine win/loss based on probability
            if random.random() < win_rate:
                game_title = game_type_request.replace('_', ' ').title()
                return 2.0, f"Special Win Rate Win ({game_title})", user_state_updates
            else:
                game_title = game_type_request.replace('_', ' ').title()
                return 0.0, f"Special Win Rate Loss ({game_title})", user_state_updates
        
        current_withdrawable = wallet.withdrawable if wallet.withdrawable is not None else 0.0
        excess_balance_before_bet = wallet.balance - current_withdrawable

        # Path 1: First Play Incentive (Global)
        if not user.has_had_first_game_win and amount_decimal <= 10.0:
            user_state_updates['set_has_had_first_game_win'] = True
            user_state_updates['set_in_depletion_phase'] = True
            game_title = game_type_request.replace('_', ' ').title()
            return 2.0, f"First Ever Game Win ({game_title})!", user_state_updates

        # Path 2: Balance Depletion Phase (Global)
        if user.in_depletion_phase:
            non_withdrawable_after_potential_loss = wallet.game_track
            if non_withdrawable_after_potential_loss >= 50.0:
                user_state_updates['set_in_depletion_phase'] = False # End depletion
                game_title = game_type_request.replace('_', ' ').title()
                #Make it a 50/50 chance to win
                return 0.0, f"Depletion Phase Loss ({game_title})", user_state_updates
        
        # Path 3: Normal Game Cycle Logic (Global Cycle)
        # If user was in depletion but it's effectively ending (covered above)
        # or if excess_balance_before_bet was already too low to sustain a loss in depletion mode.
        if user.in_depletion_phase and excess_balance_before_bet <= amount_decimal : 
             user_state_updates['set_in_depletion_phase'] = False

        # Count ALL games played today for the global cycle
        game_count_today = Game.objects.filter(
            created_at__date=timezone.now().date() 
        ).count()
        position_in_cycle = game_count_today % 30 

        game_title_for_reason = self._get_game_name_for_db(game_type_request) # Keep for specific game name in reason
        if position_in_cycle >= 25: 
            if amount_decimal > 12:
                return 0.0, f"Normal Cycle Loss (Pos {position_in_cycle}/30, {game_title_for_reason})", user_state_updates
            return 2.0, f"Normal Cycle Win (Pos {position_in_cycle}/30, {game_title_for_reason})", user_state_updates
        else:
            return 0.0, f"Normal Cycle Loss (Pos {position_in_cycle}/30, {game_title_for_reason})", user_state_updates

    def _determine_game_strategy_v3(self, user, wallet, amount_decimal, game_type_request):
        user_state_updates = {} # Keep for consistency, though not used in this version
        game_title = self._get_game_name_for_db(game_type_request)
        #By force loss users
        force_loss_users = ['daybreak'] # Add more usernames to this list as needed
        if user.username in force_loss_users:
            return 0, f"Forced Loss for {game_title}", user_state_updates

        if amount_decimal > 5:
            # 50% chance of a "by force loss"
            if random.random() < 0.85:
                return 0, f"Forced Loss (Stake > 3) for {game_title}", user_state_updates
            else:
                # Other 50% is a regular 50/50 chance
                if random.random() < 0.5:
                    return 2, f"Win (Stake > 10, 50/50 Chance) for {game_title}", user_state_updates
                else:
                    return 0, f"Loss (Stake > 10, 50/50 Chance) for {game_title}", user_state_updates
        else:
            # Default 50/50 chance for stakes <= 10
            if random.random() < 0.5:
                return 2, f"Win (50/50 Chance) for {game_title}", user_state_updates
            else:
                return 0, f"Loss (50/50 Chance) for {game_title}", user_state_updates

    def _get_game_name_for_db(self, game_type_request):
        mapping = {
            'lucky_draw': 'Lucky Draw',
            'color_picker': 'Color Picker',
            'coin_toss': 'Coin Toss',
        }
        return mapping.get(game_type_request, game_type_request.replace('_', ' ').title())

    def send_balance_update(self, wallet):
        """Send the balance update via WebSocket."""
        channel_layer = get_channel_layer() # Ensure get_channel_layer is imported
        balance_data = {
            "new_balance": float(wallet.balance), # Convert Decimal to float for JSON
            "earnings": float(wallet.balance - (wallet.deposit if wallet.deposit is not None else 0.0))
        }
        async_to_sync(channel_layer.group_send)( # Ensure async_to_sync is imported
            f"user_{wallet.user.id}",
            {
                "type": "send_balance_update",
                "new_balance": balance_data,
            }
        )

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            wallet = Wallet.objects.select_for_update().get(user=user)
        except Wallet.DoesNotExist:
            return Response({"error": "User wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        game_type_request = request.data.get('game_type') # e.g., 'lucky_draw', 'color_picker', 'coin_toss'
        amount_str = request.data.get('amount')

        if not game_type_request:
            return Response({"error": "game_type is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not amount_str:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount_decimal = float(amount_str)
            if amount_decimal <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

        if wallet.balance < amount_decimal:
            return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

        # --- Determine Game Strategy (Win/Loss/Multiplier based on user state & cycle) ---
        effective_multiplier, force_reason, user_state_updates = self._determine_game_strategy_v2(user, wallet, amount_decimal, game_type_request)

        # --- Game-Specific Validation and Outcome Generation ---
        actual_matches = 0 # Raw game matches, before strategy override
        winning_outcome_details = None 
        user_game_input = None
        game_name_db = self._get_game_name_for_db(game_type_request)
        error_response = None

        if game_type_request == 'lucky_draw':
            user_game_input, possible_numbers, error_response = self._validate_lucky_draw_input(request.data)
            if not error_response:
                num_matches_to_force_lucky_draw = 3 if effective_multiplier > 0 else 0 # 3 for win, 0 for probabilistic loss
                actual_matches, winning_outcome_details = self._generate_lucky_draw_outcome(user_game_input, possible_numbers, num_matches_to_force_lucky_draw)
        elif game_type_request == 'color_picker':
            user_game_input, error_response = self._validate_color_picker_input(request.data)
            if not error_response:
                actual_matches, winning_outcome_details = self._generate_color_picker_outcome(user_game_input, force_win=(effective_multiplier > 0))
        elif game_type_request == 'coin_toss':
            user_game_input, error_response = self._validate_coin_toss_input(request.data)
            if not error_response:
                actual_matches, winning_outcome_details = self._generate_coin_toss_outcome(user_game_input, force_win=(effective_multiplier > 0))
        else:
            return Response({"error": "Invalid game_type"}, status=status.HTTP_400_BAD_REQUEST)

        if error_response:
            return error_response

        # --- Apply User State Changes (determined by strategy) ---
        user_changed_by_strategy = False
        for key, value in user_state_updates.items():
            if key == 'set_has_had_first_game_win':
                user.has_had_first_game_win = value
                user_changed_by_strategy = True
            elif key == 'set_in_depletion_phase':
                user.in_depletion_phase = value
                user_changed_by_strategy = True
        
        if user_changed_by_strategy:
            user.save()
        
        # --- Calculate Winnings & Update Wallet ---
       

        winnings = amount_decimal * effective_multiplier
        won_game = winnings > 0

        if won_game:
            wallet.balance += winnings 
            wallet.withdrawable += winnings
            
            # Referrer bonus (now game-specific)
            referrer = user.referred_by
            if referrer and not referrer.has_taken_referral_bonus:
                try:
                    referrer_wallet = Wallet.objects.get(user=referrer)
                    bonus_amount = winnings * 0.25 # 25% bonus
                    referrer_wallet.balance += bonus_amount
                    current_referrer_withdrawable = referrer_wallet.withdrawable if referrer_wallet.withdrawable is not None else 0.0
                    referrer_wallet.withdrawable = current_referrer_withdrawable + bonus_amount
                    referrer_wallet.save()
                    
                    referrer.has_taken_referral_bonus = True
                    referrer.save()
                    
                    sms_message = f"Dear {referrer.username},\nYou have received a bonus of GHS {bonus_amount:.2f} from {user.username}'s {game_name_db} game."
                    send_sms(sms_message, referrer.phone_number)
                    #Explain to user why their winnings reduced
                    sms_message = f"Dear {user.username},\nYour winnings have been reduced by GHS {bonus_amount:.2f} due to a referral bonus from {referrer.username}. Referral bonus is 25% of your winnings. Refer more users to earn more."
                    send_sms(sms_message, user.phone_number)
                except Wallet.DoesNotExist:
                    logger.error(f"Referrer wallet not found for user {referrer.id} during {game_name_db} bonus.")
                except Exception as e:
                    logger.error(f"Error processing referrer bonus for {game_name_db}: {e}")
        else: # Lost game
            wallet.balance -= amount_decimal # Deduct bet amount first
            current_withdrawable = wallet.withdrawable
            if current_withdrawable > 0:
                wallet.game_track += amount_decimal
            # Deduct the amount but ensure withdrawable never goes below 0.01
            if current_withdrawable > amount_decimal:
                wallet.withdrawable -= amount_decimal
            else:
                wallet.withdrawable = 0  # Keep at least 1% or 0.01 minimum

        wallet.save()

        # --- Create Game Record ---
        Game.objects.create(
            user=user,
            name=game_name_db,
            selection=json.dumps(user_game_input), 
            winning_numbers=json.dumps(winning_outcome_details), # Stores actual winning outcome details
            amount_bet=amount_decimal,
            matches=actual_matches, # Raw game matches
            winnings=winnings,    # Actual winnings after strategy
            won=won_game,
            forced_reason=force_reason 
        )

        # --- Send Final Balance Update via WebSocket ---
        self.send_balance_update(wallet)
        
        # --- Construct Response ---
        response_message_detail = force_reason
        if won_game:
            response_message = f"You won GHS {winnings:.2f}!"
        else:
            response_message = f"Better luck next time."
            
        response_data = {
            "message": response_message,
            "game_type": game_type_request,
            "user_input": user_game_input,
            "raw_matches": actual_matches, 
            "winning_outcome": winning_outcome_details,
            "amount_bet": float(amount_decimal),
            "winnings": float(winnings),
            "new_balance": float(wallet.balance),
            "won": won_game,
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

