# custom_exceptions.py

class ExternalAPIError(Exception):
    def __init__(self, status_code, details):
        self.status_code = status_code
        self.details = details
        super().__init__(f"External API Error: {status_code} - {details}")
