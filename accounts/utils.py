import requests
import os
from .exceptions import ExternalAPIError
def send_otp(phone, username):
        message = f"Hello {username},"
        data = {
        'expiry': 5,
        'length': 6,
        'medium': 'sms',
        'message': message+' This is your login OTP code:\n%otp_code%\nPlease do not share this code with anyone.',
        'number': phone,
        'sender_id': 'TMHub',
        'type': 'numeric',
        }

        headers = {
        'api-key': os.environ.get('ARK_API_KEY'),
        }

        url = 'https://sms.arkesel.com/api/otp/generate'

        try:
            response = requests.post(url, json=data, headers=headers)
            if response.status_code != 200:
                raise ExternalAPIError(response.status_code, response.json())
            else:
                return response.json()
        except requests.RequestException as e:
            raise ExternalAPIError(500, str(e))