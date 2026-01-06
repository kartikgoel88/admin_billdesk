import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.FileUtils import FileUtils


class PolicyExtractor:
    def __init__(self, input_pdf_path, system_prompt_path):
        self.input_pdf_path = input_pdf_path
        self.system_prompt_path = system_prompt_path
        self.model = "llama-3.3-70b-versatile"

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

        llm = ChatGroq(
            model=self.model,
            temperature=0
        )

        parser = StrOutputParser()

        chain = prompt | llm | parser

        output = chain.invoke({
            "system_prompt": system_prompt,
            "ocr_text": ocr_text
        })

        # Step 4: Save the JSON output using existing helper
        FileUtils.write_json_to_file(output, "D:/pycharm/admin_billdesk/src/output/policy.json")

        print(f"✅ Policy JSON written to policy.json from: {self.input_pdf_path}")


if __name__ == "__main__":
    pdf_path = "D:/pycharm/admin_billdesk/resources/policy/company_policy.pdf"
    system_prompt_file_path = "D:/pycharm/admin_billdesk/src/prompt/system_prompt_policy.txt"
    extractor = PolicyExtractor(pdf_path, system_prompt_file_path)
    extractor.run()
