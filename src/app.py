"""
BillDesk - Unified Invoice Processing Application

This application processes employee expense invoices (commute, meal, fuel),
validates them, extracts policies, and runs them through a decision engine.

Modes:
  - Full flow (default): policy extraction → OCR + extraction → validation → decision engine.
  - --skip-decision: run everything except the decision engine.
  - --decision-only: load policy and validated bills from output_dir and run only the decision engine.

By default reads from the standardized processed folder (paths.processed_dir,
e.g. resources/processed_inputs). Use --resources-dir to point at raw resources.

Usage:
    python src/app.py
    python src/app.py --resources-dir resources/processed_inputs
    python src/app.py --employee IIIPL-1000_naveen_oct_amex --category commute
    python src/app.py --decision-only
"""

import csv
import os
import re
import sys
import json
import argparse
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.constants import Constants as Co
from commons.FileUtils import FileUtils
from commons.config import config
from commons.llm import get_llm_model_name

# For decision-only: resolve output path relative to project
def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _output_dir_absolute(output_dir: str) -> str:
    if os.path.isabs(output_dir):
        return output_dir
    return os.path.join(_project_root(), output_dir)

# Extendible extractors and decision engine
from app.extractors import CommuteExtractor, MealExtractor, get_extractor
from app.extractors.policy_extractor import PolicyExtractor as BasePolicyExtractor
from app.decision import DecisionEngine
from app.org_api import get_org_client


# =============================================================================
# Configuration
# =============================================================================

def _default_resources_dir() -> str:
    """Default: standardized processed inputs (processed_dir), else raw resources_dir."""
    paths = config.get("paths") or {}
    return paths.get("processed_dir") or paths.get("resources_dir", "resources")


@dataclass
class AppConfig:
    """Application configuration loaded from config.yaml"""
    resources_dir: str = field(default_factory=_default_resources_dir)
    output_dir: str = field(default_factory=lambda: (config.get("paths") or {}).get("output_dir", "resources/model_output"))
    model_name: str = field(default_factory=get_llm_model_name)
    temperature: float = field(default_factory=lambda: (config.get(Co.LLM) or {}).get(Co.TEMPERATURE, 0))
    enable_rag: bool = field(default_factory=lambda: config.get("rag", {}).get("enabled", False))
    rag_chunk_size: int = field(default_factory=lambda: config.get("rag", {}).get("chunk_size", 500))
    rag_chunk_overlap: int = field(default_factory=lambda: config.get("rag", {}).get("chunk_overlap", 50))
    rag_top_k: int = field(default_factory=lambda: config.get("rag", {}).get("top_k", 5))
    rag_embedding_model: str = field(default_factory=lambda: config.get("rag", {}).get("embedding_model", "sentence-transformers/all-MiniLM-L6-v2"))


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
                model_name=self.config.rag_embedding_model
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
        """Extract policy from PDF using existing PolicyExtractor (policy_path is under app resources_dir)."""
        print(f"\n📋 Extracting policy from: {policy_path}")
        root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        extractor = BasePolicyExtractor(
            root_folder=root_folder + "/",
            input_pdf_path=policy_path if os.path.isabs(policy_path) else os.path.join(root_folder, policy_path),
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
        self.employee_org_data = {}  # key: "emp_id_emp_name", value: org API response or None (optional enrichment)
        self.policy = None  # extracted policy JSON (used for validation limits and decision engine)

    def discover_employees(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Discover all employee folders in resources. Supports multiple months per employee:
        folder names {emp_id}_{emp_name}_{month}_{client} or {emp_id}_{emp_name}_{month}_{year}_{client}.
        emp_name is normalized (concatenated without spaces) so 'John', 'John Doe', 'John  Doe' match the same employee.
        Returns dict: emp_key -> { category -> [folder_path, ...] } (all months collected).
        """
        employees: Dict[str, Dict[str, List[str]]] = {}

        for category in ["commute", "meal", "fuel"]:
            category_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), self.config.resources_dir, category)
            if not os.path.exists(category_path):
                continue

            for folder_name in os.listdir(category_path):
                folder_path = os.path.join(category_path, folder_name)
                if not os.path.isdir(folder_path):
                    continue

                parts = folder_name.split("_")
                if len(parts) >= 4:
                    emp_id = parts[0]
                    emp_name_raw = parts[1]
                    name_part = re.sub(r"\s+", "", (emp_name_raw or "").strip()).lower()
                    key = f"{emp_id}_{name_part}"

                    if key not in employees:
                        employees[key] = {"commute": [], "meal": [], "fuel": []}
                    employees[key][category].append(folder_path)

        return employees

    def process_employee(self, emp_key: str, folders: Dict[str, List[str]]) -> List[Dict]:
        """
        Process all invoices for a single employee across all month folders.
        folders: category -> list of folder paths (one per month). Uses extractor registry.
        """
        print(f"\n{'=' * 60}")
        print(f"👤 Processing employee: {emp_key}")
        print(f"{'=' * 60}")

        results = []
        prompt_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "src", "prompt")
        category_to_prompt = {
            "commute": os.path.join(prompt_dir, "system_prompt_cab.txt"),
            "meal": os.path.join(prompt_dir, "system_meal_prompt.txt"),
            "fuel": os.path.join(prompt_dir, "system_prompt_fuel.txt"),
        }
        category_labels = {"commute": "🚗 commute", "meal": "🍽️ meal", "fuel": "⛽ fuel"}

        for category in ["commute", "meal", "fuel"]:
            folder_list = folders.get(category) or []
            if not folder_list or (self.args.category and self.args.category != category):
                continue
            for folder_path in folder_list:
                extractor = get_extractor(
                    category,
                    input_folder=folder_path,
                    system_prompt_path=category_to_prompt.get(category),
                    policy=self.policy,
                )
                if not extractor:
                    continue
                print(f"\n{category_labels.get(category, category)} invoices from: {folder_path}")
                category_results = extractor.run(save_to_file=True)
                if category_results:
                    results.extend(category_results)
                    print(f"✅ Extracted {len(category_results)} {category} invoices")

        return results

    def _emp_key_from_folder_name(self, folder_name: str) -> Optional[str]:
        """Derive emp_key from extraction output folder name (e.g. IIIPL-1000_naveen_oct_amex -> IIIPL-1000_naveen)."""
        parts = folder_name.split("_")
        if len(parts) < 4:
            return None
        emp_id = parts[0]
        emp_name_raw = parts[1]
        name_part = re.sub(r"\s+", "", (emp_name_raw or "").strip()).lower()
        return f"{emp_id}_{name_part}"

    def _load_policy_from_output(self) -> Optional[Dict]:
        """Load policy JSON from existing extraction output (policy/{model_name}/policy.json)."""
        base = _output_dir_absolute(self.config.output_dir)
        policy_path = os.path.join(base, "policy", self.config.model_name, "policy.json")
        if not os.path.isfile(policy_path):
            print(f"❌ Policy file not found: {policy_path}")
            return None
        try:
            return FileUtils.load_json_from_file(policy_path)
        except Exception as e:
            print(f"❌ Failed to load policy: {e}")
            return None

    def _load_bills_from_output(self) -> Dict[str, List[Dict]]:
        """Load all bills from existing extraction output (category/model_name/folder_name JSON files)."""
        base = _output_dir_absolute(self.config.output_dir)
        all_bills: Dict[str, List[Dict]] = {}
        for category in ["commute", "meal", "fuel"]:
            category_dir = os.path.join(base, category, self.config.model_name)
            if not os.path.isdir(category_dir):
                continue
            for name in os.listdir(category_dir):
                path = os.path.join(category_dir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    data = FileUtils.load_json_from_file(path)
                except Exception:
                    continue
                if not isinstance(data, list):
                    continue
                emp_key = self._emp_key_from_folder_name(name)
                if not emp_key:
                    continue
                if emp_key not in all_bills:
                    all_bills[emp_key] = []
                for b in data:
                    if isinstance(b, dict) and b.get("category") is None:
                        b = {**b, "category": category}
                    all_bills[emp_key].append(b)
        return all_bills

    def _write_decisions(self, decisions: List[Dict]) -> None:
        """Write decision outputs (audit JSON, summary, README, org data) to output_dir."""
        base = _output_dir_absolute(self.config.output_dir)
        decisions_dir = os.path.join(base, "decisions", self.config.model_name)
        os.makedirs(decisions_dir, exist_ok=True)
        if not decisions:
            return
        grouped = {}
        for d in decisions:
            name = f"{d.get('employee_id', '')}_{d.get('employee_name', '')}"
            cat = d.get("category", "unknown")
            month = d.get("month", "unknown")
            grouped.setdefault(name, {}).setdefault(cat, {}).setdefault(month, []).append(d)
        _audit = {
            "_meta": {
                "purpose": "Audit trail: full decision detail for traceability and debugging",
                "model": self.config.model_name,
                "generated_at": datetime.now().isoformat(),
            },
            "decisions": grouped,
        }
        decisions_path = os.path.join(base, "decisions", self.config.model_name, "decisions.json")
        with open(decisions_path, "w", encoding="utf-8") as f:
            json.dump(_audit, f, indent=2)
        print(f"\n💾 Decisions (audit) saved to: {decisions_path} (full detail for tech/audit)")

        def _normalize_reason(reason: str) -> str:
            if not reason:
                return "Other"
            return re.sub(r"\s*\(\d+%\)\s*$", "", str(reason).strip()) or "Other"
        summary = {}
        for name, by_cat in grouped.items():
            summary[name] = {}
            for cat, by_month in by_cat.items():
                summary[name][cat] = {}
                for month, items in by_month.items():
                    total_claimed = sum(float(d.get("claimed_amount") or 0) for d in items)
                    total_approved = sum(float(d.get("approved_amount") or 0) for d in items)
                    any_reject = any((d.get("decision") or "").upper() == "REJECT" for d in items)
                    currency = (items[0].get("currency") or "INR") if items else "INR"
                    valid_count = sum(len(d.get("valid_bill_ids") or []) for d in items)
                    invalid_count = sum(len(d.get("invalid_bill_ids") or []) for d in items)
                    reason_counts = {}
                    for d in items:
                        for es in (d.get("error_summary") or []):
                            r = _normalize_reason(es.get("reason", ""))
                            reason_counts[r] = reason_counts.get(r, 0) + (es.get("count") or len(es.get("bill_ids") or []))
                    invalid_reasons = [{"reason": r, "count": c} for r, c in sorted(reason_counts.items())] if reason_counts else []
                    entry = {
                        "decision": "REJECT" if any_reject else "APPROVE",
                        "claimed_amount": round(total_claimed, 2),
                        "approved_amount": round(total_approved, 2),
                        "currency": currency,
                        "valid_bill_count": valid_count,
                        "invalid_bill_count": invalid_count,
                        "period_count": len(items),
                    }
                    if invalid_reasons:
                        entry["invalid_reasons"] = invalid_reasons
                    summary[name][cat][month] = entry
        summary_path = os.path.join(base, "decisions", self.config.model_name, "decisions_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"💾 Admin summary saved to: {summary_path} (high-level for admin team)")

        # Final CSV: emp id, emp name, category, month, amount approved, bill counts, consolidated invalid reasons
        def _consolidate_invalid_reasons(d: dict) -> str:
            parts = []
            for es in d.get("error_summary") or []:
                reason = (es.get("reason") or "").strip() or "Other"
                count = es.get("count") or len(es.get("bill_ids") or [])
                if count > 1:
                    parts.append(f"{reason} ({count})")
                else:
                    parts.append(reason)
            return "; ".join(parts)

        csv_path = os.path.join(base, "decisions", self.config.model_name, "decisions_final.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "emp_id", "emp_name", "category", "month", "bill_date", "amount_approved",
                "total_bills", "valid_bills", "invalid_bills", "invalid_reasons",
            ])
            for d in decisions:
                valid_ids = d.get("valid_bill_ids") or []
                invalid_ids = d.get("invalid_bill_ids") or []
                total = len(valid_ids) + len(invalid_ids)
                bill_date = d.get("date") or ""
                writer.writerow([
                    d.get("employee_id", ""),
                    d.get("employee_name", ""),
                    d.get("category", ""),
                    d.get("month", ""),
                    bill_date,
                    round(float(d.get("approved_amount") or 0), 2),
                    total,
                    len(valid_ids),
                    len(invalid_ids),
                    _consolidate_invalid_reasons(d),
                ])
        print(f"💾 Final CSV saved to: {csv_path} (emp, category, month, amount approved, bill counts, invalid reasons)")

        readme_path = os.path.join(decisions_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Decision outputs\n\n")
            f.write("- **decisions_final.csv** – Final flat list: emp_id, emp_name, category, month, bill_date, amount_approved, total_bills, valid_bills, invalid_bills, invalid_reasons (one row per employee/category/month or per day for meal).\n\n")
            f.write("- **decisions_summary.json** – For **admin**: high-level view (approve/reject, amounts, valid/invalid counts, reason labels). No bill IDs.\n\n")
            f.write("- **decisions.json** – For **tech/audit**: full detail (bill IDs, per-bill reasons, error_summary with IDs) and `_meta` (model, generated_at) for traceability.\n")
        if self.employee_org_data:
            org_path = os.path.join(base, "decisions", self.config.model_name, "employee_org_data.json")
            with open(org_path, "w", encoding="utf-8") as f:
                json.dump(self.employee_org_data, f, indent=2)
            print(f"💾 Employee org data (enrichment) saved to: {org_path}")

    def _run_decision_engine_per_category(self, policy: Dict) -> List[Dict]:
        """Run decision engine separately for commute, meal, and fuel so decision data are not mixed."""
        all_decisions: List[Dict] = []
        org_data = self.employee_org_data if self.employee_org_data else None
        for category in ["commute", "meal", "fuel"]:
            bills_for_cat = {
                k: [b for b in v if (b.get("category") or "").strip().lower() == category]
                for k, v in self.all_bills.items()
            }
            bills_for_cat = {k: v for k, v in bills_for_cat.items() if v}
            if not bills_for_cat:
                continue
            decisions_cat = self.decision_engine.run(
                bills_for_cat,
                policy,
                employee_org_data=org_data,
                category_filter=category,
            )
            all_decisions.extend(decisions_cat)
        return all_decisions

    def run(self):
        """Run the complete pipeline, or only the decision engine when --decision-only."""
        print("\n" + "=" * 60)
        print("🏢 BillDesk - Invoice Processing System")
        print("=" * 60)
        print(f"📁 Resources: {self.config.resources_dir}")
        print(f"🤖 Model: {self.config.model_name}")
        print(f"🔍 RAG Enabled: {self.config.enable_rag}")
        if getattr(self.args, "decision_only", False):
            print("⚖️ Mode: decision-only (using existing OCR/validation output)")
        print("=" * 60)

        project_root = _project_root()

        if getattr(self.args, "decision_only", False):
            # Decision-only: load policy and bills from previous extraction/validation output
            self.policy = self._load_policy_from_output()
            if not self.policy:
                return
            self.all_bills = self._load_bills_from_output()
            if not self.all_bills:
                print("❌ No bills found in output. Run full flow first (without --decision-only).")
                return
            print(f"📂 Loaded policy and {sum(len(v) for v in self.all_bills.values())} bills for {len(self.all_bills)} employee(s)")
            self.decision_engine = DecisionEngine(
                model_name=self.config.model_name,
                temperature=self.config.temperature,
                output_dir=self.config.output_dir,
                resources_dir=self.config.resources_dir,
                enable_rag=self.config.enable_rag,
                policy_extractor=self.policy_extractor if self.config.enable_rag else None
            )
            org_client = get_org_client()
            if org_client:
                for emp_key in self.all_bills:
                    emp_id = emp_key.split("_", 1)[0]
                    try:
                        self.employee_org_data[emp_key] = org_client.get_employee_details(emp_id)
                    except Exception:
                        self.employee_org_data[emp_key] = None
            # Run decision engine per category (commute, meal, fuel separately)
            decisions = self._run_decision_engine_per_category(self.policy)
            self._write_decisions(decisions)
            print("\n" + "=" * 60)
            print("✅ Decision-only run complete!")
            print("=" * 60)
            return

        # Step 1: Extract policy — look under resources_dir first, then fall back to raw resources (policy often lives there)
        raw_resources = (config.get("paths") or {}).get("resources_dir", "resources")
        for base in (self.config.resources_dir, raw_resources):
            policy_path = os.path.join(project_root, base, "company_policy.pdf")
            if os.path.exists(policy_path):
                break
            policy_path = os.path.join(project_root, base, "policy", "company_policy.pdf")
            if os.path.exists(policy_path):
                break
        else:
            policy_path = os.path.join(project_root, self.config.resources_dir, "policy", "company_policy.pdf")

        policy_prompt_path = "src/prompt/system_prompt_policy.txt"
        self.policy = self.policy_extractor.extract(policy_path, policy_prompt_path)

        if not self.policy:
            print("❌ Failed to extract policy. Exiting.")
            return
        policy = self.policy  # alias for decision engine call below

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
            # Process specific employee (match on full key or name; keys are e.g. IIIPL-3185_smitha or SMITHA_smitha from folder names)
            employees = self.discover_employees()
            needle = self.args.employee.lower()
            matching = {k: v for k, v in employees.items() if needle in k.lower()}
            # If no match, try matching by name only (e.g. "smitha" matches SMITHA_smitha when folders use name as id)
            if not matching and "_" in self.args.employee:
                name_part = self.args.employee.rsplit("_", 1)[-1].lower()
                matching = {k: v for k, v in employees.items() if name_part in k.lower()}
            if not matching:
                available = ", ".join(sorted(employees.keys())) if employees else "(none)"
                print(f"❌ No employee found matching: {self.args.employee}")
                print(f"   Available keys (from folder names under {self.config.resources_dir}/commute|meal|fuel): {available}")
                print(f"   Tip: use --employee <key> or just the name, e.g. --employee smitha")
                return

            employees = matching
        else:
            # Process all employees
            employees = self.discover_employees()

        print(f"\n📊 Found {len(employees)} employee(s) to process")

        # Optional: fetch org data (employee details, leave, manager) for enrichment; not mandatory
        org_client = get_org_client()
        if org_client:
            print("📡 Org API enabled: fetching employee/leave/manager data for enrichment")
        for emp_key, folders in employees.items():
            if org_client:
                emp_id = emp_key.split("_", 1)[0]
                try:
                    self.employee_org_data[emp_key] = org_client.get_employee_details(emp_id)
                except Exception:
                    self.employee_org_data[emp_key] = None

            results = self.process_employee(emp_key, folders)
            if results:
                self.all_bills[emp_key] = results

        # Step 4: Run decision engine per category (commute, meal, fuel separately)
        if self.all_bills and not self.args.skip_decision:
            decisions = self._run_decision_engine_per_category(policy)
            self._write_decisions(decisions)

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

  # Run only decision engine (use existing OCR/validation output)
  python src/app.py --decision-only
        """
    )

    paths_cfg = config.get("paths") or {}
    default_resources = paths_cfg.get("processed_dir") or paths_cfg.get("resources_dir", "resources")
    parser.add_argument(
        "--resources-dir",
        default=default_resources,
        help="Path to resources directory (default: paths.processed_dir from config, e.g. resources/processed_inputs)"
    )

    parser.add_argument(
        "--employee",
        help="Process specific employee (partial match supported)"
    )

    parser.add_argument(
        "--category",
        choices=["commute", "meal", "fuel"],
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

    parser.add_argument(
        "--decision-only",
        action="store_true",
        help="Run only the decision engine using existing OCR/validation output (policy and bills loaded from output_dir)"
    )

    args = parser.parse_args()
    # Run application (default: process all employees; use --employee to limit)
    # args.employee = "IIIPL-3185_smitha"   # uncomment to process only one employee
    # args.category = "meal"               # uncomment to process only one category
    app = BillDeskApp(args)
    app.run()


if __name__ == "__main__":
    main()
