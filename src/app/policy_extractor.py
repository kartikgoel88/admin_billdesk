import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.FileUtils import FileUtils
from commons.config_reader import config
from commons.constants import Constants as Co


class PolicyExtractor:
    def __init__(self,root_folder, input_pdf_path, system_prompt_path):
        self.input_pdf_path = input_pdf_path
        self.system_prompt_path = system_prompt_path
        self.root_folder=root_folder

    def run(self):
        # Step 1: Extract text from the PDF using existing OCR helper
        pdf_name = os.path.splitext(os.path.basename(self.input_pdf_path))[0]
        ocr_text = FileUtils.get_ocr_text_from_file(pdf_name, self.input_pdf_path)

        # Step 2: Load the policy-specific system prompt for LLM
        system_prompt = FileUtils.load_text_file(self.system_prompt_path)

        # Step 3: Call the LLM to parse the OCR text into structured JSON

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "{ocr_text}")
        ])

        model_name=config[Co.LLM][Co.MODEL]

        llm = ChatGroq(
            model=model_name,
            temperature=config[Co.LLM][Co.TEMPERATURE]
        )

        parser = StrOutputParser()

        chain = prompt | llm | parser

        output = chain.invoke({
            "system_prompt": system_prompt,
            "ocr_text": ocr_text
        })

        # Step 4: Save the JSON output using existing helper
        FileUtils.write_json_to_file(output, self.root_folder+"src/model_output/policy/"+model_name+"/policy.json")

        print(f"✅ Policy JSON written to policy.json from: {self.input_pdf_path}")


if __name__ == "__main__":
    root_folder=""
    pdf_path = root_folder+"resources/policy/company_policy.pdf"
    system_prompt_file_path = root_folder+"src/prompt/system_prompt_policy.txt"
    extractor = PolicyExtractor(root_folder,pdf_path, system_prompt_file_path)
    extractor.run()
