from django.core.mail import send_mail


def send_password_reset_email(email: str, reset_url: str, token: str):
    subject = "Reset your restaurant menu account password"
    body = (
        "Hello,\n\n"
        "We received a request to reset your password.\n"
        f"Reset URL: {reset_url}\n"
        f"Reset token: {token}\n\n"
        "If you did not request this, you can ignore this message.\n"
    )
    send_mail(subject, body, None, [email], fail_silently=True)
