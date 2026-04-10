# Data Protection Impact Assessment (DPIA)

**Project**: Aegion AI Governance
**Date**: [DATE]
**Status**: DRAFT

## 1. Project Description
Aegion is a governance platform that uses AI to analyze organizational data (proposals, graphs) and assist in decision-making.

## 2. Necessity & Proportionality
- **Purpose**: To automate governance scaling and reduce decision fatigue.
- **Benefit**: Faster decisions, higher compliance, reduced human error.
- **Data Minimization**: Only relevant workspace data is processed. PII is redacted.

## 3. Risk Assessment (AI Specific)

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **Bias in Decision Support** | High | Low | AI is advisory only; human must sign decision. Logic transparency. |
| **Hallucination** | Medium | Medium | Grounding in Knowledge Graph. Citation requirements. |
| **Prompt Injection** | High | Low | Injection detection layer. Governance-aware classification. |
| **Training Data Leakage** | High | Low | Zero-retention contracts. PII redaction. Context window filtering. |

## 4. Stakeholder Consultation
- **Legal**: Approval pending DPA review.
- **Security**: Penetration test scheduled.
- **Product**: Feature bounds defined (no automated firing/hiring).

## 5. Outcome
- [ ] Approved
- [ ] Approved with conditions
- [ ] Rejected

**DPO Signature**: ___________________
