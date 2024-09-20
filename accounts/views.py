from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from .serializers import UserLoginSerializer, UserRegistrationSerializer, UserOtpVerificationSerializer, UserResendOtpSerializer
from .models import Customer
import os
from rest_framework.authentication import TokenAuthentication,SessionAuthentication
from rest_framework import generics, status
from django.contrib.auth import logout,login
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from .exceptions import ExternalAPIError
import requests
from market.models import Wallet

class UserRegistrationView(generics.CreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]  # Allow anyone to register

    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_201_CREATED:
                user = Customer.objects.get(username=request.data['username'])
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
            user.is_active = True
            user.save()
            token, _ = Token.objects.get_or_create(user=user)
            walet, _ = Wallet.objects.get_or_create(user=user)
            data = {
                "message": "User verified",
                "user_id": user_id,
                "username": user.username,
                "phone_number": user.phone_number,
                "verified": user.verified,
                "token": token.key,
                "balance": walet.balance
            }
            return Response(data, status=200)
        elif response.status_code == 200 and response.json().get("message") == "Code has expired":
            return Response({"message": "Code has expired"}, status=400)
        elif response.status_code == 200 and response.json().get("message") == "Invalid code":
            return Response({"message": "Code incorrect"}, status=400)
        else:
            print(f"Error: {response.status_code} and {response.json()}")
            return Response({"message": "Code incorrect"}, status=400)

class UserOtpVerificationLogin(generics.CreateAPIView):
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
            token, _ = Token.objects.get_or_create(user=Customer.objects.get(pk=user_id))
            user = Customer.objects.get(pk=user_id)
            wallet, _ = Wallet.objects.get_or_create(user=user)
            data = {
                "message": "User logged in successfully",
                "token": token.key,
                "user_id": user_id,
                "username": user.username,
                "phone_number": user.phone_number,
                "balance": wallet.balance,
                "verified": user.verified
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
            if user.is_active == False:
                raise AuthenticationFailed(detail="User is not verified")
        except Customer.DoesNotExist:
            raise AuthenticationFailed(detail="Invalid Phone Number")

        message = f"Hello {user.username},"
        data = {
        'expiry': 5,
        'length': 6,
        'medium': 'sms',
        'message': message+' This is your login OTP code:\n%otp_code%\nPlease do not share this code with anyone.',
        'number': user.phone_number,
        'sender_id': 'TradeMatrix',
        'type': 'numeric',
        }

        headers = {
        'api-key': os.environ.get('ARK_API_KEY'),
        }

        url = 'https://sms.arkesel.com/api/otp/generate'

        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code != 200:
                user.delete()
                raise ExternalAPIError(response.status_code, response.json())
            else:
                data = {
                    "message": "OTP sent",
                    "user_id": user.id
                }
                return Response(data, status=status.HTTP_200_OK)
        except requests.RequestException as e:
            raise ExternalAPIError(500, str(e))

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
        users = Customer.objects.all().count()
        user_percentage = (users/200000)
        data = {
            "total_users": users,
            "user_percentage": user_percentage
        }
        return Response(data, status=status.HTTP_200_OK)
    
class UserCreateReferalLink(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication,SessionAuthentication]
    def get(self, request, *args, **kwargs):
        user = request.user
        referal_link = f"http://localhost:8000/accounts/register/?referral={user.username}"
        data = {
            "referal_link": referal_link,
            "message": "Referal link created successfully"
        }
        return Response(data, status=status.HTTP_200_OK)