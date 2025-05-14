from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .serializers import UserLoginSerializer, UserRegistrationSerializer, UserOtpVerificationSerializer, UserResendOtpSerializer, InvestmentSerializer, ReferredUserSerializer, GCRegisterationSerializer, GCLoginSerializer
from .models import Customer, Ref, Vendor
import random
import string
import os
from rest_framework.authentication import TokenAuthentication,SessionAuthentication
from rest_framework import generics, status
from django.db.models import Sum
from django.contrib.auth import logout,login
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from .exceptions import ExternalAPIError
import requests
from market.models import Wallet, Investment, Transaction, PoolParticipant, Game
from .utils import send_otp
from market.utils import send_promo_sms, update_user, paystack_payment, paystack_balance_check
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework import serializers

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to register

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save() # Serializer now returns the user object
            if user.paid:
                # --- OTP Sending Logic Moved Here ---
                message = f"Hello {user.username}, Welcome to TM-Hub."
                otp_data = {
                    'expiry': 5,
                    'length': 6,
                    'medium': 'sms',
                    'message': message + ' This is your verification code:\n%otp_code%\nPlease do not share this code with anyone.',
                    'number': user.phone_number,
                    'sender_id': 'TMHub',
                    'type': 'numeric',
                }

                headers = {
                    'api-key': os.environ.get('ARK_API_KEY'),
                }

                url = 'https://sms.arkesel.com/api/otp/generate'

                try:
                    response = requests.post(url, json=otp_data, headers=headers)
                    response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                    if response.status_code != 200:
                        # If OTP fails, delete the created user to avoid dangling accounts
                        user.delete()
                        raise ExternalAPIError(response.status_code, response.json())
                except requests.RequestException as e:
                    # Network error or other request issue
                    user.delete()
                    raise ExternalAPIError(500, str(e))
                except Exception as e:
                    # Catch any other unexpected errors during OTP sending
                    user.delete()
                    # You might want to log this error differently
                    raise ExternalAPIError(500, f"An unexpected error occurred during OTP sending: {str(e)}")
                # --- End of OTP Sending Logic ---
            else:
                payment_link = paystack_payment(50, user.email, user.phone_number, 'registration')
                user.reference = payment_link.get("data").get("reference")
                user.save()
                #Create a ref
                Ref.objects.create(user=user, reference=payment_link.get("data").get("reference"))
            # Prepare successful response
            response_data = {
                "message": "User registered successfully. OTP sent.",
                "user_id": user.id,
                "payment_link": payment_link.get("data").get("authorization_url")
            }
            return Response(response_data, status=status.HTTP_201_CREATED)

        except serializers.ValidationError as e:
             # Handle serializer validation errors
             return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
        except ExternalAPIError as e:
            # Handle errors raised during OTP sending or potentially referral creation
            return Response({"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            # Catch any other unexpected errors during user creation/saving
            # Log this error for debugging
            print(f"Unexpected registration error: {str(e)}") 
            return Response({"error": "An unexpected error occurred during registration."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserOtpVerification(generics.CreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = UserOtpVerificationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        code = serializer.validated_data.get('code')
        user_id = serializer.validated_data.get('user_id')
        phone = Customer.objects.get(pk=user_id).phone_number
        data = {
            "code": code,
            "number": phone,
        }

        headers = {
        'api-key': os.environ.get('ARK_API_KEY'),
        }

        url = 'https://sms.arkesel.com/api/otp/verify'

        response = requests.post(url, json=data, headers=headers)
        print(response.json())
        if response.status_code == 200 and response.json().get("message") == "Successful":
            print(response.json())
            user = Customer.objects.get(pk=user_id)
            if not user.is_active:
                user.is_active = True
                user.save()
            token, _ = Token.objects.get_or_create(user=user)
            walet, _ = Wallet.objects.get_or_create(user=user)
            earnings = walet.amount_from_games

            acceleration_end_time = datetime(2025, 3, 7, 18, 0).isoformat()
            is_user_in_pool = PoolParticipant.objects.filter(user=user).exists()
            data = {
                "message": "User verified",
                "user_id": user_id,
                "username": user.username,
                "phone_number": user.phone_number,
                "verified": user.verified,
                "token": token.key,
                "balance": walet.balance,
                "earnings": earnings,
                "deposit": walet.deposit,
                "end_time": acceleration_end_time,
                "accelerator": walet.valid_for_pool,
                "is_user_in_pool": is_user_in_pool
            }
            login(request, user)
            return Response(data, status=200)
        elif response.status_code == 200 and response.json().get("message") == "Code has expired":
            return Response({"message": "Code has expired"}, status=400)
        elif response.status_code == 200 and response.json().get("message") == "Invalid code":
            return Response({"message": "Code incorrect"}, status=400)
        else:
            print(f"Error: {response.status_code} and {response.json()}")
            return Response({"message": "Code incorrect"}, status=400)

class UserLoginView(generics.CreateAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        
        try:
            user = Customer.objects.get(phone_number=phone_number)
        except Customer.DoesNotExist:
            raise AuthenticationFailed(detail="Invalid Phone Number")

        if user.paid:
            send_otp(user.phone_number, user.username)
            data = {
                "message": "OTP sent",
                "user_id": user.id,
                "user_paid": user.paid
            }
        else:
            payment_link = paystack_payment(50, user.email, user.phone_number, 'registration')
            user.reference = payment_link.get("data").get("reference")
            user.save()
            #Create a ref
            Ref.objects.create(user=user, reference=payment_link.get("data").get("reference"))
            data = {
                "user_id": user.id,
                "user_paid": user.paid,
                "payment_link": payment_link.get("data").get("authorization_url")
            }
        return Response(data, status=status.HTTP_200_OK)

class UserLogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    def get(self, request, *args, **kwargs):
        logout(request)
        return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
    
class UserResendOTP(generics.CreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = UserResendOtpSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone = Customer.objects.get(pk=serializer.validated_data.get('user_id')).phone_number
        user_id = serializer.validated_data.get('user_id')
        user = Customer.objects.get(pk=user_id)
        if not user.paid:
            return Response({"message": "Payment required"}, status=400)
        message = f"Hello {user.username}, Welcome to Trade-Matrix."
        data = {
        'expiry': 5,
        'length': 6,
        'medium': 'sms',
        'message': message+' This is your verification code:\n%otp_code%\nPlease do not share this code with anyone.',
        'number': phone,
        'sender_id': 'TMHub',
        'type': 'numeric',
        }

        headers = {
        'api-key': os.environ.get('ARK_API_KEY'),
        }

        url = 'https://sms.arkesel.com/api/otp/generate'

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200 and response.json().get("code") == '1000':
            print(response.json())
            return Response({"message": "OTP sent"}, status=200)
        else:
            print(f"Error: {response.status_code} and {response.json()}")
            return Response({"message": "OTP not sent"}, status=400)

class TotalNumberOfUsers(generics.GenericAPIView):
    permission_classes = [AllowAny]
    def get(self, request, *args, **kwargs):
        users = Customer.objects.filter(verified=True).count()
        user_percentage = (users/200000)*100
        if user_percentage < 10:
            user_percentage = 13
        elif user_percentage > 100:
            user_percentage = 100
        data = {
            "total_users": users,
            "user_percentage": round(user_percentage)
        }
        return Response(data, status=status.HTTP_200_OK)
    
class UserCreateReferalLink(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    
    def get(self, request, *args, **kwargs):
        if not request.user.verified:
            return Response(
                {"message": "Deposit required before you can refer."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user = request.user
        # Check for both null and empty email
        referal_link = f"https://tm-hub.com/signup/?referral={user.username}"
        #Check if user is associated with a vendor model
        try:
            vendor = Vendor.objects.get(user=user)
            referal_link = f"https://tm-hub.com/signup/?referral={user.username}&vendor_code={vendor.code}"
        except Vendor.DoesNotExist:
            pass
            
        data = {
            "referal_link": referal_link,
            "message": "Referal link created successfully"
        }
        return Response(data, status=status.HTTP_200_OK)

class GetRefferedUsers(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    serializer_class = ReferredUserSerializer
    def get(self, request, *args, **kwargs):
        user = request.user
        referred_transactions = Transaction.objects.filter(user=user, type='referal')
        serializer = ReferredUserSerializer(referred_transactions, many=True)
        data = {
            "data": serializer.data
        }
        return Response(data, status=status.HTTP_200_OK)

class GetUserInvestments(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    serializer_class = InvestmentSerializer
    def get(self, request, *args, **kwargs):
        user = request.user
        investments = Investment.objects.filter(user=user)
        serializer = InvestmentSerializer(investments, many=True)
        data = {
            "data": serializer.data
        }
        return Response(data, status=status.HTTP_200_OK)

class UserDetails(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    
    def get(self, request, *args, **kwargs):
        user = request.user
        walet, _ = Wallet.objects.get_or_create(user=user)
        earnings = walet.amount_from_games
        number_of_investments = Investment.objects.filter(user=user).count()
        number_of_refferals = Transaction.objects.filter(user=user, type='referal',status='completed').count()
        referal_earnings = Transaction.objects.filter(user=user, type='referal',status='completed').aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        eligibility = walet.eligible
        is_user_in_pool = PoolParticipant.objects.filter(user=user).exists()
        is_vendor = Vendor.objects.filter(user=user).exists()
        acceleration_end_time = datetime(2025, 3, 21, 18, 0).isoformat()  # Set to February 13th, 2025 at 18:00 GMT
        #check if user is associated with a vendor model
        try:
            vendor = Vendor.objects.get(user=user)
            #check number of users associated with vendor
            number_of_users = Customer.objects.filter(vendor=vendor).count()
        except Vendor.DoesNotExist:
            number_of_users = 0
        data = {
            "user_id": user.id,
            "username": user.username,
            "balance": walet.balance,
            "earnings": earnings,
            "deposit": walet.deposit,
            "investments": number_of_investments,
            "refferals": number_of_refferals,
            'referal_earnings': referal_earnings,
            "vendor_sales": number_of_users,
            "vendor_earnings": number_of_users * 20,
            "eligibility": eligibility,
            "accelerator": walet.valid_for_pool,
            "phone_number": user.phone_number,
            "end_time": acceleration_end_time,
            "is_user_in_pool": is_user_in_pool,
            "is_admin": user.is_superuser,
            "is_vendor": is_vendor
        }
        return Response(data, status=status.HTTP_200_OK)

class DeleteAccount(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    def delete(self, request, *args, **kwargs):
        user = request.user
        user.is_active = False
        user.paid = False
        user.save()
        #Delete user token
        Token.objects.filter(user=user).delete()
        return Response({"message": "Account deleted successfully"}, status=status.HTTP_200_OK)

class NumberofReferralsRequired(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def get(self, request, *args, **kwargs):
        try:
            wallet = Wallet.objects.get(user=request.user)
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND)

        earnings = wallet.balance - wallet.deposit
        num_referrals = Transaction.objects.filter(user=request.user, type='referal', status='completed').count()

        # Calculate required referrals based on earnings
        required_referrals = round(earnings / 10,2)
        if required_referrals < 10:
            required_referrals = 10

        # Avoid division by zero when calculating the percentage
        if required_referrals > 0:
            percentage = round((num_referrals / required_referrals) * 100)
        else:
            percentage = 100  # Default to 100% if no referrals are required

        # Cap the percentage at 100
        percentage = min(percentage, 100)

        data = {
            "required_referrals": required_referrals,
            "number_of_referrals": num_referrals,
            "percentage": percentage
        }
        if percentage == 100:
            data["eligiblility"] = False
        else:
            data["eligibility"] = False
        return Response(data, status=status.HTTP_200_OK)

class RegisteronGoldenCash(generics.CreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = GCRegisterationSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_201_CREATED:
                user = Customer.objects.get(email=request.data['email'])
                token, _ = Token.objects.get_or_create(user=user)
                walet, _ = Wallet.objects.get_or_create(user=user)
                earnings = walet.amount_from_games
                update_user(user.email, "Welcome","Welcome to Golden Cash",'new.html')
                data = {
                    "message": "User verified",
                    "user_id": user.id,
                    "username": user.username,
                    "phone_number": user.phone_number,
                    "verified": user.verified,
                    "token": token.key,
                    "balance": walet.balance,
                    "earnings": earnings,
                    "deposit": walet.deposit,
                }
                login(request, user)
                return Response(data, status=status.HTTP_201_CREATED)
            return response
        except Customer.DoesNotExist:
            return Response(
                {"error": "User creation failed"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except ExternalAPIError as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

class UserLoginGoldenCash(generics.CreateAPIView):
    serializer_class = GCLoginSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            user = Customer.objects.get(email=email)
        except Customer.DoesNotExist:
            raise AuthenticationFailed(detail="Invalid Email")
        
        if not user.check_password(password):
            raise AuthenticationFailed(detail="Invalid Password")
        
        if not user.is_active:
            raise AuthenticationFailed(detail="Account not activated")
        
        token, _ = Token.objects.get_or_create(user=user)
        walet, _ = Wallet.objects.get_or_create(user=user)
        earnings = walet.amount_from_games
        data = {
            "message": "User verified",
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "verified": user.verified,
            "token": token.key,
            "balance": walet.balance,
            "earnings": earnings,
            "deposit": walet.deposit,
        }
        login(request, user)

        return Response(data, status=200)

class AdminAnalytics(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
   
    def get(self, request, *args, **kwargs):
        # Define special users to exclude from analytics
        special_users = [
            'sammy',
            'profschemes',
            'aaron_',
            'krazykoinz62',
            'dlways',
            'elite',
            'Admin',
            'kobbykat',
            'prince_',
        ]
        
        # Exclude special users from queries
        regular_users = Customer.objects.exclude(username__in=special_users, paid=True)
        
        total_withdraws = Transaction.objects.filter(type='withdraw', user__in=regular_users).aggregate(total_amount=Sum('amount'))['total_amount'] or 0
        total_deposits = Wallet.objects.filter(user__in=regular_users).aggregate(total_amount=Sum('deposit'))['total_amount'] or 0
        
        data = {
            "total_users": regular_users.count(),
            "total_games_played": Game.objects.all().count(),
            "total_vendors": Vendor.objects.exclude(user__username__in=special_users).count(),
            "total_platform_revenue": float(total_deposits)- (float(total_withdraws)+ float(Wallet.objects.filter(user__in=regular_users).aggregate(total_amount=Sum('withdrawable'))['total_amount'] or 0)) or 0,
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdraws,
            "total_referrals": Transaction.objects.filter(type='referal').count(),
            "total_affiliate_users": regular_users.filter(affiliate=True).count(),
            "total_affiliate_earnings": Wallet.objects.filter(user__affiliate=True, user__in=regular_users).aggregate(total_amount=Sum('withdrawable'))['total_amount'] or 0,
            "total_non_affiliate_users": regular_users.filter(affiliate=False).count(),
            "total_non_affiliate_earnings": Wallet.objects.filter(user__affiliate=False, user__in=regular_users).aggregate(total_amount=Sum('withdrawable'))['total_amount'] or 0,
            #"paystack_balance": paystack_balance_check().get("data").get("balance")
        }
        return Response(data, status=status.HTTP_200_OK)

class BecomeVendor(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]

    def post(self, request, *args, **kwargs):
        #Check if user is already a vendor
        if Vendor.objects.filter(user=request.user).exists():
            return Response({"message": "User is already a vendor"}, status=status.HTTP_400_BAD_REQUEST)
        #Check balance
        if Wallet.objects.get(user=request.user).balance < 50:
            return Response({"message": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        #Create a five digit code starting with username initials of first three letters plus random strings
        code = user.username[:3].upper() + ''.join(random.choices(string.ascii_letters + string.digits, k=2))
        vendor = Vendor.objects.create(user=user, code=code)
        wallet = Wallet.objects.get(user=user)
        wallet.balance -= 50
        wallet.save()
        return Response({"message": "Vendor created successfully"}, status=status.HTTP_201_CREATED)
