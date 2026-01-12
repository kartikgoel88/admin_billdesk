import sys
import os
import json
from commons.FileUtils import FileUtils
from commons.llm_utils import LLMUtils
from groq import Groq
import shutil

if __name__ == "__main__":
    # Collect all ride outputs from output folder matching ridesIIIPL*
    rides_folder = "src/output"
    bills_map = {}  # key: "emp_id_emp_name", value: list of bills
    bills = []
    for fname in os.listdir(rides_folder):
        if fname.startswith("ridesIIIPL") and os.path.isfile(os.path.join(rides_folder, fname)):
            try:
                file_bills = FileUtils.load_json_from_file(os.path.join(rides_folder, fname))
                if not isinstance(file_bills, list):
                    file_bills = [file_bills]

                for b in file_bills:
                    emp_id = b.get("emp_id", "")
                    emp_name = b.get("emp_name", "")
                    key = f"{emp_id}_{emp_name}"
                    if key not in bills_map:
                        bills_map[key] = []
                    bills_map[key].append(b)

            except Exception as e:
                print(f"⚠️ Failed to load {fname}: {e}")

    # Flatten bills if you still need a list elsewhere
    bills = [bill for bills_list in bills_map.values() for bill in bills_list]

    # Load policy JSON from output
    policy = FileUtils.load_json_from_file(
        "src/output/policy.json"
    )

    if not bills:
        print("❌ No bills found in ridesIIIPL output files.")
        sys.exit(1)

    # Prepare groups_data for the LLM
    groups_data = []
    save_data = []
    for key, emp_bills in bills_map.items():
        emp_id, emp_name = key.split("_", 1)

        # Separate valid and invalid bills for this person
        valid_for_group = [b for b in emp_bills if b.get("validation", {}).get("is_valid")]
        invalid_for_group = [b for b in emp_bills if not b.get("validation", {}).get("is_valid")]

        # Calculate monthly_total for valid bills
        monthly_total = sum(float(b.get("amount", 0) or 0) for b in valid_for_group)

        # Determine category
        category = ""
        if valid_for_group and valid_for_group[0].get("category") is not None:
            category = valid_for_group[0].get("category")
        elif invalid_for_group and invalid_for_group[0].get("category") is not None:
            category = invalid_for_group[0].get("category")

        groups_data.append({
            "employee_id": emp_id,
            "employee_name": emp_name,
            "category": category,
            "valid_bills": [b.get("ride_id") for b in valid_for_group],
            "invalid_bills": [b.get("ride_id") for b in invalid_for_group],
            "monthly_total": monthly_total
        })
        save_data.append({
            "employee_id": emp_id,
            "employee_name": emp_name,
            "valid_files": [b.get("filename") for b in valid_for_group],
            "invalid_files": [b.get("filename") for b in invalid_for_group]
        })

    # Debug print
    print(f"🗂 Prepared {groups_data} groups for LLM processing.")

    # Construct user prompt using all groups
    user_prompt = json.dumps({
        "policy": policy,
        "groups": groups_data
    }, indent=2)

    # Load and append system prompt
    system_prompt = FileUtils.load_text_file(
        "admin_billdesk/src/prompt/system_prompt_decision.txt"
    )

    model = "llama-3.3-70b-versatile"
    client = Groq()
    output = LLMUtils.call_llm(client, model, system_prompt, user_prompt, 0)

    print("\n📄 All Decisions Output:")
    print(output)

    valid_base_dir = "admin_billdesk/src/output/valid_bills"
    invalid_base_dir = "admin_billdesk/src/output/invalid_bills"
    os.makedirs(valid_base_dir, exist_ok=True)
    os.makedirs(invalid_base_dir, exist_ok=True)
    src_commute_root = "admin_billdesk/resources/commute"

    for emp in save_data:
        emp_id = emp.get("employee_id")
        emp_name = emp.get("employee_name")

        emp_valid_dir = os.path.join(valid_base_dir, f"{emp_id}_{emp_name}")
        emp_invalid_dir = os.path.join(invalid_base_dir, f"{emp_id}_{emp_name}")
        os.makedirs(emp_valid_dir, exist_ok=True)
        os.makedirs(emp_invalid_dir, exist_ok=True)

        valid_files = emp.get("valid_files", [])
        invalid_files = emp.get("invalid_files", [])

        # Determine the commute source folder for the employee
        commute_src_dir = None
        for folder_name in os.listdir(src_commute_root):
            if folder_name.startswith(emp_id):
                commute_src_dir = os.path.join(src_commute_root, folder_name)
                break

        if not commute_src_dir:
            print(f"⚠️ No commute source found for {emp_id}_{emp_name}")
            continue

        # Copy valid files
        for fname in os.listdir(commute_src_dir):
            for vf in valid_files:
                if vf and vf in fname:
                    src_path = os.path.join(commute_src_dir, fname)
                    dest_path = os.path.join(emp_valid_dir, fname)
                    shutil.copy(src_path, dest_path)

        # Copy invalid files
        for fname in os.listdir(commute_src_dir):
            for inf in invalid_files:
                if inf and inf in fname:
                    src_path = os.path.join(commute_src_dir, fname)
                    dest_path = os.path.join(emp_invalid_dir, fname)
                    shutil.copy(src_path, dest_path)

        print(f"✅ Copied files for {emp_id}_{emp_name}: {len(valid_files)} valid, {len(invalid_files)} invalid.")
