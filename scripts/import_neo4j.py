"""Import cleaned CSV data into Neo4j."""

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
CYPHER = ROOT / "cypher" / "schema.cypher"

load_dotenv(ROOT / ".env")

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def run_schema(session) -> None:
    if not CYPHER.exists():
        return
    statements = [
        s.strip()
        for s in CYPHER.read_text(encoding="utf-8").split(";")
        if s.strip() and not s.strip().startswith("//")
    ]
    for stmt in statements:
        session.run(stmt)


def clear_graph(session) -> None:
    session.run("MATCH (n) DETACH DELETE n")


def import_drugs(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (d:Drug {id: row.drug_id})
        SET d.generic_name = row.generic_name,
            d.brand_name = row.brand_name,
            d.atc = row.atc,
            d.dosage_form = row.dosage_form,
            d.manufacturer = row.manufacturer
        """,
        rows=df.to_dict("records"),
    )


def import_diseases(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (d:Disease {id: row.disease_id})
        SET d.name = row.name,
            d.icd = row.icd,
            d.category = row.category,
            d.description = row.description
        """,
        rows=df.to_dict("records"),
    )


def import_plans(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (p:Plan {id: row.plan_id})
        SET p.name = row.name,
            p.line = row.line,
            p.source = row.source,
            p.evidence_level = row.evidence_level,
            p.population = row.population,
            p.description = row.description
        WITH p, row
        MATCH (dis:Disease {id: row.disease_id})
        MERGE (p)-[:TARGETS]->(dis)
        """,
        rows=df.to_dict("records"),
    )


def import_relations(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (drug:Drug {id: row.drug_id}), (dis:Disease {id: row.disease_id})
        MERGE (drug)-[r:TREATS]->(dis)
        SET r.source = row.source, r.line = row.line, r.relation_type = row.relation_type
        """,
        rows=df.to_dict("records"),
    )


def import_plan_drugs(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (p:Plan {id: row.plan_id}), (drug:Drug {id: row.drug_id})
        MERGE (p)-[:INCLUDES]->(drug)
        """,
        rows=df.to_dict("records"),
    )


def import_aliases(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (d:Drug {id: row.drug_id})
        MERGE (d)-[:HAS_ALIAS]->(a:Alias {name: row.alias})
        """,
        rows=df.to_dict("records"),
    )


def import_interactions(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (a:Drug {id: row.drug_id_a}), (b:Drug {id: row.drug_id_b})
        MERGE (a)-[r:INTERACTS_WITH]-(b)
        SET r.severity = row.severity,
            r.description = row.description,
            r.recommendation = row.recommendation
        """,
        rows=df.to_dict("records"),
    )


def import_contraindications(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (d:Drug {id: row.drug_id})
        MERGE (d)-[r:CONTRAINDICATED_FOR]->(c:Condition {name: row.condition})
        SET r.condition_type = row.condition_type,
            r.severity = row.severity,
            r.description = row.description
        """,
        rows=df.to_dict("records"),
    )


def import_adverse_effects(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (d:Drug {id: row.drug_id})
        MERGE (d)-[r:CAUSES]->(e:AdverseEffect {name: row.effect})
        SET r.frequency = row.frequency, r.severity = row.severity
        """,
        rows=df.to_dict("records"),
    )


def import_dosages(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (drug:Drug {id: row.drug_id}), (dis:Disease {id: row.disease_id})
        MERGE (drug)-[r:HAS_DOSAGE_FOR]->(dis)
        SET r.dose = row.dose,
            r.frequency = row.frequency,
            r.route = row.route,
            r.notes = row.notes
        """,
        rows=df.to_dict("records"),
    )


def import_hierarchy(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (child:Disease {id: row.child_disease_id}),
              (parent:Disease {id: row.parent_disease_id})
        MERGE (child)-[:SUBCLASS_OF]->(parent)
        """,
        rows=df.to_dict("records"),
    )


def import_atc(session, df: pd.DataFrame) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MERGE (a:AtcClass {code: row.atc_code})
        SET a.name = row.name, a.level = toInteger(row.level)
        """,
        rows=df.to_dict("records"),
    )
    session.run(
        """
        MATCH (d:Drug), (a:AtcClass)
        WHERE d.atc = a.code
        MERGE (d)-[:BELONGS_TO_ATC]->(a)
        """
    )
    session.run(
        """
        MATCH (child:AtcClass), (parent:AtcClass)
        WHERE child.code <> parent.code
          AND child.code STARTS WITH parent.code
          AND size(child.code) = size(parent.code) + 1
        MERGE (child)-[:SUBCLASS_OF]->(parent)
        """
    )


def print_stats(session) -> None:
    stats = session.run(
        """
        MATCH (d:Drug) WITH count(d) AS drugs
        MATCH (dis:Disease) WITH drugs, count(dis) AS diseases
        MATCH (p:Plan) WITH drugs, diseases, count(p) AS plans
        MATCH ()-[t:TREATS]->() WITH drugs, diseases, plans, count(t) AS treats
        MATCH ()-[i:INTERACTS_WITH]-() WITH drugs, diseases, plans, treats, count(i)/2 AS interactions
        MATCH ()-[c:CONTRAINDICATED_FOR]->() WITH drugs, diseases, plans, treats, interactions, count(c) AS contraindications
        MATCH ()-[a:CAUSES]->() RETURN drugs, diseases, plans, treats, interactions, contraindications, count(a) AS adverse_effects
        """
    ).single()
    print("Import done:")
    for key in stats.keys():
        print(f"  {key}: {stats[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSV data into Neo4j")
    parser.add_argument("--full", action="store_true", help="Clear graph before import")
    args = parser.parse_args()

    if not (CLEAN / "drugs.csv").exists():
        raise FileNotFoundError("Run scripts/clean.py first to generate data/clean/")

    files = {
        "drugs": pd.read_csv(CLEAN / "drugs.csv", dtype=str).fillna(""),
        "diseases": pd.read_csv(CLEAN / "diseases.csv", dtype=str).fillna(""),
        "relations": pd.read_csv(CLEAN / "relations.csv", dtype=str).fillna(""),
        "plans": pd.read_csv(CLEAN / "plans.csv", dtype=str).fillna(""),
        "plan_drugs": pd.read_csv(CLEAN / "plan_drugs.csv", dtype=str).fillna(""),
        "aliases": pd.read_csv(CLEAN / "drug_aliases.csv", dtype=str).fillna(""),
        "interactions": pd.read_csv(CLEAN / "drug_interactions.csv", dtype=str).fillna(""),
        "contraindications": pd.read_csv(CLEAN / "contraindications.csv", dtype=str).fillna(""),
        "adverse_effects": pd.read_csv(CLEAN / "adverse_effects.csv", dtype=str).fillna(""),
        "dosages": pd.read_csv(CLEAN / "dosages.csv", dtype=str).fillna(""),
        "hierarchy": pd.read_csv(CLEAN / "disease_hierarchy.csv", dtype=str).fillna(""),
        "atc_classes": pd.read_csv(CLEAN / "atc_classes.csv", dtype=str).fillna(""),
    }

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        print(f"Connected to Neo4j: {URI}")
        with driver.session() as session:
            run_schema(session)
            if args.full:
                print("Clearing existing graph...")
                clear_graph(session)
            import_drugs(session, files["drugs"])
            import_diseases(session, files["diseases"])
            import_plans(session, files["plans"])
            import_relations(session, files["relations"])
            import_plan_drugs(session, files["plan_drugs"])
            import_aliases(session, files["aliases"])
            import_interactions(session, files["interactions"])
            import_contraindications(session, files["contraindications"])
            import_adverse_effects(session, files["adverse_effects"])
            import_dosages(session, files["dosages"])
            import_hierarchy(session, files["hierarchy"])
            import_atc(session, files["atc_classes"])
            print_stats(session)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
