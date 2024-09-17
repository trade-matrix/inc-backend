from django.contrib import admin
from .models import *
# Register your models here.
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'username', 'verified']
    list_filter = ['verified']
    search_fields = ['phone_number', 'username']
admin.site.register(Customer, CustomerAdmin)