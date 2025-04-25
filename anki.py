import json
import os
import uuid
from datetime import datetime, timedelta

ANKI_FILE = "anki.json"

def load_anki_data():
    """Loads flashcard data from JSON file."""
    if not os.path.exists(ANKI_FILE):
        return {"cards": []}
    try:
        with open(ANKI_FILE, 'r') as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {ANKI_FILE}. Returning empty card list.")
        return {"cards": []}

def save_anki_data(data):
    """Saves flashcard data to JSON file."""
    with open(ANKI_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def create_card(front, back, reverse=False):
    """Creates a new flashcard and its reverse if specified."""
    data = load_anki_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create main card
    card_id = uuid.uuid4().hex
    new_card = {
        "id": card_id,
        "front": front,
        "back": back,
        "reverse": reverse,
        "easiness_factor": 2.5,
        "interval": 1,
        "repetitions": 0,
        "review_date": today,
        "created_date": today
    }
    data["cards"].append(new_card)
    
    # Create reverse card if requested
    if reverse:
        reverse_id = uuid.uuid4().hex
        reverse_card = {
            "id": reverse_id,
            "front": back,
            "back": front,
            "reverse": False,  # Don't mark the reverse card as reverse
            "easiness_factor": 2.5,
            "interval": 1,
            "repetitions": 0,
            "review_date": today,
            "created_date": today
        }
        data["cards"].append(reverse_card)
    
    save_anki_data(data)
    return card_id

def get_card(card_id):
    """Retrieves a specific flashcard by ID."""
    data = load_anki_data()
    return next((card for card in data["cards"] if card["id"] == card_id), None)

def update_card(card_id, front, back, reverse=False):
    """Updates an existing flashcard."""
    data = load_anki_data()
    card = next((card for card in data["cards"] if card["id"] == card_id), None)
    
    if card:
        # Check if this was previously a reverse card
        was_reverse = card.get("reverse", False)
        
        # Update the card
        card["front"] = front
        card["back"] = back
        card["reverse"] = reverse
        
        # Handle the reverse card
        reverse_card = None
        if was_reverse:
            # Find the existing reverse card (if any)
            for c in data["cards"]:
                if c["front"] == card["back"] and c["back"] == card["front"]:
                    reverse_card = c
                    break
        
        if reverse and not was_reverse:
            # Create a new reverse card
            create_card(back, front, False)
        elif not reverse and was_reverse and reverse_card:
            # Remove the reverse card
            data["cards"] = [c for c in data["cards"] if c["id"] != reverse_card["id"]]
        elif reverse and was_reverse and reverse_card:
            # Update existing reverse card
            reverse_card["front"] = back
            reverse_card["back"] = front
        
        save_anki_data(data)

def delete_card(card_id):
    """Deletes a flashcard and its reverse if it exists."""
    data = load_anki_data()
    card = next((card for card in data["cards"] if card["id"] == card_id), None)
    
    if card:
        # Remove the card
        data["cards"] = [c for c in data["cards"] if c["id"] != card_id]
        
        # If this is a card with a reverse, remove the reverse too
        if card.get("reverse", False):
            for c in list(data["cards"]):
                if c["front"] == card["back"] and c["back"] == card["front"]:
                    data["cards"] = [x for x in data["cards"] if x["id"] != c["id"]]
        
        save_anki_data(data)

def get_due_cards():
    """Returns all cards due for review."""
    data = load_anki_data()
    today = datetime.now().strftime("%Y-%m-%d")
    
    due_cards = [card for card in data["cards"] 
                if card["review_date"] <= today]
    
    return due_cards

def process_card_review(card_id, rating):
    """Processes a card review using the SM2 algorithm."""
    data = load_anki_data()
    card = next((card for card in data["cards"] if card["id"] == card_id), None)
    
    if card:
        # Apply SM2 algorithm
        if rating < 3:
            # If rating is less than 3, reset repetitions
            card["repetitions"] = 0
            card["interval"] = 1
        else:
            # Calculate new interval
            if card["repetitions"] == 0:
                card["interval"] = 1
            elif card["repetitions"] == 1:
                card["interval"] = 6
            else:
                card["interval"] = round(card["interval"] * card["easiness_factor"])
            
            # Increment repetition counter
            card["repetitions"] += 1
        
        # Update easiness factor
        card["easiness_factor"] = max(1.3, card["easiness_factor"] + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02)))
        
        # Calculate next review date
        next_date = datetime.now() + timedelta(days=card["interval"])
        card["review_date"] = next_date.strftime("%Y-%m-%d")
        
        save_anki_data(data)