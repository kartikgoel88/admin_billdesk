"""
BillDesk - Unified Invoice Processing Application

This application processes employee expense invoices (commute and meal),
validates them, extracts policies, and runs them through a decision engine.

Usage:
    python src/app.py --resources-dir resources --enable-rag
    python src/app.py --employee IIIPL-1000_naveen_oct_amex --category commute
"""

import os
import sys
import json
import argparse
import shutil
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.constants import Constants as Co
from commons.FileUtils import FileUtils
from commons.config_reader import config

# Reuse existing extractors
from app.commute_invoice_extractor import CommuteExtractor
from app.meal_invoice_extractor import MealExtractor
from app.policy_extractor import PolicyExtractor as BasePolicyExtractor
from app.decision_engine import DecisionEngine  # Import DecisionEngine from separate file


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class AppConfig:
    """Application configuration loaded from config.yaml"""
    resources_dir: str ="resources"
    output_dir: str = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),"src/model_output")
    model_name: str = field(default_factory=lambda: config[Co.LLM][Co.MODEL])
    temperature: float = field(default_factory=lambda: config[Co.LLM][Co.TEMPERATURE])
    enable_rag: bool = field(default_factory=lambda: config.get("rag", {}).get("enabled", False))
    rag_chunk_size: int = field(default_factory=lambda: config.get("rag", {}).get("chunk_size", 500))
    rag_chunk_overlap: int = field(default_factory=lambda: config.get("rag", {}).get("chunk_overlap", 50))
    rag_top_k: int = field(default_factory=lambda: config.get("rag", {}).get("top_k", 5))


# =============================================================================
# RAG Policy Extractor (Optional Enhancement)
# =============================================================================

class RAGPolicyExtractor:
    """
    RAG-based policy extraction using vector embeddings.
    Provides semantic search over policy documents.
    """

    def __init__(self, policy_text: str, app_config: AppConfig):
        self.policy_text = policy_text
        self.config = app_config
        self.vector_store = None
        self.embeddings = None

    def _init_rag(self):
        """Initialize RAG components lazily"""
        try:
            from langchain_community.vectorstores import FAISS
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.rag_chunk_size,
                chunk_overlap=self.config.rag_chunk_overlap
            )
            chunks = text_splitter.split_text(self.policy_text)

            # Create embeddings and vector store
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.vector_store = FAISS.from_texts(chunks, self.embeddings)

            print(f"✅ RAG initialized with {len(chunks)} policy chunks")
            return True

        except ImportError as e:
            print(f"⚠️ RAG dependencies not installed: {e}")
            print("   Install with: pip install faiss-cpu sentence-transformers langchain-community")
            return False
        except Exception as e:
            print(f"⚠️ RAG initialization failed: {e}")
            return False

    def query_policy(self, query: str) -> str:
        """Query policy using RAG retrieval"""
        if self.vector_store is None:
            if not self._init_rag():
                return ""

        docs = self.vector_store.similarity_search(query, k=self.config.rag_top_k)
        return "\n\n".join([doc.page_content for doc in docs])

    def get_relevant_policy_for_category(self, category: str) -> str:
        """Get policy sections relevant to a specific expense category"""
        queries = {
            "commute": "cab taxi commute transportation travel allowance limit policy",
            "cab": "cab taxi commute transportation travel allowance limit policy",
            "meal": "meal food allowance daily limit lunch dinner policy",
            "fuel": "fuel petrol diesel reimbursement vehicle policy"
        }
        query = queries.get(category, category + " policy allowance limit")
        return self.query_policy(query)


# =============================================================================
# Enhanced Policy Extractor with RAG Support
# =============================================================================

class PolicyExtractorWithRAG:
    """
    Wrapper around BasePolicyExtractor that adds RAG capabilities.
    """

    def __init__(self, app_config: AppConfig):
        self.config = app_config
        self.rag_extractor = None
        self.policy = None

        if self.config.enable_rag:
            print("🔍 RAG mode enabled for policy extraction")

    def extract(self, policy_path: str, system_prompt_path: str) -> Dict:
        """Extract policy from PDF using existing PolicyExtractor"""
        print(f"\n📋 Extracting policy from: {policy_path}")
        root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        # Use the existing PolicyExtractor class
        print("root_folder:", root_folder)
        extractor = BasePolicyExtractor(
            root_folder=root_folder + "/",
            input_pdf_path=os.path.join(root_folder, policy_path),
            system_prompt_path=os.path.join(root_folder, system_prompt_path)
        )

        self.policy = extractor.run(save_to_file=True)

        # Initialize RAG if enabled
        if self.config.enable_rag and extractor.get_policy_text():
            self.rag_extractor = RAGPolicyExtractor(
                extractor.get_policy_text(),
                self.config
            )

        return self.policy

    def get_relevant_policy(self, category: str) -> Optional[str]:
        """Get relevant policy section using RAG (if enabled)"""
        if self.rag_extractor and self.config.enable_rag:
            return self.rag_extractor.get_relevant_policy_for_category(category)
        return None


# =============================================================================
# Main Application
# =============================================================================

class BillDeskApp:
    """Main application orchestrator - reuses existing extractors"""

    def __init__(self, args):
        self.args = args
        self.config = AppConfig(
            resources_dir=args.resources_dir,
            enable_rag=args.enable_rag if hasattr(args, 'enable_rag') else False
        )

        self.policy_extractor = PolicyExtractorWithRAG(self.config)
        self.decision_engine = None  # Initialized after policy extraction

        self.all_bills = {}  # key: "emp_id_emp_name", value: list of bills

    def discover_employees(self) -> Dict[str, Dict[str, str]]:
        """Discover all employee folders in resources"""
        employees = {}

        for category in ["commute", "meal"]:
            category_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),self.config.resources_dir, category)
            if not os.path.exists(category_path):
                continue

            for folder_name in os.listdir(category_path):
                folder_path = os.path.join(category_path, folder_name)
                if not os.path.isdir(folder_path):
                    continue

                # Parse employee info from folder name
                parts = folder_name.split("_")
                if len(parts) >= 4:
                    emp_id = parts[0]
                    emp_name = parts[1]
                    key = f"{emp_id}_{emp_name}"

                    if key not in employees:
                        employees[key] = {"commute": None, "meal": None}

                    employees[key][category] = folder_path

        return employees

    def process_employee(self, emp_key: str, folders: Dict[str, str]) -> List[Dict]:
        """
        Process all invoices for a single employee.
        Reuses CommuteExtractor and MealExtractor classes.
        """
        print(f"\n{'=' * 60}")
        print(f"👤 Processing employee: {emp_key}")
        print(f"{'=' * 60}")

        results = []

        # Process commute invoices using existing CommuteExtractor
        if folders.get("commute") and (not self.args.category or self.args.category == "commute"):
            print(f"\n🚗 Processing commute invoices from: {folders['commute']}")

            commute_extractor = CommuteExtractor(
                input_folder=folders["commute"],
                system_prompt_path=os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),"src/prompt/system_prompt_cab.txt")
            )
            commute_results = commute_extractor.run(save_to_file=True)

            if commute_results:
                results.extend(commute_results)
                print(f"✅ Extracted {len(commute_results)} commute invoices")

        # Process meal invoices using existing MealExtractor
        if folders.get("meal") and (not self.args.category or self.args.category == "meal"):
            print(f"\n🍽️ Processing meal invoices from: {folders['meal']}")

            meal_extractor = MealExtractor(
                input_folder=folders["meal"],
                system_prompt_path=os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),"src/prompt/system_meal_prompt.txt")
            )
            meal_results = meal_extractor.run(save_to_file=True)

            if meal_results:
                results.extend(meal_results)
                print(f"✅ Extracted {len(meal_results)} meal invoices")

        return results

    def run(self):
        """Run the complete pipeline"""
        print("\n" + "=" * 60)
        print("🏢 BillDesk - Invoice Processing System")
        print("=" * 60)
        print(f"📁 Resources: {self.config.resources_dir}")
        print(f"🤖 Model: {self.config.model_name}")
        print(f"🔍 RAG Enabled: {self.config.enable_rag}")
        print("=" * 60)

        # Step 1: Extract policy using existing PolicyExtractor (wrapped with RAG support)
        policy_path = os.path.join(self.config.resources_dir, "company_policy.pdf")
        if not os.path.exists(policy_path):
            policy_path = os.path.join(self.config.resources_dir, "policy", "company_policy.pdf")

        policy_prompt_path = "src/prompt/system_prompt_policy.txt"
        policy = self.policy_extractor.extract(policy_path, policy_prompt_path)

        if not policy:
            print("❌ Failed to extract policy. Exiting.")
            return

        # Initialize decision engine with direct parameters from separate module
        # Pass policy_extractor only if RAG is enabled
        self.decision_engine = DecisionEngine(
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            output_dir=self.config.output_dir,
            resources_dir=self.config.resources_dir,
            enable_rag=self.config.enable_rag,
            policy_extractor=self.policy_extractor if self.config.enable_rag else None
        )

        # Step 2: Discover and process employees
        if self.args.employee:
            # Process specific employee
            employees = self.discover_employees()
            matching = {k: v for k, v in employees.items() if self.args.employee.lower() in k.lower()}

            if not matching:
                print(f"❌ No employee found matching: {self.args.employee}")
                return

            employees = matching
        else:
            # Process all employees
            employees = self.discover_employees()

        print(f"\n📊 Found {len(employees)} employee(s) to process")

        # Step 3: Process each employee using reused extractors
        for emp_key, folders in employees.items():
            results = self.process_employee(emp_key, folders)

            if results:
                self.all_bills[emp_key] = results

        # Step 4: Run decision engine
        if self.all_bills and not self.args.skip_decision:
            decisions = self.decision_engine.run(self.all_bills, policy)

            # Save decisions
            if decisions:
                decisions_path = f"{self.config.output_dir}/decisions/{self.config.model_name}/decisions.json"
                os.makedirs(os.path.dirname(decisions_path), exist_ok=True)
                with open(decisions_path, "w", encoding="utf-8") as f:
                    json.dump(decisions, f, indent=2)
                print(f"\n💾 Decisions saved to: {decisions_path}")

        print("\n" + "=" * 60)
        print("✅ Processing complete!")
        print("=" * 60)


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BillDesk - Unified Invoice Processing System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all employees
  python src/app.py
  
  # Process with RAG enabled for policy
  python src/app.py --enable-rag
  
  # Process specific employee
  python src/app.py --employee IIIPL-1000
  
  # Process only commute invoices
  python src/app.py --category commute
  
  # Custom resources directory
  python src/app.py --resources-dir /path/to/resources
        """
    )

    parser.add_argument(
        "--resources-dir",
        default="resources",
        help="Path to resources directory (default: resources)"
    )

    parser.add_argument(
        "--employee",
        help="Process specific employee (partial match supported)"
    )

    parser.add_argument(
        "--category",
        choices=["commute", "meal"],
        help="Process only specific category"
    )

    parser.add_argument(
        "--enable-rag",
        action="store_true",
        help="Enable RAG for policy extraction (requires additional dependencies)"
    )

    parser.add_argument(
        "--skip-decision",
        action="store_true",
        help="Skip decision engine (only extract and validate)"
    )

    args = parser.parse_args()
    # Run application
    args.resources_dir=os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),"resources")
    args.employee = "IIIPL-3185_smitha"
    #args.category = "meal"
    #args.employee = "IIIPL-5653_ashwini"
    #args.category = "commute"
    app = BillDeskApp(args)
    app.run()


if __name__ == "__main__":
    main()
