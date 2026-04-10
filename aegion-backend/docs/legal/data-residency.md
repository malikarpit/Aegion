# Data Residency & Sovereignty

## primary Region

Unless otherwise configured, Aegion hosts data in:
- **Primary**: AWS US-East-1 (N. Virginia)
- **Backup**: AWS US-West-2 (Oregon)

## Supported Regions

Enterprise customers may pin data to specific geographies:

| Region | Providers | Compliance |
|---|---|---|
| **United States** | AWS `us-east-1` | SOC2, HIPAA |
| **European Union** | AWS `eu-central-1` (Frankfurt) | GDPR |
| **United Kingdom** | AWS `eu-west-2` (London) | UK GDPR |
| **APAC** | AWS `ap-southeast-1` (Singapore) | CBPR |

## Cross-Border Transfers

- **EU to US**: Protected via Data Privacy Framework (DPF) self-certification and SCCs.
- **Regional Isolation**: " Sovereign" workspaces guarantee data never leaves the selected region (requires Enterprise plan).

## Data Types by Location

| Data Type | Storage Location | Notes |
|---|---|---|
| **Graph Data** | Neo4j (In-Region) | Encrypted at rest |
| **File Blobs** | S3 (In-Region) | Encrypted at rest |
| **Vectors** | Vector DB (In-Region) | Encrypted at rest |
| **Identity** | Global (Auth0) | IdP is global resource |
| **Billing** | US (Stripe) | Payment data processed in US |
| **Audit Logs** | Global (S3 Replication) | Immutable archive replicated for DR |
