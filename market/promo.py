def message_decider(message, customer, percentage):
    if message == 'news':
        return f"""
            Hello {customer.username},

We are excited to inform you that for today only, your Math Game scores will equal the exact points you earn, rather than being divided by 10 as they were previously!

Take advantage of this exclusive offer now!

Terms and conditions apply.
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