import os
import asyncio
import nats
from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

# 1. Initialize Slack App
# IMPORTANT: 'token' here must be the xoxb- BOT token
app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

@app.command("/deezwatts")
async def handle_rivian_command(ack, respond, command):
    # Acknowledge the command immediately
    await ack()

    user_prompt = command.get('text')
    if not user_prompt:
        await respond("Please provide a prompt, e.g., `/deezwatts How is my range?`")
        return

    try:
        # 2. Connect to NATS
        nc = await nats.connect("nats://100.74.109.126:4222")

        # 3. Request-Reply Pattern
        # This creates the 'reply' inbox that your Gemini script was looking for
        print(f"Sending to NATS: {user_prompt}")
        nats_response = await nc.request("rivian.ai.prompt", user_prompt.encode(), timeout=15)

        # 4. Respond back to Slack
        # nats_response.data is the bytes returned by Gemini
        answer = nats_response.data.decode()
        await respond(answer)

        await nc.close()

    except asyncio.TimeoutError:
        await respond("⏳ Gemini is taking a while to talk to the truck. Try again in a second.")
    except Exception as e:
        await respond(f"❌ Error: {str(e)}")

async def main():
    # 5. Socket Mode Handler
    # IMPORTANT: The second argument here must be the xapp- APP token
    handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())