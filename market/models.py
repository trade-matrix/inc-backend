from django.db import models
from accounts.models import Customer
# Create your models here.
class Investment(models.Model):
    user = models.ManyToManyField(Customer, related_name='investors', blank=True)
    amount = models.FloatField()
    title = models.CharField(max_length=255)
    interest = models.FloatField()
    status = models.BooleanField(default=True)
    image = models.ImageField(upload_to='investment', blank=True)
    created_at = models.DateTimeField(auto_now_add=False)
    def __str__(self):
        return self.title
    
class Wallet(models.Model):
    user = models.OneToOneField(Customer, on_delete=models.CASCADE)
    deposit = models.FloatField(default=0.00)
    balance = models.FloatField(default=0.00)
    eligible = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    date_made_eligible = models.DateTimeField(auto_now_add=False, blank=True, null=True)
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

class Comment(models.Model):
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)
    comment = models.TextField()
    name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=False)
    def __str__(self):
        return self.user.username

class Requested_Withdraw(models.Model):
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.FloatField()
    phone_number = models.CharField(max_length=255)
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    settled = models.BooleanField(default=False)
    def __str__(self):
        return self.user.username