from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from.views import HelloWorldView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HelloWorldView.as_view(), name='hello_world'),
    path('accounts/', include('accounts.urls')),
    path('market/', include('market.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)