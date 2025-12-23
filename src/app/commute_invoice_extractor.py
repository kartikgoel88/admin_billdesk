import os

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.FileUtils import FileUtils
from entity.ride_extraction_schema import RideExtractionList
import json
from datetime import datetime
from rapidfuzz import fuzz

## Run command : python src/bill_extractor_tesseract.py D:/pycharm/admin_billdesk/resources/IIIPL-1011_smitha_oct_tesco D:\pycharm\admin_billdesk\src\prompt\system_prompt_cab.txt
## export api key via PS :$env:GROQ_API_KEY="API_KEY"
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

class CommuteExtractor:

    def __init__(self, input_folder, system_prompt_path):
        self.input_folder = input_folder
        self.system_prompt_path = system_prompt_path

        with open("clients.json", "r", encoding="utf-8") as f:
            self.client_addresses = json.load(f)

        self.employee_meta = FileUtils.extract_info_from_foldername(self.input_folder)
        print(self.employee_meta)
        # Load receipts from folder
        # Should return a list of:  {"filename": "...", "text": "..."}
        self.receipts = FileUtils.process_folder(self.input_folder)
        print("\n[Receipts loaded]")
        print(self.receipts)

        # Load system prompt
        self.system_prompt = FileUtils.load_text_file(system_prompt_path)
        print("\n[Loaded System Prompt]")
        print(self.system_prompt)

        # Choose model
        self.model_name = "llama-3.3-70b-versatile"

        self.llm = ChatGroq(
            model=self.model_name,
            temperature=0
        )

        # Pydantic parser ensures consistency and zero hallucination
        self.parser = PydanticOutputParser(pydantic_object=RideExtractionList)

        # Build prompt
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "{system_prompt}"
            ),
            (
                "human",
                "Here are the receipts:\n{receipts_json}\n\n"
                "Output must follow this JSON schema:\n{format_instructions}"
            )
        ])

        # Final chain (Prompt → Model → Parser)
        self.chain = self.prompt | self.llm | self.parser

    def validate_ride(self,ride: dict, client_addresses: dict) -> dict:
        validations = {}

        # -------------------------
        # 1. Month validation
        # -------------------------
        try:
            ride_month = datetime.strptime(ride["date"], "%d/%m/%Y").month
            expected_month = MONTH_MAP.get(ride["month"].lower())
            validations["month_match"] = (ride_month == expected_month)
        except Exception:
            validations["month_match"] = False

        # -------------------------
        # 2. Name validation (75%)
        # -------------------------
        rider = (ride.get("rider_name") or "").lower()
        emp = (ride.get("emp_name") or "").lower()

        name_score = fuzz.partial_ratio(rider, emp)
        validations["name_match_score"] = name_score
        validations["name_match"] = name_score >= 75

        # -------------------------
        # 3. Address validation (40%)
        # -------------------------
        pickup = (ride.get("pickup_address") or "").lower()
        drop = (ride.get("drop_address") or "").lower()

        client = ride.get("client", "").upper()
        addresses = client_addresses.get(client, [])

        best_address_score = 0

        for addr in addresses:
            addr = addr.lower()
            best_address_score = max(
                best_address_score,
                fuzz.partial_ratio(pickup, addr),
                fuzz.partial_ratio(drop, addr)
            )

        validations["address_match_score"] = best_address_score
        validations["address_match"] = best_address_score >= 40

        # -------------------------
        # Final decision
        # -------------------------
        validations["is_valid"] = all([
            validations["month_match"],
            validations["name_match"],
            validations["address_match"]
        ])

        return validations

    # ------------------------
    # Run Extraction
    # ------------------------
    def run(self):
        print("\n[Starting Extraction]\n")

        try:
            result: RideExtractionList = self.chain.invoke({
                "system_prompt": self.system_prompt,
                "receipts_json": self.receipts,
                "format_instructions": self.parser.get_format_instructions()
            })

            output_data = result.root  # List[RideExtraction]
            print("\n✔ Batch Extracted Successfully")
            print(output_data)

            validated_results = []

            for item in output_data:
                enriched = {
                    **item.model_dump(),
                    **self.employee_meta.to_dict()
                }

                validation = self.validate_ride(enriched, self.client_addresses)
                enriched["validation"] = validation

                validated_results.append(enriched)

            json_output = json.dumps(
                validated_results,
                indent=4,
                ensure_ascii=False
            )

            FileUtils.write_json_to_file(json_output, "rides.json")

        except Exception as e:
            print(f"❌ Error during batch extraction: {e}")


# ------------------------
# Script Entry Point
# ------------------------

if __name__ == "__main__":
    input_folder = sys.argv[1]
    system_prompt_file_path = sys.argv[2]

    extractor = CommuteExtractor(input_folder, system_prompt_file_path)
    extractor.run()
