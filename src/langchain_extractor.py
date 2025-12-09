import json
import sys
from typing import Optional

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, RootModel

from commons.FileUtils import FileUtils


# ------------------------
# 1. Define Expected Output
# ------------------------

class RideExtraction(BaseModel):
    filename: str
    ride_id: Optional[str]
    date: Optional[str]
    time: Optional[str]
    pickup_address: Optional[str]
    drop_address: Optional[str]
    amount: Optional[float]
    distance_km: Optional[float]
    service_provider: Optional[str]
    ocr: Optional[str]


class RideExtractionList(RootModel[list[RideExtraction]]):
    pass
# ------------------------
# 2. Main Extractor Class
# ------------------------

class Extractor:

    def __init__(self, input_folder, system_prompt_path):
        self.input_folder = input_folder
        self.system_prompt_path = system_prompt_path

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

            json_output = json.dumps(
                [item.model_dump() for item in output_data],
                indent=4,
                ensure_ascii=False
            )

            FileUtils.write_json_to_file(json_output, "rides.json")


            print("\n✅ Saved output to rides.json\n")

        except Exception as e:
            print(f"❌ Error during batch extraction: {e}")

# ------------------------
# Script Entry Point
# ------------------------

if __name__ == "__main__":
    input_folder = sys.argv[1]
    system_prompt_file_path = sys.argv[2]

    extractor = Extractor(input_folder, system_prompt_file_path)
    extractor.run()
