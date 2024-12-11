def message_decider(message, customer, percentage):
    if message == 'news':
        return f"""
            Hello {customer.username},
Please informed that Trade-Matrix will undergo a massive maintenance in this week and as such all transactions, especially deposits may not work.
Bear with us for this week as we are working hard to bring best services to all our cherished investors.
Sorry for any inconvenience this may cause.
The Trade-Matrix Team.
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