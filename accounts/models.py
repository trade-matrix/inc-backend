from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class Customer(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    email = models.EmailField(blank=True, null=True)
    REQUIRED_FIELDS = ['phone_number']
    referred_users = models.ManyToManyField('self', blank=True)
    verified = models.BooleanField(default=False)
    reference = models.CharField(max_length=10, blank=True, null=True)
   