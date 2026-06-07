// Disease -> Plan -> Drug (with dosage)
MATCH (dis:Disease)
WHERE dis.name CONTAINS $keyword OR dis.icd = $icd
MATCH (p:Plan)-[:TARGETS]->(dis)
MATCH (p)-[:INCLUDES]->(drug:Drug)
OPTIONAL MATCH (drug)-[dos:HAS_DOSAGE_FOR]->(dis)
RETURN dis.name AS disease, dis.icd AS icd, p.name AS plan, p.line AS line,
       p.evidence_level AS evidence, collect(DISTINCT drug.generic_name) AS drugs,
       collect(DISTINCT dos.dose + ' ' + dos.frequency) AS dosages
ORDER BY p.line, p.name;

// Drug interaction check
UNWIND $drug_ids AS did
MATCH (d:Drug {id: did})
WITH collect(d) AS drugs
UNWIND drugs AS a UNWIND drugs AS b
WITH a, b WHERE id(a) < id(b)
MATCH (a)-[r:INTERACTS_WITH]-(b)
RETURN a.generic_name AS drug_a, b.generic_name AS drug_b,
       r.severity AS severity, r.description AS description;

// Contraindications for a drug
MATCH (d:Drug)-[r:CONTRAINDICATED_FOR]->(c:Condition)
WHERE d.generic_name CONTAINS $drug_name
RETURN d.generic_name AS drug, c.name AS condition,
       r.severity AS severity, r.description AS description;
