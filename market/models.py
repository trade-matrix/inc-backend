from django.db import models
from accounts.models import Customer
from django.db.models import DecimalField
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
    withdrawable = models.FloatField(default=0.00)
    amount_from_games = models.FloatField(default=0.00)
    deposit_used = models.BooleanField(default=False)
    tier = models.IntegerField(default=1)
    eligible = models.BooleanField(default=False)
    active = models.BooleanField(default=False)
    date_made_eligible = models.DateTimeField(auto_now_add=False, blank=True, null=True)
    valid_for_pool = models.BooleanField(default=False)
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
    amount = DecimalField(max_digits=10, decimal_places=2)
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
    name = models.CharField(max_length=255, default='Lucky Draw')
    user = models.ForeignKey(Customer, related_name='players', blank=True, on_delete=models.CASCADE)
    selection = models.CharField(max_length=255, blank=True, null=True)
    winning_numbers = models.CharField(max_length=255, blank=True, null=True)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    won = models.BooleanField(default=False)
    amount_bet = models.FloatField(default=0.00)
    winnings = models.FloatField(default=0.00)
    matches = models.IntegerField(default=0)
    today = models.BooleanField(default=False)
    forced_reason = models.CharField(max_length=255, null=True, blank=True)
    def __str__(self):
        return self.name

class Profit(models.Model):
    name = models.CharField(max_length=255, default='Profit')
    amount_today = models.FloatField()
    total_amount = models.FloatField()
    def __str__(self):
        return self.name

class PoolParticipant(models.Model):
    pool = models.ForeignKey('Pool', on_delete=models.CASCADE)
    user = models.ForeignKey('accounts.Customer', on_delete=models.CASCADE)
    deposit_amount = DecimalField(max_digits=10, decimal_places=2, default=0.00)
    joined_at = models.DateTimeField(auto_now_add=True)

class Pool(models.Model):
    deposits = DecimalField(max_digits=10, decimal_places=2, default=0.00)
    name = models.CharField(max_length=255, default='Pool')
    participants = models.ManyToManyField('accounts.Customer', through='PoolParticipant')

    def __str__(self):
        return self.name
