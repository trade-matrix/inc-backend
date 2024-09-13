from django.db import models
from accounts.models import Customer
# Create your models here.
class Investment(models.Model):
    user = models.ManyToManyField(Customer, related_name='investors', blank=True)
    amount = models.FloatField()
    title = models.IntegerField()
    interest = models.FloatField()
    status = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=False)
    def __str__(self):
        return self.title