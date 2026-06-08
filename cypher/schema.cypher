CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT disease_id IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT plan_id IF NOT EXISTS FOR (p:Plan) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT atc_code IF NOT EXISTS FOR (a:AtcClass) REQUIRE a.code IS UNIQUE;
CREATE INDEX drug_generic_name IF NOT EXISTS FOR (d:Drug) ON (d.generic_name);
CREATE INDEX drug_brand_name IF NOT EXISTS FOR (d:Drug) ON (d.brand_name);
CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name);
CREATE INDEX disease_icd IF NOT EXISTS FOR (d:Disease) ON (d.icd);
