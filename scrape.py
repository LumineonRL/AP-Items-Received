import requests
from bs4 import BeautifulSoup
import json
import os
from typing import List, Tuple, Dict, Any

Item = Tuple[str, int]
ScrapedData = List[Item]

def scrape_website(url: str) -> ScrapedData:
    """Scrapes the Archipelago website and returns a list of items with their last order received."""
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to retrieve data: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    items: ScrapedData = []
    table = soup.find("table", {"id": "received-table"})
    if table:
        for row in table.find("tbody").find_all("tr"):
            columns = row.find_all("td")
            if len(columns) >= 3:
                item = columns[0].text.strip()
                last_order_received = int(columns[2].text.strip())
                items.append((item, last_order_received))

    return items

def load_json(file_path: str) -> Dict[str, Any]:
    """Loads JSON data from a file."""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return {"entries": []}

def save_json(file_path: str, data: Dict[str, Any]) -> None:
    """Saves JSON data to a file."""
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def initialize_data(room: str, slot: str, scraped_items: ScrapedData) -> Dict[str, Any]:
    """Initializes the data structure if JSON file does not exist or is empty."""
    highest_item = max(scraped_items, key=lambda x: x[1])
    return {
        "room": room,
        "slot": slot,
        "lastOrderReceived": highest_item[1],
        "items": [{"name": highest_item[0], "lastOrderReceived": highest_item[1]}]
    }

def update_data(scraped_items: ScrapedData, current_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates the data structure if JSON file exists."""
    last_check = current_data.get("lastOrderReceived", 0)
    new_items = [{"name": item, "lastOrderReceived": last_order} for item, last_order in scraped_items if last_order > last_check]

    if new_items:
        # Update the JSON file with new items, keeping only the new ones
        updated_data = {
            "room": current_data["room"],
            "slot": current_data["slot"],
            "items": new_items,
            "lastOrderReceived": max(new_items, key=lambda x: x["lastOrderReceived"])["lastOrderReceived"]
        }
    else:
        updated_data = {
            "room": current_data["room"],
            "slot": current_data["slot"],
            "items": [],
            "lastOrderReceived": last_check
        }

    return updated_data

def process_tracker(room: str, slot: str, user_data: Dict[str, Any]) -> None:
    """Processes a single (room, slot) pair."""
    url = f"https://archipelago.gg/tracker/{room}/0/{slot}"
    scraped_items = scrape_website(url)

    if not scraped_items:
        print(f"No items found on the page for room {room} and slot {slot}.")
        return

    entry_exists = False
    for entry in user_data["trackers"]:
        if entry["room"] == room and entry["slot"] == slot:
            updated_entry = update_data(scraped_items, entry)
            entry.update(updated_entry)
            entry_exists = True
            break

    if not entry_exists:
        new_entry = initialize_data(room, slot, scraped_items)
        user_data["trackers"].append(new_entry)

def main() -> None:
    json_file_path = "recent_checks.json"
    trackers_file_path = "trackers_to_scrape.json"
    
    data = load_json(json_file_path)
    trackers = load_json(trackers_file_path)

    for user in trackers.get("users", []):
        user_data = next((entry for entry in data["entries"] if entry["username"] == user["username"]), None)
        if not user_data:
            user_data = {"username": user["username"], "trackers": []}
            data["entries"].append(user_data)
        
        for tracker in user.get("trackers", []):
            room = tracker.get("room")
            slot = tracker.get("slot")
            if room and slot:
                process_tracker(room, slot, user_data)

    save_json(json_file_path, data)
    print("Data saved to recent_checks.json")

if __name__ == "__main__":
    main()
    