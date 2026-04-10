package aegion.governance

# Default deny
default allow = false
default deny_reason = "Policy denied by default"

# Allow T0 (Auto-Approve) if conditions met
allow {
    input.tier == "T0"
    input.impact_score < 10
}

# Allow T1 (Single Approval) if valid approver count >= 1
allow {
    input.tier == "T1"
    count(input.approvals) >= 1
    evidence_valid
}

# Allow T2 (Architect Review) if valid approver count >= 1 AND one is architect
allow {
    input.tier == "T2"
    count(input.approvals) >= 1
    has_architect_approval
    evidence_valid
}

# Allow T3 (Admin Only) if valid approver count >= 1 AND one is admin
allow {
    input.tier == "T3"
    count(input.approvals) >= 1
    has_admin_approval
    evidence_valid
}

# Helper: Check for architect role in approvals
has_architect_approval {
    some i
    input.approvals[i].role == "architect"
}

# Helper: Check for admin role in approvals
has_admin_approval {
    some i
    input.approvals[i].role == "admin"
}

# Helper: Validate evidence requirements based on tier
evidence_valid {
    input.tier == "T0"
}
evidence_valid {
    input.tier == "T1"
    count(input.evidence) >= 1
}
evidence_valid {
    input.tier == "T2"
    count(input.evidence) >= 2
}
evidence_valid {
    input.tier == "T3"
    count(input.evidence) >= 3
}

# Denial reasons
deny_reason = "Insufficient approvals for tier" {
    not allow
    input.tier == "T1"
    count(input.approvals) < 1
}

deny_reason = "Missing architect approval for T2" {
    not allow
    input.tier == "T2"
    not has_architect_approval
}

deny_reason = "Missing admin approval for T3" {
    not allow
    input.tier == "T3"
    not has_admin_approval
}

deny_reason = "Insufficient evidence provided" {
    not allow
    not evidence_valid
}
