"""Rule-based knowledge graph Q&A."""

import re
from typing import Any, Callable


def _extract_drug_names(text: str) -> list[str]:
    patterns = [
        r"(?:药|药物)?[：:]?\s*([\u4e00-\u9fa5A-Za-z0-9]+)",
        r"([\u4e00-\u9fa5]{2,8})(?:和|与|跟)",
        r"(?:和|与|跟)([\u4e00-\u9fa5]{2,8})",
    ]
    names: list[str] = []
    for pattern in patterns:
        names.extend(re.findall(pattern, text))
    return list(dict.fromkeys(n for n in names if len(n) >= 2))


def _extract_disease(text: str) -> str:
    m = re.search(r"(?:疾病|病|诊断)[：:]?\s*([\u4e00-\u9fa5]{2,10})", text)
    if m:
        return m.group(1)
    for kw in ["高血压", "糖尿病", "高脂血症", "冠心病", "胃食管反流", "心绞痛", "动脉粥样硬化"]:
        if kw in text:
            return kw
    return ""


def answer_question(
    question: str,
    resolve_drugs: Callable[[str], list[dict[str, Any]]],
    check_interactions: Callable[[list[str]], dict[str, Any]],
    recommend: Callable[[str, str], dict[str, Any]],
    drug_info: Callable[[str], dict[str, Any]],
    check_contraindications: Callable[[list[str], str], dict[str, Any]],
) -> dict[str, Any]:
    q = question.strip()
    if not q:
        return {"question": q, "intent": "unknown", "answer": "请输入问题。", "data": {}}

    if any(k in q for k in ["相互作用", "一起吃", "联用", "能否同时", "能不能一起"]):
        drugs = _extract_drug_names(q)
        if len(drugs) < 2:
            return {
                "question": q,
                "intent": "interaction_check",
                "answer": "请提供至少两种药品名称，例如：「阿司匹林和氯吡格雷能一起吃吗？」",
                "data": {},
            }
        resolved = []
        for name in drugs[:4]:
            resolved.extend(resolve_drugs(name))
        drug_ids = list(dict.fromkeys(d["id"] for d in resolved))
        if len(drug_ids) < 2:
            return {
                "question": q,
                "intent": "interaction_check",
                "answer": f"未能识别足够的药品，请检查名称：{', '.join(drugs)}",
                "data": {"mentioned": drugs},
            }
        result = check_interactions(drug_ids)
        interactions = result.get("interactions") or []
        duplicates = result.get("duplicate_classes") or []
        if not interactions and not duplicates:
            answer = "未发现已知显著相互作用或同类重复用药，但仍需结合临床情况评估。"
        else:
            parts = []
            for item in interactions:
                sev = {"major": "严重", "moderate": "中等", "minor": "轻微"}.get(item["severity"], item["severity"])
                parts.append(f"{item['drug_a']} 与 {item['drug_b']}：{sev} — {item['description']}。建议：{item['recommendation']}")
            for dup in duplicates:
                parts.append(f"同类重复：{', '.join(dup['drugs'])}（ATC {dup['atc_code']} {dup['atc_name']}）")
            answer = "\n".join(parts)
        return {"question": q, "intent": "interaction_check", "answer": answer, "data": result}

    if any(k in q for k in ["禁忌", "能不能用", "可以用吗", "能用吗"]) and any(
        k in q for k in ["妊娠", "怀孕", "肝", "肾", "溃疡"]
    ):
        drugs = _extract_drug_names(q)
        condition = ""
        for kw in ["妊娠期", "怀孕", "活动性肝病", "严重肾功能不全", "消化性溃疡", "心动过缓"]:
            if kw in q:
                condition = kw.replace("怀孕", "妊娠期")
                break
        drug_ids = []
        for name in drugs[:3]:
            drug_ids.extend(d["id"] for d in resolve_drugs(name))
        drug_ids = list(dict.fromkeys(drug_ids))
        if not drug_ids:
            return {"question": q, "intent": "contraindication_check", "answer": "未能识别药品，请明确药品名称。", "data": {}}
        result = check_contraindications(drug_ids, condition)
        items = result.get("contraindications") or []
        if not items:
            answer = f"知识库中未发现与「{condition or '指定条件'}」相关的禁忌记录（不代表绝对安全）。"
        else:
            answer = "\n".join(
                f"{i['drug']} — {i['condition']}（{i['severity']}）：{i['description']}" for i in items
            )
        return {"question": q, "intent": "contraindication_check", "answer": answer, "data": result}

    if any(k in q for k in ["推荐", "治疗", "方案", "用什么药"]):
        disease = _extract_disease(q)
        if not disease:
            return {"question": q, "intent": "recommend", "answer": "请说明疾病名称，例如：「高血压推荐什么方案？」", "data": {}}
        result = recommend(disease, "")
        if not result.get("count"):
            return {"question": q, "intent": "recommend", "answer": f"未找到「{disease}」的治疗方案。", "data": result}
        lines = []
        for item in result["results"][:5]:
            drugs = "、".join(d["generic_name"] for d in item.get("drugs") or [])
            line = {"first": "一线", "second": "二线"}.get(item.get("line"), item.get("line", ""))
            lines.append(f"{item['plan']}（{line}，证据等级{item.get('evidence_level', '-')}）：{drugs}")
        answer = f"「{disease}」推荐方案：\n" + "\n".join(lines)
        return {"question": q, "intent": "recommend", "answer": answer, "data": result}

    if any(k in q for k in ["适应症", "治什么", "用于什么", "作用"]):
        drugs = _extract_drug_names(q)
        name = drugs[0] if drugs else q.replace("的适应症", "").replace("治什么", "").strip()
        try:
            result = drug_info(name)
        except Exception:
            return {"question": q, "intent": "drug_info", "answer": f"未找到药品「{name}」。", "data": {}}
        diseases = result["results"][0].get("diseases") or []
        if not diseases:
            answer = f"「{name}」暂无适应症记录。"
        else:
            dis_list = "、".join(d["disease"] for d in diseases if d.get("disease"))
            answer = f"「{name}」适应症：{dis_list}"
        return {"question": q, "intent": "drug_info", "answer": answer, "data": result}

    return {
        "question": q,
        "intent": "unknown",
        "answer": "支持的问题类型：① 两药能否联用 ② 疾病推荐方案 ③ 药品适应症 ④ 禁忌查询。示例：「阿司匹林和氯吡格雷能一起吃吗？」",
        "data": {},
    }
