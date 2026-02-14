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

import os
import re
import sys
import argparse
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from commons.constants import Constants as Co
from commons.file_utils import FileUtils
from commons.config import config
from commons.llm import get_llm_model_name

from app.extractors._paths import project_path
from app.extractors import EXTRACTOR_REGISTRY, get_extractor
from app.decision import DecisionEngine
from app.rag import PolicyExtractorWithRAG
from app.decision.postprocessing import write_decision_outputs, write_postprocessing_output
from app.org_api import get_org_client

# Single source of truth for expense categories (matches extractor registry)
EXPENSE_CATEGORIES = tuple(EXTRACTOR_REGISTRY.keys())


def _output_dir_absolute(output_dir: str) -> str:
    """Resolve output dir to absolute path (project-relative if not already absolute)."""
    if os.path.isabs(output_dir):
        return output_dir
    return project_path(output_dir)


def _emp_key_from_folder_name(folder_name: str) -> Optional[str]:
    """Derive emp_key from folder name (e.g. IIIPL-1000_naveen_oct_amex -> IIIPL-1000_naveen)."""
    parts = folder_name.split("_")
    if len(parts) < 4:
        return None
    emp_id = parts[0]
    emp_name_raw = parts[1]
    name_part = re.sub(r"\s+", "", (emp_name_raw or "").strip()).lower()
    return f"{emp_id}_{name_part}"


def _resolve_policy_path(resources_dir: str) -> str:
    """Find company_policy.pdf under resources_dir or raw resources; return resolved path."""
    raw_resources = (config.get("paths") or {}).get("resources_dir", "resources")
    for base in (resources_dir, raw_resources):
        p = project_path(base, "company_policy.pdf")
        if os.path.exists(p):
            return p
        p = project_path(base, "policy", "company_policy.pdf")
        if os.path.exists(p):
            return p
    return project_path(resources_dir, "policy", "company_policy.pdf")


def _filter_employees_by_arg(employees: Dict[str, Dict[str, List[str]]], employee_arg: str) -> Dict[str, Dict[str, List[str]]]:
    """Filter employees by --employee (partial match on key or name). Returns subset or same dict if no match needed."""
    if not employee_arg:
        return employees
    needle = employee_arg.lower()
    matching = {k: v for k, v in employees.items() if needle in k.lower()}
    if not matching and "_" in employee_arg:
        name_part = employee_arg.rsplit("_", 1)[-1].lower()
        matching = {k: v for k, v in employees.items() if name_part in k.lower()}
    return matching


def _fetch_org_data_for_employees(
    employee_org_data: Dict[str, Optional[Dict]],
    all_bills: Dict[str, List],
    org_client,
) -> None:
    """Populate employee_org_data with org API response for each emp_key in all_bills (mutates employee_org_data)."""
    if not org_client:
        return
    for emp_key in all_bills:
        emp_id = emp_key.split("_", 1)[0]
        try:
            employee_org_data[emp_key] = org_client.get_employee_details(emp_id)
        except Exception:
            employee_org_data[emp_key] = None


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
        base = project_path(self.config.resources_dir)

        for category in EXPENSE_CATEGORIES:
            category_path = os.path.join(base, category)
            if not os.path.exists(category_path):
                continue
            for folder_name in os.listdir(category_path):
                folder_path = os.path.join(category_path, folder_name)
                if not os.path.isdir(folder_path):
                    continue
                key = _emp_key_from_folder_name(folder_name)
                if not key:
                    continue
                if key not in employees:
                    employees[key] = {c: [] for c in EXPENSE_CATEGORIES}
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
        prompt_dir = project_path("src", "prompt")
        category_to_prompt = {
            "commute": os.path.join(prompt_dir, "system_prompt_cab.txt"),
            "meal": os.path.join(prompt_dir, "system_meal_prompt.txt"),
            "fuel": os.path.join(prompt_dir, "system_prompt_fuel.txt"),
        }
        category_labels = {"commute": "🚗 commute", "meal": "🍽️ meal", "fuel": "⛽ fuel"}

        for category in EXPENSE_CATEGORIES:
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
        for category in EXPENSE_CATEGORIES:
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
                emp_key = _emp_key_from_folder_name(name)
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
        """Write decision outputs (audit JSON, summary, CSV, README, org data) via post-processing."""
        base = _output_dir_absolute(self.config.output_dir)
        if not decisions:
            return
        write_decision_outputs(
            decisions,
            base,
            self.config.model_name,
            employee_org_data=self.employee_org_data,
        )
        write_postprocessing_output(decisions, base, self.config.model_name)

    def _run_decision_engine_per_category(self, policy: Dict) -> List[Dict]:
        """Run decision engine separately per category so decision data are not mixed."""
        all_decisions: List[Dict] = []
        org_data = self.employee_org_data if self.employee_org_data else None
        for category in EXPENSE_CATEGORIES:
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

        if getattr(self.args, "decision_only", False):
            self._run_decision_only()
            return
        self._run_full_flow()
        print("\n" + "=" * 60)
        print("✅ Processing complete!")
        print("=" * 60)

    def _run_decision_only(self) -> None:
        """Load policy and bills from output_dir, run decision engine, write results."""
        self.policy = self._load_policy_from_output()
        if not self.policy:
            return
        self.all_bills = self._load_bills_from_output()
        if not self.all_bills:
            print("❌ No bills found in output. Run full flow first (without --decision-only).")
            return
        print(f"📂 Loaded policy and {sum(len(v) for v in self.all_bills.values())} bills for {len(self.all_bills)} employee(s)")
        self._init_decision_engine()
        _fetch_org_data_for_employees(self.employee_org_data, self.all_bills, get_org_client())
        decisions = self._run_decision_engine_per_category(self.policy)
        self._write_decisions(decisions)
        print("\n" + "=" * 60)
        print("✅ Decision-only run complete!")
        print("=" * 60)

    def _init_decision_engine(self) -> None:
        """Create decision engine with current config."""
        self.decision_engine = DecisionEngine(
            model_name=self.config.model_name,
            temperature=self.config.temperature,
            output_dir=self.config.output_dir,
            resources_dir=self.config.resources_dir,
            enable_rag=self.config.enable_rag,
            policy_extractor=self.policy_extractor if self.config.enable_rag else None,
        )

    def _run_full_flow(self) -> None:
        """Extract policy, discover/process employees, optionally run decision engine."""
        policy_path = _resolve_policy_path(self.config.resources_dir)
        policy_prompt_path = "src/prompt/system_prompt_policy.txt"
        self.policy = self.policy_extractor.extract(policy_path, policy_prompt_path)
        if not self.policy:
            print("❌ Failed to extract policy. Exiting.")
            return

        self._init_decision_engine()
        all_employees = self.discover_employees()
        employees = _filter_employees_by_arg(all_employees, getattr(self.args, "employee", None) or "")
        if getattr(self.args, "employee", None) and not employees:
            available = ", ".join(sorted(all_employees.keys())) if all_employees else "(none)"
            print(f"❌ No employee found matching: {self.args.employee}")
            print(f"   Available keys (from folder names under {self.config.resources_dir}/commute|meal|fuel): {available}")
            print("   Tip: use --employee <key> or just the name, e.g. --employee smitha")
            return

        print(f"\n📊 Found {len(employees)} employee(s) to process")
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

        if self.all_bills and not getattr(self.args, "skip_decision", False):
            decisions = self._run_decision_engine_per_category(self.policy)
            self._write_decisions(decisions)


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
