# Vendor Risk Review Guide

## Purpose

This guide helps assemble evidence for hospital procurement, cybersecurity questionnaires, vendor risk reviews, and enterprise customer security assessments.

## Frequently Requested Artifacts

- Platform security overview: `docs/readiness-binder/security-architecture-summary.md`
- Questionnaire responses: `docs/readiness-binder/security-questionnaire-reference.md`
- Control matrix: `docs/readiness-binder/control-matrix.md`
- Residual risk register: `docs/readiness-binder/residual-risk-register.md`
- Object authorization audit: `docs/enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md`
- Deployment baseline: `docs/deployment-baseline.md`
- Security review packet: `docs/security-review-packet.md`
- Control evidence index: `docs/security-control-evidence-index.md`

## Security Review Workflow

1. Confirm review scope, environment, and customer data assumptions.
2. Share the architecture summary and questionnaire reference.
3. Map questionnaire questions to the control matrix.
4. Provide test names and PR evidence where requested.
5. Discuss residual risks using the risk register.
6. Document customer-specific deployment responsibilities.
7. Record follow-up actions and owners.

## Reviewer Contacts Placeholder

Replace these placeholders during customer review:

- Security owner: `security-owner@example.com`
- Engineering owner: `engineering-owner@example.com`
- Operations owner: `operations-owner@example.com`
- Customer success owner: `customer-success-owner@example.com`

## Evidence Package References

Evidence should include merged PRs, changed files, tests executed, validation summaries, migration records, and deployment runbook outputs. Do not include production secrets, bearer tokens, private keys, raw sensitive payloads, or customer confidential data in review packets.

## Security Documentation References

- `docs/readiness-binder/README.md`
- `docs/readiness-binder/security-questionnaire-reference.md`
- `docs/readiness-binder/control-matrix.md`
- `docs/readiness-binder/security-architecture-summary.md`
- `docs/readiness-binder/residual-risk-register.md`

## Certification Note

Use this guide for readiness and evidence collection only. Do not describe it as a SOC 2 report, HITRUST report, HIPAA certification, or third-party attestation.
