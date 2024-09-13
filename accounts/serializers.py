from .exceptions import ExternalAPIError
from rest_framework import serializers
from .models import *
import requests
import os

class UserRegistrationSerializer(serializers.ModelSerializer):
    referal_code = serializers.CharField(required=False)
    class Meta:
        model = Customer
        fields = ('username', 'phone_number','referal_code')
    
    def create(self, validated_data):
        password = "defaultpassword"
        user = Customer.objects.create(**validated_data, password=password)
        user.set_password(user.password)
        user.is_active = False
        user.save()
        message = f"Hello {user.username}, Welcome to Trade-Matrix."
        data = {
        'expiry': 5,
        'length': 6,
        'medium': 'sms',
        'message': message+' This is your verification code:\n%otp_code%\nPlease do not share this code with anyone.',
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
                
        except requests.RequestException as e:
            user.delete()
            raise ExternalAPIError(500, str(e))
        if validated_data.get('referal_code'):
            try:
                referal_user = Customer.objects.get(username=validated_data.get('referal_code'))
                referal_user.referred_users.add(user)
                referal_user.save()
            except Customer.DoesNotExist:
                pass
        return user

class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()


class UserResendOtpSerializer(serializers.Serializer):
    user_id = serializers.CharField()


class UserOtpVerificationSerializer(serializers.Serializer):
    code = serializers.CharField()
    user_id = serializers.CharField()
