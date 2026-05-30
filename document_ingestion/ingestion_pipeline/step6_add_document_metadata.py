from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from dotenv import load_dotenv
from google import genai
from google.genai import types

from utils import GENERATION_MODEL, create_gemini_client_from_env, default_context_dir, default_document_metadata_dir, default_metadata_dir, default_summary_dir, find_jsonl_files, load_jsonl, save_json_atomic, save_jsonl_atomic, strip_json_fences

logger = logging.getLogger(__name__)


class _ProductSnapshot(TypedDict):
    product_name: str
    product_type: str
    insurance_company: str
    target_segment: list[str]
    main_objective: list[str]
    key_value_proposition: str


class _IdealClientProfile(TypedDict):
    suitable_for: list[str]
    not_ideal_for: list[str]
    typical_age_group: str
    income_profile: str
    family_situation: str
    financial_goals: list[str]
    risk_appetite: str


class _CoreFeatures(TypedDict):
    coverage_duration: str
    renewable: bool | None
    convertible: bool | None
    participating_status: str
    guaranteed_cash_value: bool | None
    premium_structure: str
    riders_available: list[str]
    multiplier_benefits: str
    critical_illness_stages_covered: list[str]
    premium_waiver_options: list[str]


class _UnderwritingNotes(TypedDict):
    simplified_underwriting_available: bool | None
    medical_exam_threshold: str
    health_condition_notes: list[str]
    bmi_limits: str
    foreigner_eligibility: bool | None
    other_notes: list[str]


class _QuickNumbers(TypedDict):
    entry_age: str
    minimum_premium: str
    policy_term_range: str
    maximum_coverage: str
    multiplier_duration: str
    sample_premiums: list[dict[str, str]]


class _MetadataBlock(TypedDict):
    source_document: str
    summary_version: str
    last_updated: str
    review_status: str
    intended_user: str
    compliance_review_required: bool


class DocumentMetadata(TypedDict):
    product_snapshot: _ProductSnapshot
    ideal_client_profile: _IdealClientProfile
    core_features: _CoreFeatures
    key_selling_points: list[str]
    common_use_cases: list[dict[str, str]]
    key_limitations_objections: list[str]
    underwriting_notes: _UnderwritingNotes
    rider_compatibility: list[dict[str, Any]]
    recommended_bundles: list[str]
    competitor_comparison: list[dict[str, str]]
    compliance_advisory_notes: list[str]
    quick_numbers: _QuickNumbers
    metadata: _MetadataBlock



def _to_list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _to_nullable_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"true", "yes", "y"}:
            return True
        if raw in {"false", "no", "n"}:
            return False
    return None


def _to_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_common_use_cases(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "scenario": _to_string(item.get("scenario")),
                "positioning": _to_string(item.get("positioning")),
            }
        )
    return out


def _normalize_rider_compatibility(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "rider_name": _to_string(item.get("rider_name")),
                "available": _to_nullable_bool(item.get("available")),
                "notes": _to_string(item.get("notes")),
            }
        )
    return out


def _normalize_competitor_comparison(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "this_product_better_for": _to_string(item.get("this_product_better_for")),
                "competitor_better_for": _to_string(item.get("competitor_better_for")),
                "competitor_product": _to_string(item.get("competitor_product")),
            }
        )
    return out


def _normalize_sample_premiums(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "age": _to_string(item.get("age")),
                "gender": _to_string(item.get("gender")),
                "smoker_status": _to_string(item.get("smoker_status")),
                "coverage_amount": _to_string(item.get("coverage_amount")),
                "premium": _to_string(item.get("premium")),
            }
        )
    return out


def normalize_document_metadata(raw: dict[str, Any], source_document: str, summary_version: str) -> DocumentMetadata:
    product_snapshot = raw.get("product_snapshot") if isinstance(raw.get("product_snapshot"), dict) else {}
    ideal_client_profile = raw.get("ideal_client_profile") if isinstance(raw.get("ideal_client_profile"), dict) else {}
    core_features = raw.get("core_features") if isinstance(raw.get("core_features"), dict) else {}
    underwriting_notes = raw.get("underwriting_notes") if isinstance(raw.get("underwriting_notes"), dict) else {}
    quick_numbers = raw.get("quick_numbers") if isinstance(raw.get("quick_numbers"), dict) else {}
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}

    normalized: dict[str, Any] = {
        "product_snapshot": {
            "product_name": _to_string(product_snapshot.get("product_name")),
            "product_type": _to_string(product_snapshot.get("product_type")),
            "insurance_company": _to_string(product_snapshot.get("insurance_company")),
            "target_segment": _to_list_of_strings(product_snapshot.get("target_segment")),
            "main_objective": _to_list_of_strings(product_snapshot.get("main_objective")),
            "key_value_proposition": _to_string(product_snapshot.get("key_value_proposition")),
        },
        "ideal_client_profile": {
            "suitable_for": _to_list_of_strings(ideal_client_profile.get("suitable_for")),
            "not_ideal_for": _to_list_of_strings(ideal_client_profile.get("not_ideal_for")),
            "typical_age_group": _to_string(ideal_client_profile.get("typical_age_group")),
            "income_profile": _to_string(ideal_client_profile.get("income_profile")),
            "family_situation": _to_string(ideal_client_profile.get("family_situation")),
            "financial_goals": _to_list_of_strings(ideal_client_profile.get("financial_goals")),
            "risk_appetite": _to_string(ideal_client_profile.get("risk_appetite")),
        },
        "core_features": {
            "coverage_duration": _to_string(core_features.get("coverage_duration")),
            "renewable": _to_nullable_bool(core_features.get("renewable")),
            "convertible": _to_nullable_bool(core_features.get("convertible")),
            "participating_status": _to_string(core_features.get("participating_status")),
            "guaranteed_cash_value": _to_nullable_bool(core_features.get("guaranteed_cash_value")),
            "premium_structure": _to_string(core_features.get("premium_structure")),
            "riders_available": _to_list_of_strings(core_features.get("riders_available")),
            "multiplier_benefits": _to_string(core_features.get("multiplier_benefits")),
            "critical_illness_stages_covered": _to_list_of_strings(core_features.get("critical_illness_stages_covered")),
            "premium_waiver_options": _to_list_of_strings(core_features.get("premium_waiver_options")),
        },
        "key_selling_points": _to_list_of_strings(raw.get("key_selling_points")),
        "common_use_cases": _normalize_common_use_cases(raw.get("common_use_cases")),
        "key_limitations_objections": _to_list_of_strings(raw.get("key_limitations_objections")),
        "underwriting_notes": {
            "simplified_underwriting_available": _to_nullable_bool(underwriting_notes.get("simplified_underwriting_available")),
            "medical_exam_threshold": _to_string(underwriting_notes.get("medical_exam_threshold")),
            "health_condition_notes": _to_list_of_strings(underwriting_notes.get("health_condition_notes")),
            "bmi_limits": _to_string(underwriting_notes.get("bmi_limits")),
            "foreigner_eligibility": _to_nullable_bool(underwriting_notes.get("foreigner_eligibility")),
            "other_notes": _to_list_of_strings(underwriting_notes.get("other_notes")),
        },
        "rider_compatibility": _normalize_rider_compatibility(raw.get("rider_compatibility")),
        "recommended_bundles": _to_list_of_strings(raw.get("recommended_bundles")),
        "competitor_comparison": _normalize_competitor_comparison(raw.get("competitor_comparison")),
        "compliance_advisory_notes": _to_list_of_strings(raw.get("compliance_advisory_notes")),
        "quick_numbers": {
            "entry_age": _to_string(quick_numbers.get("entry_age")),
            "minimum_premium": _to_string(quick_numbers.get("minimum_premium")),
            "policy_term_range": _to_string(quick_numbers.get("policy_term_range")),
            "maximum_coverage": _to_string(quick_numbers.get("maximum_coverage")),
            "multiplier_duration": _to_string(quick_numbers.get("multiplier_duration")),
            "sample_premiums": _normalize_sample_premiums(quick_numbers.get("sample_premiums")),
        },
        "metadata": {
            "source_document": _to_string(metadata.get("source_document")) or source_document,
            "summary_version": _to_string(metadata.get("summary_version")) or summary_version,
            "last_updated": _to_string(metadata.get("last_updated")) or datetime.now(timezone.utc).date().isoformat(),
            "review_status": _to_string(metadata.get("review_status")) or "draft",
            "intended_user": "internal_agents",
            "compliance_review_required": True,
        },
    }
    return normalized


def _schema_example() -> DocumentMetadata:
    return {
        "product_snapshot": {
            "product_name": "",
            "product_type": "",
            "insurance_company": "",
            "target_segment": [],
            "main_objective": [],
            "key_value_proposition": "",
        },
        "ideal_client_profile": {
            "suitable_for": [],
            "not_ideal_for": [],
            "typical_age_group": "",
            "income_profile": "",
            "family_situation": "",
            "financial_goals": [],
            "risk_appetite": "",
        },
        "core_features": {
            "coverage_duration": "",
            "renewable": None,
            "convertible": None,
            "participating_status": "",
            "guaranteed_cash_value": None,
            "premium_structure": "",
            "riders_available": [],
            "multiplier_benefits": "",
            "critical_illness_stages_covered": [],
            "premium_waiver_options": [],
        },
        "key_selling_points": [],
        "common_use_cases": [{"scenario": "", "positioning": ""}],
        "key_limitations_objections": [],
        "underwriting_notes": {
            "simplified_underwriting_available": None,
            "medical_exam_threshold": "",
            "health_condition_notes": [],
            "bmi_limits": "",
            "foreigner_eligibility": None,
            "other_notes": [],
        },
        "rider_compatibility": [{"rider_name": "", "available": None, "notes": ""}],
        "recommended_bundles": [],
        "competitor_comparison": [
            {"this_product_better_for": "", "competitor_better_for": "", "competitor_product": ""}
        ],
        "compliance_advisory_notes": [],
        "quick_numbers": {
            "entry_age": "",
            "minimum_premium": "",
            "policy_term_range": "",
            "maximum_coverage": "",
            "multiplier_duration": "",
            "sample_premiums": [
                {"age": "", "gender": "", "smoker_status": "", "coverage_amount": "", "premium": ""}
            ],
        },
        "metadata": {
            "source_document": "",
            "summary_version": "",
            "last_updated": "",
            "review_status": "",
            "intended_user": "internal_agents",
            "compliance_review_required": True,
        },
    }


def extract_metadata_with_llm(client: genai.Client, model: str, summary_text: str) -> dict[str, Any]:
    schema_text = json.dumps(_schema_example(), ensure_ascii=False, indent=2)
    prompt = (
        "Extract the product document metadata from the summary below.\n"
        "Return JSON only, no markdown.\n"
        "Use this exact schema and keys.\n"
        "If unknown, use empty string, empty array, or null based on field type.\n\n"
        f"Schema:\n{schema_text}\n\n"
        f"Summary:\n{summary_text}"
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    text = strip_json_fences(response.text or "")
    if not text:
        raise ValueError("LLM returned empty metadata response")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM metadata response is not a JSON object")
    return parsed


def load_summary_record(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        raise FileNotFoundError(f"Step 5 summary file not found: {summary_path}")
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid summary payload in {summary_path}")
    return data


def metadata_already_present(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        doc_meta = row.get("document_metadata")
        if not isinstance(doc_meta, dict):
            return False
        if not doc_meta:
            return False
    return True


def stable_summary_version(source_id: str, summary_record: dict[str, Any]) -> str:
    stable_components = "|".join(
        [
            source_id,
            str(summary_record.get("idempotency_key", "")),
            str(summary_record.get("generated_at", "")),
            hashlib.sha256(str(summary_record.get("generated_summary", "")).encode("utf-8")).hexdigest(),
        ]
    )
    return hashlib.sha256(stable_components.encode("utf-8")).hexdigest()


def enrich_file(
    input_path: Path,
    output_path: Path,
    document_metadata_path: Path,
    summary_root: Path,
    client: genai.Client,
    model: str,
    force: bool,
) -> None:
    source_id = input_path.stem
    rows = load_jsonl(input_path)
    if not rows:
        logger.info("Skipping %s because input is empty", source_id)
        return

    if output_path.exists() and not force:
        existing_rows = load_jsonl(output_path)
        if metadata_already_present(existing_rows):
            if not document_metadata_path.exists():
                existing_metadata = existing_rows[0].get("document_metadata")
                if isinstance(existing_metadata, dict) and existing_metadata:
                    save_json_atomic(document_metadata_path, existing_metadata)
                    logger.info("Backfilled document metadata file for %s to %s", source_id, document_metadata_path)
            logger.info("Skipping %s because output already contains document metadata: %s", source_id, output_path)
            return

    summary_path = summary_root / f"{source_id}.json"
    summary_record = load_summary_record(summary_path)
    summary_text = str(summary_record.get("generated_summary", "")).strip()
    if not summary_text:
        raise ValueError(f"Summary text is empty in {summary_path}")

    extracted = extract_metadata_with_llm(client, model, summary_text)
    normalized = normalize_document_metadata(
        raw=extracted,
        source_document=summary_record.get("pdf_path", f"{source_id}.pdf"),
        summary_version=stable_summary_version(source_id, summary_record),
    )
    save_json_atomic(document_metadata_path, normalized)

    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        updated = dict(row)
        updated["document_metadata"] = normalized
        enriched_rows.append(updated)

    save_jsonl_atomic(output_path, enriched_rows)
    logger.info("Saved metadata-enriched chunks for %s to %s", source_id, output_path)
    logger.info("Saved document metadata for %s to %s", source_id, document_metadata_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Attach Step-5 document metadata extraction to each chunk.")
    parser.add_argument("--file", default=None, help="Process only this PDF filename.")
    parser.add_argument("--input-dir", default=default_context_dir())
    parser.add_argument("--output-dir", default=default_metadata_dir())
    parser.add_argument("--document-metadata-dir", default=default_document_metadata_dir())
    parser.add_argument("--summary-dir", default=default_summary_dir())
    parser.add_argument("--model", default=GENERATION_MODEL)
    parser.add_argument("--force", action="store_true", help="Recompute metadata even when output already has rows.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    load_dotenv()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s %(message)s")

    input_root = Path(args.input_dir)
    output_root = Path(args.output_dir)
    document_metadata_root = Path(args.document_metadata_dir)
    summary_root = Path(args.summary_dir)

    client = create_gemini_client_from_env()
    for input_path in find_jsonl_files(input_root, args.file):
        output_path = output_root / input_path.name
        document_metadata_path = document_metadata_root / f"{input_path.stem}.json"
        enrich_file(
            input_path=input_path,
            output_path=output_path,
            document_metadata_path=document_metadata_path,
            summary_root=summary_root,
            client=client,
            model=args.model,
            force=args.force,
        )


if __name__ == "__main__":
    main()
