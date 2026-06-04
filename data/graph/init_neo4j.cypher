CREATE CONSTRAINT company_name_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.name IS UNIQUE;

MERGE (audit:Company {name: "华辰智能装备股份有限公司"})
SET audit.industry = "智能装备制造", audit.listed = true;

MERGE (supplier:Company {name: "启明供应链管理有限公司"})
SET supplier.industry = "供应链服务";

MERGE (factor:Company {name: "远航商业保理有限公司"})
SET factor.industry = "商业保理";

MERGE (material:Company {name: "海岳新材料有限公司"})
SET material.industry = "新材料";

MERGE (controller:Person {name: "张某"})
SET controller.role = "疑似实际控制人";

MERGE (audit)-[:CONTROLLED_BY {ratio: 0.31, hidden: false}]->(controller);
MERGE (supplier)-[:CONTROLLED_BY {ratio: 0.26, hidden: true}]->(controller);
MERGE (audit)-[:HAS_RECEIVABLE_FROM {amount: 26800000, hidden: true}]->(factor);
MERGE (audit)-[:PURCHASES_FROM {amount: 48300000, hidden: true}]->(material);
MERGE (material)-[:RELATED_TO {reason: "高管交叉任职", hidden: true}]->(controller);

