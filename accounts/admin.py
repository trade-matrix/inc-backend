from django.contrib import admin
from .models import *
# Register your models here.
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['username', 'phone_number', 'platform', 'verified']
    list_filter = ['verified','platform']
    search_fields = ['phone_number', 'username', 'email']
admin.site.register(Customer, CustomerAdmin)

class RefAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user']
    search_fields = ['reference']
admin.site.register(Ref, RefAdmin)