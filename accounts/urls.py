from django.urls import path
from .views import *

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('login/verify/', UserOtpVerificationLogin.as_view(), name='login-verify'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('verify/', UserOtpVerification.as_view(), name='verify'),
    path('resend-otp/', UserResendOTP.as_view(), name='resend-otp'),
    path('users/', TotalNumberOfUsers.as_view(), name='users'),
]
