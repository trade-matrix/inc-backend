from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .serializers import UserLoginSerializer, UserRegistrationSerializer, UserOtpVerificationSerializer, UserResendOtpSerializer, InvestmentSerializer, ReferredUserSerializer, GCRegisterationSerializer, GCLoginSerializer
from .models import Customer
import os
from rest_framework.authentication import TokenAuthentication,SessionAuthentication
from rest_framework import generics, status
from django.contrib.auth import logout,login
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from .exceptions import ExternalAPIError
import requests
from market.models import Wallet, Investment, Transaction
from .utils import send_otp
from market.utils import send_promo_sms, update_user

class UserRegistrationView(generics.CreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]  # Allow anyone to register

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_201_CREATED:
                user = Customer.objects.get(username=request.data['username'])
                send_promo_sms(user)
                user_id = user.id
                response.data['user_id'] = user_id
            return response
        except ExternalAPIError as e:
            # Here you can customize the response as per your frontend requirements
            return Response({"error": str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
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
        platform = serializer.validated_data['platform']
        try:
            user = Customer.objects.get(phone_number=phone_number)
        except Customer.DoesNotExist:
            if platform == 'Gc':
                user = Customer.objects.create_user(username="investor", phone_number=phone_number)
                send_otp(user.phone_number, user.username)
                data = {
                    "message": "OTP sent",
                    "user_id": user.id
                }
                return Response(data, status=status.HTTP_200_OK)
            raise AuthenticationFailed(detail="Invalid Phone Number")

        send_otp(user.phone_number, user.username)
        data = {
            "message": "OTP sent",
            "user_id": user.id
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
        message = f"Hello {user.username}, Welcome to Trade-Matrix."
        data = {
        'expiry': 5,
        'length': 6,
        'medium': 'sms',
        'message': message+' This is your verification code:\n%otp_code%\nPlease do not share this code with anyone.',
        'number': phone,
        'sender_id': 'TradeMatrix',
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
        if user.email is None or user.email.strip() == '':
            referal_link = f"https://trade-matrix.net/auth/sign-up/?referral={user.username}"
        else:
            referal_link = f"https://goldencash.vercel.app/auth/sign-up/?referral={user.username}"
            
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
        eligibility = walet.eligible
        data = {
            "user_id": user.id,
            "username": user.username,
            "balance": walet.balance,
            "earnings": earnings,
            "deposit": walet.deposit,
            "investments": number_of_investments,
            "refferals": number_of_refferals,
            "eligibility": eligibility
        }
        return Response(data, status=status.HTTP_200_OK)

class DeleteAccount(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    def delete(self, request, *args, **kwargs):
        user = request.user
        user.delete()
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
                user = Customer.objects.get(username=request.data['username'])
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
    