def message_decider(message, customer, percentage):
    if message == 'news':
        return f"""
            Hello {customer.username},
Trade-Matrix is back!
No more withdrawal restrictions - withdraw your earnings anytime.
Earn 50% of your referral's first deposit.
For our loyal users: No deposit needed. Just refer and earn now.
Don't miss this special offer!
"""
    elif message == 'promo':
        return f"""
    Hello {customer.username},

In celebration of achieving {percentage}% of our target, we are pleased to offer you an exclusive 24-hour withdrawal window. This is a prime opportunity to invest more, play more, refer more, and enhance your chances of winning big.

To qualify, ensure you have two completed referals and is among the users with the most interactions by Tuesday. Don't miss out on this special offer.

Terms and conditions apply.
    """
    elif message == 'opened':
        return f"""
    Hello {customer.username},
The 24 hour withdrawal window has been opened. You have from now until tomorrow to make a withdrawal. Don't miss out on this special offer.
"""
    elif message == 'update':
        return f"""
    Hello {customer.username},
Your account deposit has been updated accordingly. You can now proceed to make referals. Don't miss out on this special offer.
"""
    elif message == 'closed':
        return f"""
    Hello {customer.username},
You just earned 10 cedis from your referral. Log in to withdraw your earnings. Don't miss out on this special offer.
"""