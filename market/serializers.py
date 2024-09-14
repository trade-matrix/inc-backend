from rest_framework import serializers
from .models import Investment

class InvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investment
        fields = '__all__'

class RequesttoInvest(serializers.Serializer):
    id = serializers.IntegerField()

class ConfirmPayment(serializers.Serializer):
    reference = serializers.CharField()

class Withdraw(serializers.Serializer):
    amount = serializers.IntegerField()
    phone_number = serializers.CharField()
    operator = serializers.CharField()

class CheckMomoSerializer(serializers.Serializer):
    operator = serializers.CharField()