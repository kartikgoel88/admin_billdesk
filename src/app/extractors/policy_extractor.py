"""Policy extraction from PDF. Implements PolicyExtractor protocol."""

import json
import os

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from commons.file_utils import FileUtils
from commons.config import config
from commons.constants import Constants as Co
from commons.llm import get_llm, get_llm_model_name

from app.extractors._paths import get_output_base, project_path


class PolicyExtractor:
    """Extract structured policy from a policy PDF."""

    def __init__(
        self,
        root_folder: str = "",
        input_pdf_path: str | None = None,
        system_prompt_path: str | None = None,
    ):
        self.root_folder = root_folder.rstrip("/") + "/" if root_folder else ""
        self.input_pdf_path = input_pdf_path or project_path("resources", "policy", "company_policy.pdf")
        self.system_prompt_path = system_prompt_path or project_path(
            "src", "prompt", "system_prompt_policy.txt"
        )
        self.model_name = get_llm_model_name()
        self.policy_text: str | None = None

    def run(self, save_to_file: bool = True) -> dict | None:
        pdf_name = os.path.splitext(os.path.basename(self.input_pdf_path))[0]
        ocr_text = FileUtils.get_ocr_text_from_file(pdf_name, self.input_pdf_path)
        self.policy_text = ocr_text.get(pdf_name, "")

        system_prompt = FileUtils.load_text_file(self.system_prompt_path)
        print("\n[Loaded System Prompt]")

        llm = get_llm(http_client=httpx.Client(verify=False))
        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "{ocr_text}"),
        ])
        chain = prompt | llm | StrOutputParser()
        output = chain.invoke({"system_prompt": system_prompt, "ocr_text": ocr_text})

        print("\n📄 Policy Output:")
        print(output)

        base_parts = get_output_base().strip("/").split("/")
        output_path = project_path(*(base_parts + ["policy", self.model_name, "policy.json"]))
        if save_to_file:
            FileUtils.write_json_to_file(output, output_path)
            print(f"✅ Policy JSON written from: {self.input_pdf_path}")

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            print("⚠️ Could not parse policy output as JSON")
            return None

    def get_policy_text(self) -> str | None:
        return self.policy_text
