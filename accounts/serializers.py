from .exceptions import ExternalAPIError
from rest_framework import serializers
from .models import *
import requests
import os
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from market.models import Transaction, Investment
import random
import logging

logger = logging.getLogger(__name__)

class UserRegistrationSerializer(serializers.ModelSerializer):
    referal_code = serializers.CharField(required=False, allow_blank=True)
    vendor_code = serializers.CharField(required=False, allow_blank=True)
    class Meta:
        model = Customer
        fields = ('username', 'phone_number', 'referal_code','email','vendor_code')
    
    def validate_username(self, value):
        logger.info(f"Original username: {value}")
        # First remove all whitespace
        value = ''.join(value.split())
        logger.info(f"After whitespace removal: {value}")
        # Then remove any remaining special characters
        cleaned_username = ''.join(char.lower() for char in value if char.isalnum() or char == '_')
        logger.info(f"Final cleaned username: {cleaned_username}")
        
        if not cleaned_username:
            raise serializers.ValidationError("Username must contain at least one alphanumeric character")
            
        # Check for username conflicts and add random numbers if needed
        original_username = cleaned_username
        counter = 0
        while Customer.objects.filter(username=cleaned_username).exists():
            random_number = random.randint(1000, 9999)
            cleaned_username = f"{original_username}{random_number}"
            counter += 1
            if counter > 10:  # Prevent infinite loops
                raise serializers.ValidationError("Unable to generate unique username. Please try a different name.")
                
        logger.info(f"Final unique username: {cleaned_username}")
        return cleaned_username

    def validate(self, data):
        if 'username' in data:
            data['username'] = self.validate_username(data['username'])
        return data

    def create(self, validated_data):
        #Check if user already exists and return that user, if not create a new user
        try:
            user = Customer.objects.get(phone_number=validated_data.get('phone_number'))
            return user
        except Customer.DoesNotExist:
            # Double-check username sanitization before creation
            validated_data['username'] = self.validate_username(validated_data.get('username', ''))

            password = "defaultpassword"
            # The username will already have been sanitized by validate_username
            referral_code = validated_data.pop('referal_code', None) # Extract referral code
            vendor_code = validated_data.pop('vendor_code', None) # Extract vendor code
            if vendor_code:
                vendor = Vendor.objects.get(code=vendor_code)
                validated_data['vendor'] = vendor
            user = Customer.objects.create(**validated_data, password=password)
            user.set_password(user.password)
            user.is_active = False
            user.platform = 'TM'
            user.paid = False
            user.save()

            # Handle referral code if present
            if referral_code:
                try:
                    referal_user = Customer.objects.get(username=referral_code)
                    if referal_user.paid:
                        user.referred_by = referal_user
                        user.save()
                    else:
                        user.referred_by = None
                        user.save()

                except Customer.DoesNotExist:
                    pass # Referral user not found, proceed without referral

            return user # Return the created user object

class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

class UserResendOtpSerializer(serializers.Serializer):
    user_id = serializers.CharField()

class UserOtpVerificationSerializer(serializers.Serializer):
    code = serializers.CharField()
    user_id = serializers.CharField()

class InvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investment
        fields = '__all__'

class ReferredUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ('id', 'status','reffered','created_at')

class GCRegisterationSerializer(serializers.ModelSerializer):
    referal_code = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = Customer
        fields = ('username', 'email', 'referal_code', 'password')
    
    def validate_username(self, value):
        logger.info(f"Original username: {value}")
        # First remove all whitespace
        value = ''.join(value.split())
        logger.info(f"After whitespace removal: {value}")
        # Then remove any remaining special characters
        cleaned_username = ''.join(char.lower() for char in value if char.isalnum() or char == '_')
        logger.info(f"Final cleaned username: {cleaned_username}")
        
        if not cleaned_username:
            raise serializers.ValidationError("Username must contain at least one alphanumeric character")
            
        # Check for username conflicts and add random numbers if needed
        original_username = cleaned_username
        counter = 0
        while Customer.objects.filter(username=cleaned_username).exists():
            random_number = random.randint(1000, 9999)
            cleaned_username = f"{original_username}{random_number}"
            counter += 1
            if counter > 10:  # Prevent infinite loops
                raise serializers.ValidationError("Unable to generate unique username. Please try a different name.")
                
        logger.info(f"Final unique username: {cleaned_username}")
        return cleaned_username

    def validate(self, data):
        if 'username' in data:
            data['username'] = self.validate_username(data['username'])
        return data

    def create(self, validated_data):
        # Double-check username sanitization before creation
        validated_data['username'] = self.validate_username(validated_data.get('username', ''))
        try:
            Customer.objects.get(email=validated_data.get('email'))
            raise serializers.ValidationError('User with this email already exists')
        except Customer.DoesNotExist:
            pass
        # Generate unique phone number
        while True:
            phone_number = str(random.randint(100000000, 999999999))
            if not Customer.objects.filter(phone_number=phone_number).exists():
                break
        validated_data['phone_number'] = phone_number
        # The username will already have been sanitized by validate_username
        user = Customer.objects.create(**validated_data)
        user.set_password(user.password)
        user.is_active = True
        user.platform = 'GC'
        user.save()

        # Handle referral code if present
        if validated_data.get('referal_code'):
            try:
                referal_user = Customer.objects.get(username=validated_data.get('referal_code'))
                user.referred_by = referal_user
                user.save()

                # Create a transaction for the referring user
                transaction = Transaction.objects.create(
                    user=referal_user, 
                    amount=25.00, 
                    status='pending', 
                    type='referal', 
                    reffered=user.username, 
                    image='https://darkpass.s3.us-east-005.backblazeb2.com/investment/male.png'
                )

                # Send transaction to WebSocket
                channel_layer = get_channel_layer()
                transaction_data = {
                    'id': transaction.id,
                    'user': transaction.user.id,
                    'amount': transaction.amount,
                    'status': transaction.status,
                    'type': transaction.type,
                    'reffered': transaction.reffered,
                    'created_at': transaction.created_at.isoformat(),
                }
                async_to_sync(channel_layer.group_send)(
                    f"user_{referal_user.id}",
                    {
                        'type': 'send_user_transaction',
                        'transaction': transaction_data,
                    }
                )

            except Customer.DoesNotExist:
                pass

        return user

class GCLoginSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField()