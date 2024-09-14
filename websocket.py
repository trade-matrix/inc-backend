import asyncio
import json
import websockets

async def test():
    token = "69c8e96ffe6781aa582b95e360826b32febe6f20"
    async with websockets.connect(f"ws://127.0.0.1:8000/ws/balance/?token={token}") as websocket:
        # Listen for messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received message: {data}")

asyncio.run(test())
