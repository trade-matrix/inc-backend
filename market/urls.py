from django.urls import path
from .views import *

urlpatterns = [
    path('webhook/', webhook_view, name='webhook'),
    path('invest/', UserInvest.as_view(), name='invest'),
    path('create-payment-link/', CreatePaymentLink.as_view(), name='create-payment-link'),
    path('investments/', InvestmentListView.as_view(), name='investments'),
    path('confirm/', VerifyPayment.as_view(), name='confirm'),
    path('withdraw/', WithdrawfromWallet.as_view(), name='withdraw'),
    path('check/', CheckUserMomo.as_view(), name='check'),
    path('transactions/', TransactionListView.as_view(), name='transactions'),
    path('wallet/', UserWalletView.as_view(), name='wallet'),
    path('modify-wallet/', IncreaseBalancePrediction.as_view(), name='modify-wallet'),
    path('increase-balace/', IncreaseBalance.as_view(), name='increase-wallet'),
    path('comment/', CommentView.as_view(), name='comment'),
    path('top-earners/', TopEarners.as_view(), name='top-earners'),
    path('top-earners/gc/', TopEarnersGc.as_view(), name='top-earners-gc'),
    path('alert/', AlertUsersonCompletedWithdrawal.as_view(), name='alert'),
    path('alert/gc/', AlertUsersonCompletedWithdrawalGC.as_view(), name='alert-gc'),
    path('game/', GameView.as_view(), name='game'),
    path('off/today/', SetGameTodayFalse.as_view(), name='game-today'),
    path('revert/', RevertWithdrawals.as_view(), name='revert'),
    path('distribute-pool/', DistributePoolEarnings.as_view(), name='distribute-pool'),
    path('pool-status/', UserPoolGroupStatus.as_view(), name='pool-status'),
]
