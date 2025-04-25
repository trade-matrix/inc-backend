from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class Customer(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    email = models.EmailField(blank=True, null=True)
    REQUIRED_FIELDS = ['phone_number']
    referred_by = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True)
    verified = models.BooleanField(default=False)
    reference = models.CharField(max_length=255, blank=True, null=True)
    referal_code = models.CharField(max_length=255, blank=True, null=True)
    recepient_code = models.CharField(max_length=255, blank=True, null=True)
    withdrawal_reference = models.CharField(max_length=255, blank=True, null=True)
    platform = models.CharField(max_length=255, blank=True, null=True)
    paid = models.BooleanField(default=False)
    affiliate = models.BooleanField(default=False)
    vendor = models.ForeignKey('Vendor', on_delete=models.SET_NULL, blank=True, null=True)

class Vendor(models.Model):
    user = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='vendors')
    code = models.CharField(max_length=255)

    def __str__(self):
        return self.user.username

class Ref(models.Model):
    reference = models.CharField(max_length=255)
    user = models.ForeignKey(Customer, on_delete=models.CASCADE)

    def __str__(self):
        return self.reference