"""Clean raw CSV data and export to data/clean/."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

TEXT_COLS = {
    "drugs.csv": ["generic_name", "brand_name", "atc", "dosage_form", "manufacturer"],
    "diseases.csv": ["name", "icd", "category", "description"],
    "relations.csv": ["relation_type", "source", "line"],
    "plans.csv": ["name", "line", "source", "evidence_level", "population", "description"],
    "drug_aliases.csv": ["alias"],
    "drug_interactions.csv": ["severity", "description", "recommendation"],
    "contraindications.csv": ["condition_type", "condition", "severity", "description"],
    "adverse_effects.csv": ["effect", "frequency", "severity"],
    "dosages.csv": ["dose", "frequency", "route", "notes"],
    "atc_classes.csv": ["name", "level"],
}


def load_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / name, dtype=str).fillna("")


def strip_text(df: pd.DataFrame, name: str) -> pd.DataFrame:
    for col in TEXT_COLS.get(name, []):
        if col in df.columns:
            df[col] = df[col].str.strip()
    return df


def clean_drugs(df: pd.DataFrame) -> pd.DataFrame:
    df = strip_text(df, "drugs.csv")
    return df.drop_duplicates(subset=["drug_id"])


def clean_diseases(df: pd.DataFrame) -> pd.DataFrame:
    df = strip_text(df, "diseases.csv")
    return df.drop_duplicates(subset=["disease_id"])


def clean_relations(df: pd.DataFrame, drugs: pd.DataFrame, diseases: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    valid_diseases = set(diseases["disease_id"])
    df = strip_text(df, "relations.csv")
    df = df[df["drug_id"].isin(valid_drugs) & df["disease_id"].isin(valid_diseases)]
    return df.drop_duplicates(subset=["drug_id", "disease_id", "relation_type"])


def clean_plans(df: pd.DataFrame, diseases: pd.DataFrame) -> pd.DataFrame:
    valid_diseases = set(diseases["disease_id"])
    df = strip_text(df, "plans.csv")
    df = df[df["disease_id"].isin(valid_diseases)]
    return df.drop_duplicates(subset=["plan_id"])


def clean_plan_drugs(df: pd.DataFrame, plans: pd.DataFrame, drugs: pd.DataFrame) -> pd.DataFrame:
    valid_plans = set(plans["plan_id"])
    valid_drugs = set(drugs["drug_id"])
    df = df[df["plan_id"].isin(valid_plans) & df["drug_id"].isin(valid_drugs)]
    return df.drop_duplicates(subset=["plan_id", "drug_id"])


def clean_aliases(df: pd.DataFrame, drugs: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    df = strip_text(df, "drug_aliases.csv")
    df = df[df["drug_id"].isin(valid_drugs)]
    return df.drop_duplicates(subset=["drug_id", "alias"])


def clean_interactions(df: pd.DataFrame, drugs: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    df = strip_text(df, "drug_interactions.csv")
    df = df[df["drug_id_a"].isin(valid_drugs) & df["drug_id_b"].isin(valid_drugs)]
    df = df[df["drug_id_a"] != df["drug_id_b"]]
    df["pair_key"] = df.apply(lambda r: tuple(sorted([r["drug_id_a"], r["drug_id_b"]])), axis=1)
    return df.drop_duplicates(subset=["pair_key"]).drop(columns=["pair_key"])


def clean_contraindications(df: pd.DataFrame, drugs: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    df = strip_text(df, "contraindications.csv")
    df = df[df["drug_id"].isin(valid_drugs)]
    return df.drop_duplicates(subset=["drug_id", "condition_type", "condition"])


def clean_adverse_effects(df: pd.DataFrame, drugs: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    df = strip_text(df, "adverse_effects.csv")
    df = df[df["drug_id"].isin(valid_drugs)]
    return df.drop_duplicates(subset=["drug_id", "effect"])


def clean_dosages(df: pd.DataFrame, drugs: pd.DataFrame, diseases: pd.DataFrame) -> pd.DataFrame:
    valid_drugs = set(drugs["drug_id"])
    valid_diseases = set(diseases["disease_id"])
    df = strip_text(df, "dosages.csv")
    df = df[df["drug_id"].isin(valid_drugs) & df["disease_id"].isin(valid_diseases)]
    return df.drop_duplicates(subset=["drug_id", "disease_id", "dose"])


def clean_hierarchy(df: pd.DataFrame, diseases: pd.DataFrame) -> pd.DataFrame:
    valid = set(diseases["disease_id"])
    df = df[df["child_disease_id"].isin(valid) & df["parent_disease_id"].isin(valid)]
    df = df[df["child_disease_id"] != df["parent_disease_id"]]
    return df.drop_duplicates(subset=["child_disease_id", "parent_disease_id"])


def clean_atc(df: pd.DataFrame) -> pd.DataFrame:
    df = strip_text(df, "atc_classes.csv")
    return df.drop_duplicates(subset=["atc_code"])


def validate_referential_integrity(
    drugs: pd.DataFrame,
    diseases: pd.DataFrame,
    relations: pd.DataFrame,
    plans: pd.DataFrame,
    plan_drugs: pd.DataFrame,
) -> list[str]:
    warnings: list[str] = []
    clinical = set(diseases.loc[diseases["category"] != "分类", "disease_id"])
    untreated = clinical - set(relations["disease_id"])
    if untreated:
        warnings.append(f"clinical diseases without direct TREATS: {sorted(untreated)}")

    plans_without_drugs = set(plans["plan_id"]) - set(plan_drugs["plan_id"])
    if plans_without_drugs:
        warnings.append(f"plans without drugs: {sorted(plans_without_drugs)}")

    return warnings


def main() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)

    drugs = clean_drugs(load_csv("drugs.csv"))
    diseases = clean_diseases(load_csv("diseases.csv"))
    relations = clean_relations(load_csv("relations.csv"), drugs, diseases)
    plans = clean_plans(load_csv("plans.csv"), diseases)
    plan_drugs = clean_plan_drugs(load_csv("plan_drugs.csv"), plans, drugs)
    aliases = clean_aliases(load_csv("drug_aliases.csv"), drugs)
    interactions = clean_interactions(load_csv("drug_interactions.csv"), drugs)
    contraindications = clean_contraindications(load_csv("contraindications.csv"), drugs)
    adverse_effects = clean_adverse_effects(load_csv("adverse_effects.csv"), drugs)
    dosages = clean_dosages(load_csv("dosages.csv"), drugs, diseases)
    hierarchy = clean_hierarchy(load_csv("disease_hierarchy.csv"), diseases)
    atc_classes = clean_atc(load_csv("atc_classes.csv"))

    warnings = validate_referential_integrity(drugs, diseases, relations, plans, plan_drugs)

    outputs = {
        "drugs.csv": drugs,
        "diseases.csv": diseases,
        "relations.csv": relations,
        "plans.csv": plans,
        "plan_drugs.csv": plan_drugs,
        "drug_aliases.csv": aliases,
        "drug_interactions.csv": interactions,
        "contraindications.csv": contraindications,
        "adverse_effects.csv": adverse_effects,
        "dosages.csv": dosages,
        "disease_hierarchy.csv": hierarchy,
        "atc_classes.csv": atc_classes,
    }

    for name, frame in outputs.items():
        frame.to_csv(CLEAN / name, index=False, encoding="utf-8-sig")

    print("Clean done:")
    for name, frame in outputs.items():
        print(f"  {name}: {len(frame)}")
    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"  - {w}")
    print(f"  output: {CLEAN}")


if __name__ == "__main__":
    main()
