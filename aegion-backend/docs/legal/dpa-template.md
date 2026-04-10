# Data Processing Agreement (DPA) Template

**Document ID**: LEG-DPA-001
**Version**: 1.0
**Effective Date**: [DATE]

---

## 1. Definitions

- **Controller**: The Customer using the Aegion platform.
- **Processor**: Aegion Inc.
- **Subprocessors**: Third-party services listed in `subprocessors.md`.
- **Personal Data**: Any information relating to an identified or identifiable natural person.

## 2. Subject Matter & Duration

- **Subject Matter**: Processing of Personal Data to provide the Aegion Governance & Intelligence Platform.
- **Duration**: Term of the Master Services Agreement (MSA) plus retention period.

## 3. Nature and Purpose of Processing

The Processor will process Personal Data only for:
1. Providing the Service (Graph reasoning, governance workflow, analytics).
2. Improving security and preventing abuse (Fraud detection, rate limiting).
3. Complying with legal obligations.

## 4. Data Protection Measures

The Processor implements the following security measures (CC1-CC9):
- **Encryption**: AES-256-GCM for data at rest, TLS 1.3 for data in transit.
- **Access Control**: Role-Based Access Control (RBAC), Multi-Factor Authentication (MFA).
- **Isolation**: Tenant isolation via Row-Level Security (RLS) and cryptographic separation.
- **Audit**: Hash-chained, immutable audit logs retained for 7 years.
- **AI Safety**: PII redaction before processing by AI models.

## 5. Subprocessors

The Controller authorizes the engagement of Subprocessors listed in the Subprocessor List. The Processor shall:
- Ensure Subprocessors are bound by written agreements with equivalent data protection obligations.
- Notify the Controller of any changes to the Subprocessor List 30 days in advance.

## 6. Data Subject Rights

The Processor shall assist the Controller in fulfilling Data Subject Request (DSR) obligations:
- **Right to Access**: Retrieve user data via API.
- **Right to Erasure**: "Right to be Forgotten" deletes user data from active stores and backups (30-day lifecycle).
- **Right to Rectification**: Correct inaccuracies via user profile tools.

## 7. Data Breach Notification

In the event of a Personal Data Breach, the Processor shall:
- Notify the Controller without undue delay (within 72 hours).
- Provide details of the breach nature, likely consequences, and remediation measures.

## 8. International Transfers

Data resides primarily in [REGION]. Cross-border transfers are protected by Standard Contractual Clauses (SCCs) or Data Privacy Framework (DPF) certification.

---

**Signed for Processor**: _______________  **Date**: __________
**Signed for Controller**: _______________  **Date**: __________
