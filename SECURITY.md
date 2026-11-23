# Security status and reporting

Litmus R1 is a local single-user research/portfolio application. It is not a
hardened public web service. Keep its loopback server off public proxies.

The current draft release has unresolved dependency advisory matches. See the
[dated assessment](docs/RELEASE-READINESS.md) and
[tracking issue](https://github.com/RyanJBush/AI-Generated-Content-Detection-and-Authenticity-Analyzer/issues/1). Passing tests or
pip check does not establish absence of vulnerabilities. No supported version
is presently advertised as security-cleared for public production use.

## Reporting a concern

This repository is public. Do not disclose sensitive exploit material in a
public issue: use GitHub private vulnerability reporting from the Security tab.
General bugs may be opened as minimal issues, without credentials, private
documents, model weights or raw dataset texts.
No response-time guarantee or staffed security team is claimed.

Include the affected commit/version, relevant environment, a constructed
reproduction if safe, expected/actual behavior and impact. Avoid testing against
other people's machines or data. Never post working secrets as evidence.

## Frozen research environment

Security fixes may require dependency updates. Plan them in isolation and keep
original scientific evidence intact. New runtime identities must not silently
inherit accepted calibration. Do not run historical scoring/recovery commands
or access held-out texts to investigate a security report.
