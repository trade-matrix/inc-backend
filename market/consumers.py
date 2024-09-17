# consumers.py

from channels.generic.websocket import WebsocketConsumer
from asgiref.sync import async_to_sync
import json

class BalanceConsumer(WebsocketConsumer):
    def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            self.user_id = user.id

            # Add the user to a unique group
            async_to_sync(self.channel_layer.group_add)(
                f"user_{self.user_id}",
                self.channel_name
            )

            self.accept()
        else:
            self.close()

    def disconnect(self, close_code):
        # Remove the user from the group
        async_to_sync(self.channel_layer.group_discard)(
            f"user_{self.user_id}",
            self.channel_name
        )

    def send_balance_update(self, event):
        new_balance = event["new_balance"]
        self.send(text_data=json.dumps({
            'new_balance': new_balance
        }))
    
    def send_user_verified(self, event):
        self.send(text_data=json.dumps({
            'user_verified': True
        }))
    
    def send_user_transaction(self, event):
        self.send(text_data=json.dumps({
            'transaction': event['transaction']
        }))
