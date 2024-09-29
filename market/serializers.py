from rest_framework import serializers
from .models import Investment, Transaction, Wallet, Operator, Comment
import datetime

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
    operator = serializers.CharField(required=False)

class CheckMomoSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
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

class PredictionSerializer(serializers.Serializer):
    amount = serializers.CharField(required=False)
    type = serializers.CharField(required=False)
    score = serializers.CharField(required=False)
    winnings = serializers.CharField(required=False)

class CommentSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False)
    user = serializers.StringRelatedField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True, required=False)
    class Meta:
        model = Comment
        fields = '__all__'
    
    def create(self, validated_data):
        if not validated_data.get('created_at'):
            validated_data['created_at'] = datetime.datetime.now()
        return Comment.objects.create(**validated_data)

class GameSerializer(serializers.Serializer):
    name = serializers.CharField()