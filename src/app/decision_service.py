import sys
import os
import json
from commons.FileUtils import FileUtils
from commons.llm_utils import LLMUtils
from groq import Groq

if __name__ == "__main__":
    # Collect all ride outputs from output folder matching ridesIIIPL*
    rides_folder = "src/output"
    bills = []
    for fname in os.listdir(rides_folder):
        if fname.startswith("ridesIIIPL") and os.path.isfile(os.path.join(rides_folder, fname)):
            try:
                file_bills = FileUtils.load_json_from_file(os.path.join(rides_folder, fname))
                if isinstance(file_bills, list):
                    bills.extend(file_bills)
                else:
                    bills.append(file_bills)
            except Exception as e:
                print(f"⚠️ Failed to load {fname}: {e}")

    # Load policy JSON from output
    policy = FileUtils.load_json_from_file(
        "src/output/policy.json"
    )

    if not bills:
        print("❌ No bills found in ridesIIIPL output files.")
        sys.exit(1)

    #bills = bills[:2]
    # Separate valid and invalid bills based on 'validation' key
    valid_bills = [b for b in bills if b.get("validation").get("is_valid")]
    invalid_bills = [b for b in bills if not b.get("validation").get("is_valid")]

    # Calculate statistics for display
    total_valid_amount = sum(b.get("amount", 0) for b in valid_bills if isinstance(b.get("amount", 0), (int, float)))
    valid_bill_ids = [b.get("ride_id") for b in valid_bills]
    invalid_bill_ids = [b.get("ride_id") for b in invalid_bills]

    print(f"✅ Valid bill IDs: {valid_bill_ids}")
    print(f"💰 Total amount for valid bills: {total_valid_amount}")
    print(f"❌ Invalid bill IDs: {invalid_bill_ids}")

    # For testing, process all valid bills if available, else stop processing
    if valid_bills:
        bill = valid_bills  # send the whole array of valid bills instead of just the first
    else:
        print("❌ No valid bills found. Skipping LLM decision process.")
        sys.exit(0)

    # Get bills for same employee and month from valid bills
    bills_this_month = [
        b for b in valid_bills
        if b.get("emp_id") == bill[0].get("emp_id") and b.get("month") == bill[0].get("month")
    ]

    # Pre-calculate monthly total to avoid LLM math mistakes
    monthly_total = sum(float(b.get("amount", 0) or 0) for b in bills_this_month)

    # Load and update the system prompt
    system_prompt = FileUtils.load_text_file(
        "src/prompt/system_prompt_decision.txt"
    )
    system_prompt += (
        "\n\nNote: Monthly total for this employee in this category has been pre-calculated "
        f"and is {monthly_total}. Use this value directly for comparison with the monthly cap; "
        "\nBills data is directly taken from rides output files and policy from policy.json."
        "\nAlso note: INVALID bills are excluded from monthly limit calculation but listed separately."
        f"\nImportant: The output must clearly display the employee_id ({bill[0].get('emp_id')}) "
        f"and employee_name ({bill[0].get('emp_name')}) along with the decision results."
    )

    # Construct the user prompt with pre-calculated monthly_total
    user_prompt = json.dumps({
        "bill": bill,
        "policy": policy,
        "bills_this_month": bills_this_month,
        "monthly_total": monthly_total,
        "invalid_bills": invalid_bills
    }, indent=2)

    # Call LLM and print only the decision output
    model = "llama-3.3-70b-versatile"
    client = Groq()
    output = LLMUtils.call_llm(client, model, system_prompt, user_prompt, 0)
    print("\n📄 Decision Output:")
    print(output)
