def message_decider(message, customer, percentage):
    if message == 'news':
        return f"""
Hello Gamer,
Exciting news! We are thrilled to announce we are offering 100% bonus on all deposits made on our platform today.
This means if you deposit GH₵10, you will receive an additional GH₵10, giving you a total of GH₵20 to play with.
Play your favorite games and win big with this limited-time offer. All winnings can be withdrawn instantly.
Don't miss out on this opportunity to boost your wins.
"""
    elif message == 'promo':
        return f"""
Hi {customer.username},
GH₵20 no dey buy fried rice! But manlikeGregg turn am to GH₵1500 cashout.
Val's week dey come… no make them take your girl sake of you dey hide GH₵20.
Secure your spot now before Feb14 to stand a chance to participate in our valentine promo.
Cashouts are quick, secure and easy.
Signed,
~Trade-Matrix
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