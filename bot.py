import discord
import json
import os
import asyncio
from datetime import datetime

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.messages = True
bot = discord.Client(intents=intents)

def log_action(action: str) -> None:
    with open("bot_log.txt", "a", encoding="utf-8") as log_file:
        log_file.write(f"{datetime.now()}: {action}\n")

def load_json(file_path: str) -> dict:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {"users": []}

def save_json(file_path: str, data: dict) -> None:
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

async def run_scrape():
    log_action("Running scrape.py")
    process = await asyncio.create_subprocess_exec(
        "python", "scrape.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if stdout:
        print(f"[stdout]\n{stdout.decode()}")
    if stderr:
        print(f"[stderr]\n{stderr.decode()}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    
    # Run scrape.py on startup
    await run_scrape()
    await notify_users()

    # Schedule scrape.py to run every 10 minutes
    async def periodic_scrape():
        while True:
            await asyncio.sleep(600)
            await run_scrape()
            await notify_users()

    bot.loop.create_task(periodic_scrape())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.strip()
    if content.startswith('!ap'):
        command_parts = content.split()
        if len(command_parts) < 2:
            await message.channel.send("Invalid command. Use !ap add/remove [room] [slot] or !ap remove all.")
            return

        command = command_parts[1]
        user_id = message.author.id
        username = str(message.author)

        trackers_file_path = "trackers_to_scrape.json"
        trackers = load_json(trackers_file_path)

        # Ensure "users" key exists in the trackers dictionary
        if "users" not in trackers:
            trackers["users"] = []

        # Update existing entries to include user_id if missing
        for user in trackers["users"]:
            if "user_id" not in user:
                user["user_id"] = message.author.id

        user_entry = next((user for user in trackers["users"] if user["user_id"] == user_id), None)

        if command == "add" and len(command_parts) == 4:
            room, slot = command_parts[2], command_parts[3]
            if not user_entry:
                trackers["users"].append({"user_id": user_id, "username": username, "trackers": [{"room": room, "slot": slot}]})
            else:
                user_trackers = user_entry["trackers"]
                if not any(tracker["room"] == room and tracker["slot"] == slot for tracker in user_trackers):
                    user_trackers.append({"room": room, "slot": slot})
            save_json(trackers_file_path, trackers)
            await message.channel.send(f"Added {room} {slot} for {username}.")
            log_action(f"User {username} added room {room} and slot {slot}.")

        elif command == "remove" and len(command_parts) == 4:
            room, slot = command_parts[2], command_parts[3]
            if user_entry:
                original_length = len(user_entry["trackers"])
                user_entry["trackers"] = [tracker for tracker in user_entry["trackers"] if not (tracker["room"] == room and tracker["slot"] == slot)]
                if len(user_entry["trackers"]) < original_length:
                    save_json(trackers_file_path, trackers)
                    await message.channel.send(f"Removed {room} {slot} for {username}.")
                    log_action(f"User {username} removed room {room} and slot {slot}.")
                else:
                    await message.channel.send(f"No entry found for {room} {slot} for {username}.")
            else:
                await message.channel.send(f"No entries found for {username}.")

        elif command == "remove" and len(command_parts) == 3 and command_parts[2] == "all":
            if user_entry:
                trackers["users"].remove(user_entry)
                save_json(trackers_file_path, trackers)
                await message.channel.send(f"Removed all tracked slots for {username}.")
                log_action(f"User {username} removed all tracked slots.")
            else:
                await message.channel.send(f"No entries found for {username}.")

        else:
            await message.channel.send("Invalid command. Use !ap add/remove [room] [slot] or !ap remove all.")

async def notify_users():
    json_file_path = "recent_checks.json"
    data = load_json(json_file_path)

    if not data.get("entries"):
        print("No new items to notify.")
        return

    for user_data in data["entries"]:
        user_id = user_data["user_id"]
        user = await bot.fetch_user(user_id)
        if user is None:
            print(f"User ID {user_id} not found.")
            continue

        for tracker in user_data["trackers"]:
            if tracker["items"]:
                room = tracker["room"]
                slot = tracker["slot"]
                items = "\n".join([f"{item['name']} (Order Received: {item['lastOrderReceived']})" for item in tracker["items"]])
                message = f"Room: {room}, Slot: {slot} has received the following items:\n{items}"
                await user.send(message)
                log_action(f"Sent notification to user ID {user_id} for room {room} and slot {slot}.")
                await asyncio.sleep(1)  # Delay to avoid sending messages too fast - don't know if necessary.

if __name__ == "__main__":
    bot.run(TOKEN)
