from django.urls import path
from .views import *

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('verify/', UserOtpVerification.as_view(), name='verify'),
    path('resend-otp/', UserResendOTP.as_view(), name='resend-otp'),
    path('users/', TotalNumberOfUsers.as_view(), name='users'),
    path('refer/', UserCreateReferalLink.as_view(), name='refer'),
    path('referals/', GetRefferedUsers.as_view(), name='referals'),
    path('investments/', GetUserInvestments.as_view(), name='investments'),
    path('details/', UserDetails.as_view(), name='details'),
    path('delete/', DeleteAccount.as_view(), name='delete'),
    path('check-referal/', NumberofReferralsRequired.as_view(), name='check-referal'),
    path('register/gc/', RegisteronGoldenCash.as_view(), name='register-gc'),
    path('login/gc/', UserLoginGoldenCash.as_view(), name='login-gc'),
]
