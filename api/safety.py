"""Safety guardrails for the clinical-assistance Q&A endpoint."""

from __future__ import annotations

from dataclasses import dataclass


DISCLAIMER = "本系统仅供医学知识学习与临床辅助参考，不能替代医生、药师或急救服务的判断。"
EMERGENCY_TERMS = ("胸痛", "呼吸困难", "昏迷", "抽搐", "大出血", "严重过敏", "喉头水肿", "自杀", "服药过量", "药物过量", "中毒")
REVIEW_TERMS = ("剂量", "加量", "减量", "停药", "换药", "处方", "孕妇", "怀孕", "哺乳", "儿童", "婴儿", "肝功能不全", "肾功能不全")


@dataclass(frozen=True)
class SafetyDecision:
    action: str
    level: str
    reasons: list[str]
    message: str

    def as_dict(self) -> dict[str, object]:
        return {"action": self.action, "level": self.level, "reasons": self.reasons, "message": self.message, "disclaimer": DISCLAIMER}


def assess_question(question: str) -> SafetyDecision:
    """Stop emergency requests and mark individualised medication requests for review."""
    normalized = question.casefold()
    emergency_hits = [term for term in EMERGENCY_TERMS if term in normalized]
    if emergency_hits:
        return SafetyDecision("blocked", "critical", emergency_hits, "该问题可能涉及紧急医疗风险。请立即联系当地急救服务或前往急诊，不要等待在线问答结果。")
    review_hits = [term for term in REVIEW_TERMS if term in normalized]
    if review_hits:
        return SafetyDecision("review_required", "high", review_hits, "该问题可能需要个体化处方或剂量判断。以下内容仅作知识参考，请由医生或药师结合病史、检查结果和完整用药清单确认。")
    return SafetyDecision("allowed", "standard", [], "结果来自本地知识图谱；请结合专业人员意见使用。")
