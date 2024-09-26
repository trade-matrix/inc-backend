from django.contrib import admin
from django.urls import path,include
from.views import HelloWorldView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HelloWorldView.as_view(), name='hello_world'),
    path('accounts/', include('accounts.urls')),
    path('market/', include('market.urls')),
]
