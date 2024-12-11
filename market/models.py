from django.db import models
from accounts.models import Customer
# Create your models here.
class Investment(models.Model):
    user = models.ManyToManyField(Customer, related_name='investors', blank=True)
    amount = models.FloatField()
    title = models.CharField(max_length=255)
    interest = models.FloatField()
    author = models.CharField(max_length=255, blank=True, null=True)
    status = models.BooleanField(default=True)
    number = models.IntegerField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    image = models.ImageField(blank=True, null=True, upload_to='investment/')
    created_at = models.DateTimeField(auto_now_add=False)
    def __str__(self):
        return self.title
    
class Wallet(models.Model):
    user = models.OneToOneField(Customer, on_delete=models.CASCADE)
    deposit = models.FloatField(default=0.00)
    balance = models.FloatField(default=0.00)
    amount_from_games = models.FloatField(default=0.00)
    deposit_used = models.BooleanField(default=False)
    tier = models.IntegerField(default=1)
    eligible = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    date_made_eligible = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    def __str__(self):
        return self.user.username

class Task(models.Model):
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    allocated_tier_1_members = models.IntegerField()
    allocated_tier_2_members = models.IntegerField()
    allocated_tier_3_members = models.IntegerField()
    tier_1_completed = models.BooleanField(default=False)
    tier_2_completed = models.BooleanField(default=False)
    tier_3_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.title

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
    reffered = models.CharField(max_length=255, blank=True)
    image = models.CharField(max_length=255, blank=True)
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
    operator = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    settled = models.BooleanField(default=False)
    messaged = models.BooleanField(default=False)
    class Meta:
        verbose_name = 'Requested Withdraw'
        verbose_name_plural = 'Requested Withdraws'
    def __str__(self):
        return self.user.username
    
class Game(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey(Customer, related_name='players', blank=True, on_delete=models.CASCADE)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    today = models.BooleanField(default=False)
    def __str__(self):
        return self.name