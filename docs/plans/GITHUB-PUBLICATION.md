# Private GitHub publication, approved 2026-11-02

Ryan authorized the publication preparation steps and confirmed execution after
choosing MIT. Target: authenticated personal account RyanJBush, private repository
litmus. Preserve existing history and frozen E/F/G artifacts. This does not
authorize changing repository visibility to public or deploying a web service.

Scope: license, installation instructions, all-reachable-history pattern/path
audit, synthetic CUDA/C2PA HTTP interface checks, fresh-source wheel install,
relevant model-free tests and immutable-evidence verification, Claude advisory
review, commit and private push. No data/model downloads, held-out text access,
threshold changes, calibration or frozen source edits.

## Privacy and audit disposition

Baseline history scan: 689 blobs, 73 commits and 408 trees, totaling 35,222,780
bytes across all object types. A final audit runs after commit, before push,
with its output saved outside the repository to avoid a self-referential receipt.
Only master and the named recovery tag are pushed; tool checkpoint refs stay local.
Patterns
covered common OpenAI/Anthropic/GitHub/AWS tokens, private-key PEM headers and
credential-bearing HTTP URLs. Only the two documented generated test signing
keys matched. No models directory, safetensors, train.csv, data/raid or dotenv
paths were found. This pattern/path audit is not proof that arbitrary unknown
secret formats or dataset text hidden under another path are absent.

Published evidence is metadata, scores and constructed inputs; locally held
RAID text blobs and weights remain ignored. Existing commit author identity
includes Ryan's email; historical evidence includes the Windows username/local
paths. These are preserved for the authorized private repository, not silently
redacted or rewritten. Review them explicitly before any public release. No
collaborators are added by this publication.

## Scope of verification and remaining limitations

The real production HTTP server analyzed only len512_00.txt (twice) and the
constructed active_ai_declared.jpg fixture. Both CUDA reports were identical,
score 1.0038838386535645, accepted configuration/calibration applied, and matched
the frozen synthetic preflight. C2PA returned inconclusive with valid integrity
and claim signature, unknown signer trust, absent timestamp and zero anchors.
No real TSA validation claim. Saved JSON reports pass the same explicit
validation without rerunning analysis (`verify_ui_engines.py --verify-saved`).

Fresh-source snapshot wheel build/install and isolated UI/CLI smoke passed
without downloads, using the existing pinned runtime dependencies. This is not
a claim that fresh dependency downloads or arbitrary GPU machines were tested.

The publication checks exposed a Windows malformed-request reset: 4 failures
in 100 repetitions. Closing-order changes alone did not fix it; rejected
Transfer-Encoding requests had no usable Content-Length, so the old path did
not drain the body. The error handler now flushes JSON, drains raw bytes under
64 KB and a 50 ms absolute deadline, then half-closes. The 100-request regression
and 33 UI tests pass. This regression is probabilistic, not proof of absence of
all timing failures. Rejections with large bodies may still surface as a
generic network error because draining is deliberately bounded. Final engine
reports in ui_engine_reports_final.json were captured after this repair.

Low-priority observations from Claude's original review remain tracked here:
single-thread HTTP upload uses a per-operation timeout (a local slow sender can
block requests); unexpected handler exceptions may close a connection instead
of returning JSON 500; format characters can alter filename display; Windows
temporary cleanup may fail under external file locks. These are disclosed local
single-user limitations, not fixed in this publication slice. No public server
hosting is supported. The historical evaluation driver remains unsupported;
checking out its old scoring revision and manually running it while local
held-out blobs remain present can permit rescoring. Do not do that. Original
transfer-cap compliance remains unproven under the accepted narrow exception.

No full accessibility audit, alternate hardware run, full slow suite or complete
native C2PA regression suite is claimed. The previously recorded scientific
results and evidence remain unchanged.
