from django.db import models
from accounts.models import Customer
# Create your models here.
class Investment(models.Model):
    user = models.ManyToManyField(Customer, related_name='investors', blank=True)
    amount = models.FloatField()
    title = models.CharField(max_length=255)
    interest = models.FloatField()
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=False)
    def __str__(self):
        return self.title
    
class Wallet(models.Model):
    user = models.OneToOneField(Customer, on_delete=models.CASCADE)
    deposit = models.FloatField(default=0.00)
    balance = models.FloatField(default=0.00)
    def __str__(self):
        return self.user.username

class Operator(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10)
    def __str__(self):
        return self.name

class Transaction(models.Model):
    choices = [
        ('deposit', 'Investment'),
        ('withdraw', 'Withdraw'),
        ('referal', 'Referal'),
    ]
    state = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.FloatField()
    status = models.CharField(max_length=255, choices=state)
    type = models.CharField(max_length=255, choices=choices)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.user.username