TEST ONLY. Everything in this directory was generated locally by
scripts/generate_c2pa_fixtures.py for Litmus tests (R1-D1).

- The private keys (*_key.pem) are TEST ONLY: they protect nothing and must
  never be used for signing anything outside these test fixtures.
- test_root_ca.pem is the test trust anchor. It is loaded only by tests,
  through litmus.c2pa.settings.test_anchor_config. Production configuration
  never references this directory.
- untrusted_root_ca.pem is a separate root that is never used as an anchor.
- Validity of every certificate: 2026-01-01T00:00:00Z to 2046-01-01T00:00:00Z.
- No timestamp authority was used.
