from rest_framework import serializers
from .models import Investment, Transaction, Wallet, Operator

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

class OperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Operator
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = '__all__'