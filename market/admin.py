from django.contrib import admin
from .models import *
# Register your models here.
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['amount', 'title', 'interest', 'status', 'created_at',]
    list_filter = ['status', 'created_at']
    search_fields = ['user', 'title']
admin.site.register(Investment, InvestmentAdmin)

class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'deposit', 'balance']
    search_fields = ['user']
admin.site.register(Wallet, WalletAdmin)

class OperatorAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']
admin.site.register(Operator, OperatorAdmin)

class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'type', 'created_at']
    list_filter = ['status', 'type', 'created_at']
    search_fields = ['user']
admin.site.register(Transaction, TransactionAdmin)

class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'comment', 'name', 'created_at']
    search_fields = ['user', 'name']
admin.site.register(Comment, CommentAdmin)

class Requested_WithdrawAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'phone_number', 'settled', 'created_at']
    search_fields = ['user', 'phone_number']
    list_filter = ['settled', 'created_at']
admin.site.register(Requested_Withdraw, Requested_WithdrawAdmin)