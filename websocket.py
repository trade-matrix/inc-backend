import asyncio
import json
import websockets

async def test():
    token = "0cb3431a6a8d1e2e905779b806c7d3cba8d48807"
    async with websockets.connect(f"wss://api-dkqs.onrender.com/ws/balance/?token={token}") as websocket:
        # Listen for messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received message: {data}")

asyncio.run(test())
