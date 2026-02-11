from __future__ import annotations

import json
import os
import shutil
from typing import Dict, List, Optional, Tuple, Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.FileUtils import FileUtils

class DecisionEngine:
    """Process validated bills through decision engine"""

    def __init__(
        self, 
        model_name: str,
        temperature: float,
        output_dir: str,
        resources_dir: str,
        enable_rag: bool = False,
        policy_extractor: Optional[Any] = None
    ):
        """
        Initialize DecisionEngine with direct configuration parameters.
        
        Args:
            model_name: LLM model name to use
            temperature: Temperature for LLM
            output_dir: Directory for output files
            resources_dir: Directory containing resources
            enable_rag: Whether RAG is enabled
            policy_extractor: Optional PolicyExtractorWithRAG instance for RAG context
        """
        self.model_name = model_name
        self.temperature = temperature
        self.output_dir = output_dir
        self.resources_dir = resources_dir
        self.enable_rag = enable_rag
        self.policy_extractor = policy_extractor
        
        self.llm = ChatGroq(
            model=self.model_name,
            temperature=self.temperature,
            api_key=os.getenv("GROQ_API_KEY"),
        )

    def _prepare_groups(self, bills_map: Dict[str, List[Dict]]) -> Tuple[List[Dict], List[Dict]]:
        """Prepare grouped data for decision engine"""
        groups_data = []
        save_data = []

        for key, emp_bills in bills_map.items():
            emp_id, emp_name = key.split("_", 1)

            # Group by category
            category_groups = {}
            for b in emp_bills:
                cat = b.get("category", "unknown")
                category_groups.setdefault(cat, []).append(b)

            # Process each category
            for category, cat_bills in category_groups.items():
                valid_bills = [b for b in cat_bills if b.get("validation", {}).get("is_valid")]
                invalid_bills = [b for b in cat_bills if not b.get("validation", {}).get("is_valid")]

                # Calculate daily totals
                daily_totals = {}
                for b in valid_bills:
                    invoice_date = b.get("date")
                    if invoice_date not in daily_totals:
                        daily_totals[invoice_date] = 0
                    daily_totals[invoice_date] += float(b.get("amount", 0) or 0)

                if category == "meal" and daily_totals:
                    # One group per date for meal bills
                    for date, total in daily_totals.items():
                        groups_data.append({
                            "employee_id": emp_id,
                            "employee_name": emp_name,
                            "category": category,
                            "date": date,
                            "valid_bills": [b.get("id") for b in valid_bills if b.get("date") == date],
                            "invalid_bills": [b.get("id") for b in invalid_bills if b.get("date") == date],
                            "daily_total": total,
                            "monthly_total": None
                        })
                else:
                    # One record per month for commute/fuel
                    groups_data.append({
                        "employee_id": emp_id,
                        "employee_name": emp_name,
                        "category": category,
                        "date": None,
                        "valid_bills": [b.get("id") for b in valid_bills],
                        "invalid_bills": [b.get("id") for b in invalid_bills],
                        "daily_total": None,
                        "monthly_total": sum(float(b.get("amount", 0) or 0) for b in valid_bills)
                    })

                save_data.append({
                    "employee_id": emp_id,
                    "employee_name": emp_name,
                    "category": category,
                    "valid_files": [b.get("filename") for b in valid_bills],
                    "invalid_files": [b.get("filename") for b in invalid_bills]
                })

        return groups_data, save_data

    def run(self, bills_map: Dict[str, List[Dict]], policy: Dict) -> List[Dict]:
        """Run decision engine on all bills"""
        print("\n⚖️ Running decision engine...")

        if not bills_map:
            print("❌ No bills to process")
            return []

        groups_data, save_data = self._prepare_groups(bills_map)

        # Enhance with RAG context if available
        if self.policy_extractor and self.enable_rag:
            # Check if policy_extractor has the get_relevant_policy method
            if hasattr(self.policy_extractor, 'get_relevant_policy'):
                for group in groups_data:
                    category = group.get("category", "")
                    try:
                        rag_context = self.policy_extractor.get_relevant_policy(category)
                        if rag_context:
                            group["rag_policy_context"] = rag_context
                            print(f"   📎 Added RAG context for {category}")
                    except Exception as e:
                        print(f"   ⚠️ Failed to get RAG context for {category}: {e}")
            else:
                print("   ⚠️ Policy extractor doesn't support RAG queries")

        # Prepare prompt
        user_prompt = json.dumps({
            "policy": policy,
            "groups": groups_data
        }, indent=2)

        system_prompt = FileUtils.load_text_file("prompt/system_prompt_decision.txt")

        prompt = ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            ("human", "{user_prompt}")
        ])

        parser = StrOutputParser()
        chain = prompt | self.llm | parser

        output = chain.invoke({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        })

        print("\n📄 Decision Output:")
        print(output)

        # Copy files to valid/invalid directories
        self._copy_files(save_data)

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            print("⚠️ Could not parse decision output as JSON")
            return []

    def _copy_files(self, save_data: List[Dict]):
        """Copy files to valid/invalid directories"""
        print("\n📁 Copying files to valid/invalid directories...")
        valid_base_dir = f"{self.output_dir}/{{category}}/{self.model_name}/valid_bills"
        invalid_base_dir = f"{self.output_dir}/{{category}}/{self.model_name}/invalid_bills"
        res = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")), self.resources_dir)
        src_resources_root = f"{res}/{{category}}"
        for emp in save_data:
            emp_id = emp.get("employee_id")
            emp_name = emp.get("employee_name")
            category = emp.get("category")

            if category == "cab":
                category = "commute"

            emp_valid_dir = os.path.join(valid_base_dir.replace("{category}", category), f"{emp_id}_{emp_name}")
            emp_invalid_dir = os.path.join(invalid_base_dir.replace("{category}", category), f"{emp_id}_{emp_name}")
            os.makedirs(emp_valid_dir, exist_ok=True)
            os.makedirs(emp_invalid_dir, exist_ok=True)

            valid_files = emp.get("valid_files", [])
            invalid_files = emp.get("invalid_files", [])

            # Find source folder
            resources_src_dir = None
            src_path = src_resources_root.replace("{category}", category)

            if os.path.exists(src_path):
                for folder_name in os.listdir(src_path):
                    if folder_name.startswith(emp_id):
                        resources_src_dir = os.path.join(src_path, folder_name)
                        break

            if not resources_src_dir:
                continue

            # Copy files
            for fname in os.listdir(resources_src_dir):
                for vf in valid_files:
                    if vf and vf in fname:
                        src = os.path.join(resources_src_dir, fname)
                        dest = os.path.join(emp_valid_dir, fname)
                        shutil.copy(src, dest)

                for inf in invalid_files:
                    if inf and inf in fname:
                        src = os.path.join(resources_src_dir, fname)
                        dest = os.path.join(emp_invalid_dir, fname)
                        shutil.copy(src, dest)

            print(
                f"✅ Copied {category} files for {emp_id}_{emp_name}: {len(valid_files)} valid, {len(invalid_files)} invalid")

