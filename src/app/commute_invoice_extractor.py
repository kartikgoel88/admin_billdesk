import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.validate_commute_fields import ValidateCommuteFeilds

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from commons.constants import Constants as Co
from commons.FileUtils import FileUtils
from commons.config_reader import config
from entity.ride_extraction_schema import RideExtractionList
import json
from datetime import datetime
from rapidfuzz import fuzz

## Run command : python src/bill_extractor_tesseract.py D:/pycharm/admin_billdesk/resources/IIIPL-1011_smitha_oct_tesco D:\pycharm\admin_billdesk\src\prompt\system_prompt_cab.txt
## export api key via PS :$env:GROQ_API_KEY="API_KEY"


class CommuteExtractor:
    def __init__(self, input_folder, system_prompt_path):
        self.input_folder = input_folder
        self.system_prompt_path = system_prompt_path
        self.output_folder = "src/model_output/commute/" + config[Co.LLM][Co.MODEL] + "/"
        self.employee_meta = FileUtils.extract_info_from_foldername(self.input_folder)
        self.category = {"category":"cab"}
        # Load receipts from folder
        # Should return a list of:  {"filename": "...", "text": "..."}
        self.receipts = FileUtils.process_folder(self.input_folder)
        print("\n[Receipts loaded]")

        with open("clients.json", "r", encoding="utf-8") as f:
            self.client_addresses = json.load(f)

        # Load system prompt
        self.system_prompt = FileUtils.load_text_file(system_prompt_path)
        print("\n[Loaded System Prompt]")
        print(self.system_prompt)

        # Choose model
        self.llm = ChatGroq(
            model = config[Co.LLM][Co.MODEL],
            temperature= config[Co.LLM][Co.TEMPERATURE]
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
                    **self.employee_meta.to_dict(),
                    **self.category
                }

                validation = ValidateCommuteFeilds.validate_ride(enriched, self.client_addresses)
                enriched["validation"] = validation

                validated_results.append(enriched)

            json_output = json.dumps(
                validated_results,
                indent=4,
                ensure_ascii=False
            )

            FileUtils.write_json_to_file(json_output, self.output_folder + self.input_folder.split("/")[-1])
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
