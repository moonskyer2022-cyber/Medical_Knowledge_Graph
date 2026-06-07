"""Graph visualization builders."""

from typing import Any


def build_disease_graph(record: dict[str, Any]) -> dict[str, list]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node_id: str, label: str, group: str, title: str = "") -> None:
        nodes[node_id] = {"id": node_id, "label": label, "group": group, "title": title or label}

    def add_edge(source: str, target: str, label: str) -> None:
        edge_id = f"{source}-{label}-{target}"
        if not any(e["id"] == edge_id for e in edges):
            edges.append({"id": edge_id, "from": source, "to": target, "label": label})

    disease_id = f"disease-{record['disease_id']}"
    add_node(disease_id, record["disease_name"], "disease", f"{record['disease_name']} ({record['icd']})")

    for parent in record.get("parents") or []:
        if not parent.get("id"):
            continue
        parent_id = f"disease-{parent['id']}"
        add_node(parent_id, parent["name"], "category", parent["name"])
        add_edge(disease_id, parent_id, "SUBCLASS_OF")

    for plan in record.get("plans") or []:
        if not plan.get("id"):
            continue
        plan_id = f"plan-{plan['id']}"
        add_node(plan_id, plan["name"], "plan", f"line: {plan.get('line', '')}")
        add_edge(plan_id, disease_id, "TARGETS")

    for drug in record.get("plan_drugs") or []:
        if not drug.get("id"):
            continue
        drug_id = f"drug-{drug['id']}"
        add_node(drug_id, drug["generic_name"], "drug", drug.get("brand_name", ""))
        for plan in record.get("plans") or []:
            if plan.get("id"):
                add_edge(drug_id, f"plan-{plan['id']}", "INCLUDES")

    for drug in record.get("direct_drugs") or []:
        if not drug.get("id"):
            continue
        drug_id = f"drug-{drug['id']}"
        add_node(drug_id, drug["generic_name"], "drug", drug.get("brand_name", ""))
        add_edge(drug_id, disease_id, "TREATS")

    return {"nodes": list(nodes.values()), "edges": edges}


def build_drug_graph(record: dict[str, Any]) -> dict[str, list]:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add_node(node_id: str, label: str, group: str, title: str = "") -> None:
        nodes[node_id] = {"id": node_id, "label": label, "group": group, "title": title or label}

    def add_edge(source: str, target: str, label: str) -> None:
        edge_id = f"{source}-{label}-{target}"
        if not any(e["id"] == edge_id for e in edges):
            edges.append({"id": edge_id, "from": source, "to": target, "label": label})

    drug_id = f"drug-{record['drug_id']}"
    add_node(drug_id, record["drug_name"], "drug", record.get("brand_name", ""))

    disease_ids = []
    for dis in record.get("diseases") or []:
        if not dis.get("id"):
            continue
        disease_node = f"disease-{dis['id']}"
        add_node(disease_node, dis["name"], "disease", dis.get("icd", ""))
        add_edge(drug_id, disease_node, "TREATS")
        disease_ids.append(disease_node)

    for plan in record.get("plans") or []:
        if not plan.get("id"):
            continue
        plan_id = f"plan-{plan['id']}"
        add_node(plan_id, plan["name"], "plan", plan.get("line", ""))
        if disease_ids:
            add_edge(plan_id, disease_ids[0], "TARGETS")

    for drug in record.get("related_drugs") or []:
        if not drug.get("id") or drug["id"] == record["drug_id"]:
            continue
        related_id = f"drug-{drug['id']}"
        add_node(related_id, drug["generic_name"], "drug", drug.get("brand_name", ""))

    for inter in record.get("interactions") or []:
        if not inter.get("id"):
            continue
        other_id = f"drug-{inter['id']}"
        add_node(other_id, inter["generic_name"], "drug", inter.get("severity", ""))
        add_edge(drug_id, other_id, "INTERACTS")

    for ae in record.get("adverse_effects") or []:
        if not ae.get("name"):
            continue
        ae_id = f"ae-{ae['name']}"
        add_node(ae_id, ae["name"], "effect", ae.get("severity", ""))
        add_edge(drug_id, ae_id, "CAUSES")

    return {"nodes": list(nodes.values()), "edges": edges}
