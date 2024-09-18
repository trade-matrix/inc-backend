from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework import permissions
from .models import Investment
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Wallet, Operator, Transaction
from .serializers import InvestmentSerializer, RequesttoInvest, ConfirmPayment, Withdraw, CheckMomoSerializer, TransactionSerializer, WalletSerializer
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.response import Response
from accounts.models import Customer
from .utils import payment, status_check, send_money, send_sms, check_momo
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
import json
from django.views.decorators.csrf import csrf_exempt
import datetime

class InvestmentListView(generics.ListAPIView):
    queryset = Investment.objects.all()
    serializer_class = InvestmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
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
        if not request.user.verified:
            user = request.user
            pk = request.data.get('id')
            investment = Investment.objects.get(pk=pk)
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
        return Response({"error": "User has Already Invested"}, status=status.HTTP_400_BAD_REQUEST)

class VerifyPayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = ConfirmPayment
    def post(self, request, *args, **kwargs):
        reference = request.data.get('reference')
        status_chec = status_check(reference)
        if status_chec['data']['status'] == 'success':
            user = Customer.objects.get(reference=reference)
            user.verified = True
            user.save()
            investment = Investment.objects.get(title=status_chec['data']['metadata']['investment'])
            wallet,_ = Wallet.objects.get_or_create(user=user)
            
            # Update the wallet balance
            wallet.balance += float(status_chec['data']['amount_paid'])*investment.interest
            wallet.deposit = float(status_chec['data']['amount_paid'])  # For example, adding a deposit
            wallet.save()
            # Create a transaction record
            transaction = Transaction.objects.create(user=user, amount=float(status_chec['data']['amount_paid']), status='completed', type='deposit')
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
                referrer_wallet.balance += float(status_chec['data']['amount_paid'])*investment.interest*0.15
                referrer_wallet.save()
                transaction = Transaction.objects.create(user=user.referred_by, amount=float(status_chec['data']['amount_paid'])*investment.interest*0.15, status='completed', type='referal')
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.referred_by.id}",
                    {
                        "type": "send_balance_update",
                        "new_balance": referrer_wallet.balance,
                    }
                )
                send_sms(f"You’ll receive 85% of your returns since you were referred by {user.referred_by.username}. Refer more people to boost your earnings!", user.phone_number)
                send_sms(f"Congratulations! You just earned 15% of {user.username}'s investment.\nYour total balance is now GHS {referrer_wallet.balance}", user.referred_by.phone_number)
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
        operator = request.data.get('operator')
        phone_number = request.data.get('phone_number')
        if wallet.balance >= float(amount):
            send_money(amount, phone_number, operator, user.id)
            if not send_money:
                return Response({"error": "Withdrawal failed"}, status=status.HTTP_400_BAD_REQUEST)
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
                send_sms("Your withdrawal was successful", phone_number)
            elif payload.get('event') == 'transfer.failed':
                phone_number = payload['metadata']['phone_number']
                user_id = payload['metadata']['user_id']
                wallet = Wallet.objects.get(user=user_id)
                wallet.balance += float(payload['data']['amount'])
                wallet.save()

                # Send balance update to the WebSocket consumer
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}",  # Unique group for each user
                    {
                        "type": "send_balance_update",
                        "new_balance": wallet.balance,
                    }
                )
                send_sms("Your withdrawal failed. Your balance has been reverted.", phone_number)   
            elif payload.get('event') == 'charge.success':
                reference = payload['data']['reference']
                user = Customer.objects.get(reference=reference)
                wallet,_ = Wallet.objects.get_or_create(user=user)
                
                # Update the wallet balance
                wallet.active = True
                wallet.eligible = True
                wallet.date_made_eligible = datetime.datetime.now()
                wallet.save()

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

class UserWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    serializer_class = WalletSerializer
    def get(self, request, *args, **kwargs):
        wallet = Wallet.objects.get(user=request.user)
        data = {
            "balance": wallet.balance,
            "deposit": wallet.deposit
        }
        return Response(data, status=status.HTTP_200_OK)