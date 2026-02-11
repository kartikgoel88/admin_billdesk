import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from openai import http_client
import httpx
from commons.FileUtils import FileUtils
from commons.config_reader import config
from commons.constants import Constants as Co


class PolicyExtractor:
    def __init__(self, root_folder, input_pdf_path, system_prompt_path):
        self.input_pdf_path = input_pdf_path
        self.system_prompt_path = system_prompt_path
        self.root_folder = root_folder
        self.model_name = config[Co.LLM][Co.MODEL]
        self.policy_text = None  # Store raw OCR text for RAG

    def run(self, save_to_file: bool = True):
        """
        Run policy extraction.
        
        Args:
            save_to_file: If True, saves results to output file. Default True.
            
        Returns:
            Parsed policy as dictionary, or None on error.
        """
        # Step 1: Extract text from the PDF using existing OCR helper
        pdf_name = os.path.splitext(os.path.basename(self.input_pdf_path))[0]
        ocr_text = FileUtils.get_ocr_text_from_file(pdf_name, self.input_pdf_path)
        self.policy_text = ocr_text.get(pdf_name, "")  # Store for RAG usage

        # Step 2: Load the policy-specific system prompt for LLM
        system_prompt = FileUtils.load_text_file(self.system_prompt_path)
        print("\n[Loaded System Prompt]")
        #print(self.system_prompt_path)
        #print(system_prompt)
        # Step 3: Call the LLM to parse the OCR text into structured JSON
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "{ocr_text}")
        ])

        llm = ChatGroq(
            model=self.model_name,
            temperature=config[Co.LLM][Co.TEMPERATURE],
            http_client = httpx.Client(verify=False),
            api_key=os.getenv("GROQ_API_KEY"),
        )

        parser = StrOutputParser()
        chain = prompt | llm | parser

        output = chain.invoke({
            "system_prompt": system_prompt,
            "ocr_text": ocr_text
        })

        print("\n�� Policy Output:")
        print(output)
        print(self.root_folder)
        # Step 4: Save the JSON output using existing helper
        output_path = self.root_folder + "src/model_output/policy/" + self.model_name + "/policy.json"
        if save_to_file:
            FileUtils.write_json_to_file(output, output_path)
            print(f"✅ Policy JSON written to policy.json from: {self.input_pdf_path}")

        # Return parsed policy
        try:
            import json
            return json.loads(output)
        except json.JSONDecodeError:
            print("⚠️ Could not parse policy output as JSON")
            return None
    
    def get_policy_text(self):
        """Get raw policy text for RAG usage"""
        return self.policy_text


if __name__ == "__main__":
    root_folder=""
    pdf_path = root_folder+"resources/policy/company_policy.pdf"
    system_prompt_file_path = root_folder+"src/prompt/system_prompt_policy.txt"
    extractor = PolicyExtractor(root_folder,pdf_path, system_prompt_file_path)
    extractor.run()
