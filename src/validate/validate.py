import json
import re
from pathlib import Path
from typing import List, Optional

from thefuzz import fuzz

try:
    from sentence_transformers import SentenceTransformer, util
    MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
except ImportError:
    MODEL = None
    print("⚠ sentence-transformers not installed. Address similarity will use token overlap only.")

# ----------------------------
# Utilities
# ----------------------------
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def word_match(emp_name: str, rider_name: str) -> bool:
    emp_words = emp_name.strip().split()
    rider_words = rider_name.strip().split()
    return any(ew.lower() == rw.lower() for ew in emp_words for rw in rider_words)

def normalize_address(addr: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+", addr.lower())

def token_overlap_similarity(addr1: str, addr2: str) -> float:
    """Simple token overlap score between two addresses."""
    if not addr1 or not addr2:
        return 0.0
    tokens1 = set(normalize_address(addr1))
    tokens2 = set(normalize_address(addr2))
    if not tokens1 or not tokens2:
        return 0.0
    matches = len(tokens1 & tokens2)
    return matches / len(tokens1)  # ratio of addr1 tokens present in addr2

def address_similarity(addr1: str, addr2: str) -> float:
    """Semantic similarity if model available, fall back to token overlap."""
    if not addr1 or not addr2:
        return 0.0
    if MODEL:
        emb1 = MODEL.encode(addr1, convert_to_tensor=True)
        emb2 = MODEL.encode(addr2, convert_to_tensor=True)
        return float(util.cos_sim(emb1, emb2))
    else:
        return token_overlap_similarity(addr1, addr2)

def partial_address_match(address_list: List[str], ride_addr: str, threshold: float = 0.40) -> float:
    """Returns best similarity score, matching ride address to any in address_list."""
    if not ride_addr:
        return 0.0
    scores = [address_similarity(ride_addr, ref) for ref in address_list]
    return max(scores) if scores else 0.0

# ----------------------------
# Validation Logic
# ----------------------------
def validate():
    employee_data = load_json(Path(__file__).parent / "employee.json")
    rides_data = load_json(Path(__file__).parent / "rides.json")

    # Build filename -> employee meta mapping
    attachment_map = {}
    for emp_code, emp_info in employee_data.items():
        for attachment in emp_info.get("Attachments", []):
            attachment_map[attachment['filename']] = {
                "emp_name": emp_info.get("emp_name", ""),
                "attachment_date": attachment['date'],
                "employee_address": emp_info.get("employee_address", []),
                "client_address": emp_info.get("client_addresses", [])
            }

    for ride in rides_data:
        filename = ride.get("filename")
        errors = []

        # 1. Filename check
        if filename not in attachment_map:
            errors.append(" Filename not found in employee Attachments")
            ride["validation_result"] = "Invalid"
            ride["validation_error"] = errors
            continue

        emp_info = attachment_map[filename]

        # 2. Date match (strict)
        if ride.get("date") != emp_info["attachment_date"]:
            errors.append(f" Date mismatch: Attachment={emp_info['attachment_date']} Ride={ride.get('date')}")

        # 3. Pickup/Drop match (flexible: employee OR client address)
        pickup_score = partial_address_match(emp_info["employee_address"] + emp_info["client_address"], ride.get("pickup_address", ""), threshold=0.40)
        drop_score = partial_address_match(emp_info["employee_address"] + emp_info["client_address"], ride.get("drop_address", ""), threshold=0.40)
        ride["pickup_match_score"] = pickup_score
        ride["drop_match_score"] = drop_score

        if pickup_score < 0.40 or drop_score < 0.40:
            errors.append(f" Pickup/Drop mismatch: pickup_score={pickup_score:.2f}, drop_score={drop_score:.2f}")

        # 4. Name match (fuzz + strict word)
        name_score = 0
        if ride.get("rider_name"):
            name_score = fuzz.token_set_ratio(ride["rider_name"], emp_info["emp_name"])
        ride["name_match_score"] = name_score

        if not (word_match(emp_info["emp_name"], ride.get("rider_name", "")) or name_score >= 75):
            errors.append(f" Rider name mismatch: Rider='{ride.get('rider_name', '')}' Emp='{emp_info['emp_name']}' Score={name_score}")

        # Set results
        if errors:
            ride["validation_result"] = "Invalid"
            ride["validation_error"] = errors
        else:
            ride["validation_result"] = "Valid"
            ride["validation_error"] = []

    # Save validated rides
    output_path = Path(__file__).parent / "rides_validated.json"
    save_json(output_path, rides_data)
    print(f"✅ Validation complete. Output written to {output_path}")

if __name__ == "__main__":
    validate()
