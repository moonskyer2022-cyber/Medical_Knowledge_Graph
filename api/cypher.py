"""Neo4j Cypher query definitions."""

RESOLVE_DRUG = """
MATCH (d:Drug)
WHERE d.generic_name CONTAINS $name OR d.brand_name CONTAINS $name
   OR EXISTS { MATCH (d)-[:HAS_ALIAS]->(a:Alias) WHERE a.name CONTAINS $name }
RETURN d.id AS id, d.generic_name AS generic_name, d.brand_name AS brand_name
LIMIT 10
"""

RESOLVE_DISEASE = """
MATCH (d:Disease)
WHERE d.name CONTAINS $keyword OR d.icd = $icd
RETURN d.id AS id, d.name AS name, d.icd AS icd
LIMIT 10
"""

RECOMMEND_CYPHER = """
MATCH (dis:Disease)
WHERE ($keyword <> '' AND dis.name CONTAINS $keyword)
   OR ($icd <> '' AND dis.icd = $icd)
   OR ($keyword <> '' AND EXISTS {
       MATCH (child:Disease)-[:SUBCLASS_OF*1..2]->(dis)
       WHERE child.name CONTAINS $keyword
   })
MATCH (p:Plan)-[:TARGETS]->(dis)
MATCH (p)-[:INCLUDES]->(drug:Drug)
OPTIONAL MATCH (drug)-[dos:HAS_DOSAGE_FOR]->(dis)
RETURN dis.name AS disease, dis.icd AS icd, dis.category AS category,
       p.name AS plan, p.line AS line, p.source AS source,
       p.evidence_level AS evidence_level, p.population AS population,
       p.description AS plan_description,
       collect(DISTINCT {
           generic_name: drug.generic_name,
           brand_name: drug.brand_name,
           atc: drug.atc,
           dose: dos.dose,
           frequency: dos.frequency,
           route: dos.route,
           notes: dos.notes
       }) AS drugs
ORDER BY CASE p.line WHEN 'first' THEN 0 WHEN 'second' THEN 1 ELSE 2 END,
         CASE p.evidence_level WHEN 'A' THEN 0 WHEN 'B' THEN 1 ELSE 2 END,
         p.name
"""

DRUG_CYPHER = """
MATCH (drug:Drug)
WHERE drug.generic_name CONTAINS $drug_name OR drug.brand_name CONTAINS $drug_name
   OR EXISTS { MATCH (drug)-[:HAS_ALIAS]->(a:Alias) WHERE a.name CONTAINS $drug_name }
OPTIONAL MATCH (drug)-[r:TREATS]->(dis:Disease)
OPTIONAL MATCH (drug)-[dos:HAS_DOSAGE_FOR]->(dis)
OPTIONAL MATCH (drug)-[ae_rel:CAUSES]->(ae:AdverseEffect)
OPTIONAL MATCH (drug)-[ci:CONTRAINDICATED_FOR]->(cond:Condition)
OPTIONAL MATCH (drug)-[:BELONGS_TO_ATC]->(atc:AtcClass)
RETURN drug.id AS id, drug.generic_name AS drug, drug.brand_name AS brand,
       drug.atc AS atc, drug.dosage_form AS dosage_form, drug.manufacturer AS manufacturer,
       atc.name AS atc_name,
       collect(DISTINCT {disease: dis.name, icd: dis.icd, line: r.line, source: r.source,
           dose: dos.dose, frequency: dos.frequency}) AS diseases,
       collect(DISTINCT {effect: ae.name, frequency: ae_rel.frequency, severity: ae_rel.severity}) AS adverse_effects,
       collect(DISTINCT {condition: cond.name, type: ci.condition_type,
           severity: ci.severity, description: ci.description}) AS contraindications
"""

DRUG_DETAIL_CYPHER = """
MATCH (drug:Drug {id: $drug_id})
OPTIONAL MATCH (drug)-[:HAS_ALIAS]->(alias:Alias)
OPTIONAL MATCH (drug)-[r:TREATS]->(dis:Disease)
OPTIONAL MATCH (drug)-[dos:HAS_DOSAGE_FOR]->(dis)
OPTIONAL MATCH (drug)-[ae_rel:CAUSES]->(ae:AdverseEffect)
OPTIONAL MATCH (drug)-[ci:CONTRAINDICATED_FOR]->(cond:Condition)
OPTIONAL MATCH (drug)-[:BELONGS_TO_ATC]->(atc:AtcClass)
RETURN drug, collect(DISTINCT alias.name) AS aliases, atc,
       collect(DISTINCT {disease: dis.name, icd: dis.icd, line: r.line, source: r.source,
           dose: dos.dose, frequency: dos.frequency, route: dos.route}) AS diseases,
       collect(DISTINCT {effect: ae.name, frequency: ae_rel.frequency, severity: ae_rel.severity}) AS adverse_effects,
       collect(DISTINCT {condition: cond.name, type: ci.condition_type,
           severity: ci.severity, description: ci.description}) AS contraindications
"""

INTERACTION_CHECK_CYPHER = """
UNWIND $drug_ids AS did
MATCH (d:Drug {id: did})
WITH collect(d) AS drugs
UNWIND drugs AS a
UNWIND drugs AS b
WITH a, b WHERE id(a) < id(b)
OPTIONAL MATCH (a)-[r:INTERACTS_WITH]-(b)
RETURN a.id AS drug_a_id, a.generic_name AS drug_a, b.id AS drug_b_id, b.generic_name AS drug_b,
       r.severity AS severity, r.description AS description, r.recommendation AS recommendation
"""

INTERACTION_BY_NAME_CYPHER = """
MATCH (a:Drug), (b:Drug)
WHERE a.id IN $drug_ids AND b.id IN $drug_ids AND id(a) < id(b)
OPTIONAL MATCH (a)-[r:INTERACTS_WITH]-(b)
WITH a, b, r
WHERE r IS NOT NULL
RETURN a.generic_name AS drug_a, b.generic_name AS drug_b,
       r.severity AS severity, r.description AS description, r.recommendation AS recommendation
"""

DUPLICATE_CLASS_CYPHER = """
UNWIND $drug_ids AS did
MATCH (d:Drug {id: did})-[:BELONGS_TO_ATC]->(atc:AtcClass)
WITH atc, collect(d) AS drugs
WHERE size(drugs) > 1
RETURN atc.code AS atc_code, atc.name AS atc_name,
       [d IN drugs | d.generic_name] AS drugs
"""

CONTRAINDICATION_CHECK_CYPHER = """
UNWIND $drug_ids AS did
MATCH (d:Drug {id: did})-[r:CONTRAINDICATED_FOR]->(c:Condition)
WHERE ($condition = '' OR c.name CONTAINS $condition)
RETURN d.generic_name AS drug, c.name AS condition, r.condition_type AS condition_type,
       r.severity AS severity, r.description AS description
"""

COMORBIDITY_PLAN_CYPHER = """
UNWIND $disease_keywords AS kw
MATCH (dis:Disease)
WHERE dis.name CONTAINS kw
MATCH (p:Plan)-[:TARGETS]->(dis)
MATCH (p)-[:INCLUDES]->(drug:Drug)
RETURN dis.name AS disease, dis.icd AS icd, p.name AS plan, p.line AS line,
       collect(DISTINCT drug.generic_name) AS drugs
ORDER BY dis.name, p.line
"""

DISEASE_GRAPH_CYPHER = """
MATCH (dis:Disease)
WHERE ($keyword <> '' AND dis.name CONTAINS $keyword)
   OR ($icd <> '' AND dis.icd = $icd)
OPTIONAL MATCH (dis)-[:SUBCLASS_OF*0..1]->(parent:Disease)
OPTIONAL MATCH (p:Plan)-[:TARGETS]->(dis)
OPTIONAL MATCH (p)-[:INCLUDES]->(plan_drug:Drug)
OPTIONAL MATCH (direct_drug:Drug)-[t:TREATS]->(dis)
OPTIONAL MATCH (direct_drug)-[ci:CONTRAINDICATED_FOR]->(cond:Condition)
RETURN dis.id AS disease_id, dis.name AS disease_name, dis.icd AS icd,
       collect(DISTINCT {id: parent.id, name: parent.name}) AS parents,
       collect(DISTINCT {id: p.id, name: p.name, line: p.line, source: p.source,
           evidence_level: p.evidence_level}) AS plans,
       collect(DISTINCT {id: plan_drug.id, generic_name: plan_drug.generic_name,
           brand_name: plan_drug.brand_name, via: 'plan'}) AS plan_drugs,
       collect(DISTINCT {id: direct_drug.id, generic_name: direct_drug.generic_name,
           brand_name: direct_drug.brand_name, line: t.line, source: t.source, via: 'treats'}) AS direct_drugs
"""

DRUG_GRAPH_CYPHER = """
MATCH (drug:Drug)
WHERE drug.generic_name CONTAINS $drug_name OR drug.brand_name CONTAINS $drug_name
   OR EXISTS { MATCH (drug)-[:HAS_ALIAS]->(a:Alias) WHERE a.name CONTAINS $drug_name }
OPTIONAL MATCH (drug)-[t:TREATS]->(dis:Disease)
OPTIONAL MATCH (p:Plan)-[:TARGETS]->(dis)
OPTIONAL MATCH (p)-[:INCLUDES]->(included:Drug)
OPTIONAL MATCH (drug)-[inter:INTERACTS_WITH]-(other:Drug)
OPTIONAL MATCH (drug)-[c:CAUSES]->(ae:AdverseEffect)
RETURN drug.id AS drug_id, drug.generic_name AS drug_name, drug.brand_name AS brand_name,
       collect(DISTINCT {id: dis.id, name: dis.name, icd: dis.icd}) AS diseases,
       collect(DISTINCT {id: p.id, name: p.name, line: p.line}) AS plans,
       collect(DISTINCT {id: included.id, generic_name: included.generic_name,
           brand_name: included.brand_name}) AS related_drugs,
       collect(DISTINCT {id: other.id, generic_name: other.generic_name,
           severity: inter.severity}) AS interactions,
       collect(DISTINCT {name: ae.name, severity: c.severity}) AS adverse_effects
"""

LIST_DISEASES_CYPHER = """
MATCH (d:Disease)
WHERE d.category <> '分类' OR d.category IS NULL
RETURN d.name AS name, d.icd AS icd, d.category AS category
ORDER BY d.name
"""

LIST_DRUGS_CYPHER = """
MATCH (d:Drug)
OPTIONAL MATCH (d)-[:HAS_ALIAS]->(a:Alias)
RETURN d.generic_name AS name, d.brand_name AS brand,
       collect(a.name) AS aliases
ORDER BY d.generic_name
"""

STATS_CYPHER = """
MATCH (d:Drug) WITH count(d) AS drugs
MATCH (dis:Disease) WITH drugs, count(dis) AS diseases
MATCH (p:Plan) WITH drugs, diseases, count(p) AS plans
MATCH ()-[t:TREATS]->() WITH drugs, diseases, plans, count(t) AS treats
MATCH ()-[i:INTERACTS_WITH]-() WITH drugs, diseases, plans, treats, count(i)/2 AS interactions
MATCH ()-[c:CONTRAINDICATED_FOR]->() WITH drugs, diseases, plans, treats, interactions, count(c) AS contraindications
MATCH ()-[a:CAUSES]->() WITH drugs, diseases, plans, treats, interactions, contraindications, count(a) AS adverse_effects
MATCH ()-[inc:INCLUDES]->() RETURN drugs, diseases, plans, treats, interactions, contraindications, adverse_effects, count(inc) AS includes
"""

PATH_CYPHER = """
MATCH (a:Drug), (b:Drug)
WHERE (a.generic_name CONTAINS $drug_a OR a.brand_name CONTAINS $drug_a)
  AND (b.generic_name CONTAINS $drug_b OR b.brand_name CONTAINS $drug_b)
MATCH path = shortestPath((a)-[*..6]-(b))
RETURN [n IN nodes(path) | {
    labels: labels(n),
    name: coalesce(n.generic_name, n.name, n.id)
}] AS nodes,
length(path) AS length
LIMIT 5
"""
