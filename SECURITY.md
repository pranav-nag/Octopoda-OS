# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Octopoda, please report it responsibly.

**Email:** ryjoxtechnologies@gmail.com

**Please include:**
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Any suggested fixes

**Response timeline:**
- Acknowledgment: within 48 hours
- Initial assessment: within 7 days
- Fix timeline: within 90 days (coordinated disclosure)

## Scope

The following are in scope:
- Octopoda Python SDK (`pip install octopoda`)
- Octopoda Cloud API (`api.octopodas.com`)
- MCP Server
- Dashboard

## Out of Scope
- Third-party dependencies (report to their maintainers)
- Social engineering attacks
- Denial of service attacks

## Security Architecture

Octopoda implements the following security measures:

- **Password hashing:** PBKDF2-HMAC-SHA256 with 600,000 iterations
- **API key storage:** SHA-256 hashed (keys are never stored in plaintext)
- **Tenant isolation:** PostgreSQL Row-Level Security (RLS) at database level
- **Rate limiting:** Token-bucket per tenant (configurable by plan)
- **Brute-force protection:** Progressive lockout on authentication endpoints
- **Transport:** TLS/SSL on all API endpoints

## Responsible Disclosure

We ask that you:
- Allow us reasonable time to fix the issue before public disclosure
- Avoid accessing or modifying other users' data
- Act in good faith to avoid disruption to our service

We will not pursue legal action against researchers who follow this policy.
