import os
import json
import asyncio
import nats
import google.generativeai as genai
from rivian_python_api import Rivian

# --- 1. Rivian Token Management ---
def get_authenticated_rivian():
    with open("/data/rivian_tokens.json", "r") as f:
        data = json.load(f)

    rivian = Rivian()
    # Using your underscore key
    rivian.create_session(data["_refreshToken"])
    return rivian

def get_vehicle_info():
    """Fetches the current battery level and range of the Rivian."""
    # We define this as a regular 'def' because the library is sync
    # and Gemini handles standard function execution without warnings.
    rivian = get_authenticated_rivian()

    vehicles = rivian.get_vehicles()
    v_id = vehicles[0]['vehicleId']
    state = rivian.get_vehicle_state(v_id)

    return {
        "soc": state['energyStorage']['soc']['value'],
        "range_miles": state['energyStorage']['distanceToEmpty']['value'],
        "charger_status": state['chargerState']['status']['value']
    }

# --- 3. Gemini Configuration ---
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    tools=[get_vehicle_info]
)

# --- 4. The NATS Handler ---
async def message_handler(msg):
    subject = msg.subject
    reply = msg.reply
    data = msg.data.decode()

    print(f"Received request on {subject}: {data} {reply}")

    # Start a chat session with Function Calling enabled
    chat = model.start_chat(enable_automatic_function_calling=True)

    try:
        # Gemini decides if it needs to call get_vehicle_info based on the prompt
        response = await chat.send_message_async(data)

        # Send the final natural language answer back to the reply topic
        if reply:
            await nc.publish(reply, response.text.encode())
            print(f"Replied with: {response.text}")

    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(error_msg)
        if reply:
            await nc.publish(reply, error_msg.encode())

# --- 5. Main Loop ---
async def main():
    global nc
    # Connect to NATS (Use the explicit IPv4 to avoid the timeout you saw)
    nats_url = os.getenv("NATS_URL", "nats://100.74.109.126:4222")

    try:
        nc = await nats.connect(nats_url)
        print(f"Connected to NATS at {nats_url}")

        # Subscribe to the topic (matches the one published by your Slack bot)
        await nc.subscribe("rivian.ai.prompt", cb=message_handler)
        print("Listening for Rivian AI prompts...")

        # Keep the connection alive
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"NATS Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())