import json
import sys
import os


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.validate_commute_fields import ValidateCommuteFeilds

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from commons.constants import Constants as Co
from commons.config_reader import config
from commons.FileUtils import FileUtils
from entity.meal_extraction_schema import MealExtraction, MealExtractionList

## Run command : python src/bill_extractor_tesseract.py D:/pycharm/admin_billdesk/resources/IIIPL-1011_smitha_oct_tesco D:\pycharm\admin_billdesk\src\prompt\system_prompt_cab.txt
## export api key via PS :$env:GROQ_API_KEY="API_KEY"

class MealExtractor:
    def __init__(self,input_folder,system_prompt_path):
        self.input_folder = input_folder
        self.system_prompt_path = system_prompt_path
        self.output_folder = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),"src/model_output/meal/" + config[Co.LLM][Co.MODEL] + "/")
        self.employee_meta = FileUtils.extract_info_from_foldername(self.input_folder)
        self.category = {"category": "meal"}
        # Load receipts from folder
        # Should return a list of:  {"filename": "...", "text": "..."}
        self.receipts = FileUtils.process_folder(self.input_folder)
        print("\n[Receipts loaded]")
        #print(self.receipts)

        self.ocr_lookup = {}

        for rec in self.receipts:
            for filename, ocr_text in rec.items():
                self.ocr_lookup[filename] = ocr_text

        # Load system prompt
        self.system_prompt = FileUtils.load_text_file(self.system_prompt_path)
        print("\n[Loaded System Prompt]")
        #print(self.system_prompt)

        # Choose model and temperature
        self.llm = ChatGroq(
            model=config[Co.LLM][Co.MODEL],
            temperature=config[Co.LLM][Co.TEMPERATURE],
            api_key=os.getenv("GROQ_API_KEY"),
        )

        # Pydantic parser ensures consistency and zero hallucination
        self.parser = PydanticOutputParser(pydantic_object=MealExtractionList)

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
    def run(self, save_to_file: bool = True):
        """
        Run extraction and validation.
        
        Args:
            save_to_file: If True, saves results to output file. Default True.
            
        Returns:
            List of validated results, or empty list on error.
        """
        print("\n[Starting Extraction]\n")

        try:
            result: MealExtractionList = self.chain.invoke({
                "system_prompt": self.system_prompt,
                "receipts_json": self.receipts,
                "format_instructions": self.parser.get_format_instructions()
            })

            output_data = result.root  # List[MealExtraction]
            print("\n✔ Batch Extracted Successfully")
            print(output_data)

            validated_results = []

            for item in output_data:
                base = item.model_dump()

                filename = base.get("filename")
                ocr_text = self.ocr_lookup.get(filename)
                enriched = {
                    **base,
                    "ocr": ocr_text,
                    **self.employee_meta.to_dict(),
                    **self.category
                }


                validation = ValidateCommuteFeilds.validate_meal(enriched)
                enriched["validation"] = validation

                validated_results.append(enriched)

            if save_to_file:
                json_output = json.dumps(
                    validated_results,
                    indent=4,
                    ensure_ascii=False
                )
                FileUtils.write_json_to_file(json_output, self.output_folder + self.input_folder.split("/")[-1])
            
            return validated_results
            
        except Exception as e:
            print(f"❌ Error during batch extraction: {e}")
            return []

if __name__ == "__main__":
    input_folder = sys.argv[1]
    system_prompt_file_path = sys.argv[2]
    print(system_prompt_file_path)
    extractor = MealExtractor(input_folder, system_prompt_file_path)
    extractor.run()
