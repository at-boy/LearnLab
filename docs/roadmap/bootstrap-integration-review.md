# Bootstrap integration review

Reviewed 2026-10-04. Independent review of the fixed 6,948-line integration diff, `0da669f06e39288bc47ee4f94a5326847503627c..7ae9939ba3611afb05d7fab203756e2135abd2e0` (27 commits). The review covers the NixOS corrections, provider-bootstrap curriculum, shared documentation, tests, and evidence reports. Later Debian work is outside this verdict.

## Verdicts

- **Spec compliance: changes requested for one P2 integration defect.** The major safety, NONE-isolation, and certification requirements are satisfied, but the new TLS fallback is not carried into the required scratch lifecycle.
- **Quality: changes requested for the same P2 defect.** No P0/P1 safety or data-loss finding. The defect is a functional handoff omission, not a request to weaken TLS or perform live work.
- **Live readiness: still draft.** Passing the offline gate and resolving this finding do not complete either exact-digest live protocol.

## Finding

### P2 — Restore authenticated TLS trust in the fresh lifecycle shell

Location: `src/learnlab/collections/proxmox/courses/provider-bootstrap/lessons/06-authorize-scratch-lifecycle/lesson.yaml:35` (context: lines 22–35 and start at line 48).

The newly documented fallback stores the verified server leaf only in a process-scoped `SSL_CERT_FILE`. Lesson 05 explicitly clears that variable at line 67. Lesson 06 then requires a fresh separate shell and explicitly repopulates the token secret, but never restores `SSL_CERT_FILE`. There is no TLS trust-file profile field to supply the missing setting. A learner who needed the fallback to pass health, follows its cleanup instruction, and follows the scratch setup exactly therefore loses the trust configuration before `learnlab start`. The same process setting is needed by later provider-backed destroy and by any authorized resumed lifecycle shell.

Concrete source corroboration: `ProxmoxProvider.__init__` passes `verify=profile.tls_verify` to `httpx.Client` (`src/learnlab/providers/proxmox.py:52–55`). The installed HTTPX context builder reads `SSL_CERT_FILE` from the current process when verification is true; without it, the builder selects the default trust bundle. A previous health process cannot preserve its trust anchor for the fresh process. This is a deterministic instructional gap; no live endpoint or secret was needed to establish it.

Impact: the advertised fallback works for health but the following required lifecycle cannot proceed on the same certificate deployment without an undocumented correction. It fails closed; there is no demonstrated verification bypass or unsafe deletion. This is a merge-review correction because the changed TLS guidance and the existing fresh-shell lifecycle contract need to work together, not optional prose polish.

Requested correction: before scratch start, conditionally re-establish the previously authenticated owner-only trust file in this fresh shell, recheck endpoint/fingerprint/validity and rotation conditions, and export `SSL_CERT_FILE` while keeping `tls_verify = true`. Preserve it through start, destroy, and reconciliation, and include the same requirement on an authorized resume. Clear it separately from the token secret when the lifecycle shell is finished. Do not add a profile field, fetch and trust an unchecked certificate, or broaden authority. Add a focused cross-lesson regression covering the health cleanup → fresh lifecycle setup → final cleanup sequence. Refresh the provider-bootstrap digest/report after lesson bytes change and retain draft status.

## Safety and integration assessment

| Area | Assessment |
| --- | --- |
| NONE dependency boundary | The new course has eight ordered NONE lessons, empty provider/guest requirements, and only text/manual checks. Source CLI and the existing single-build installed-wheel test exercise draft gating, start/save/resume, self-attestation, and settings/secret/provider/SSH/HTTP tripwires. No production CLI/provider/lifecycle code changes occur in the reviewed range. |
| Installation and boot | The correction requires a positively stopped owned VM before changing boot order, retains recovery access, and verifies installed disk boot. Destructive installation remains deliberately learner-operated. |
| Host identity | The ext4/x86_64-only oneshot derives a four-byte hostid from machine-id, avoids a static store-backed host ID, checks input/layout, uses an owner-controlled temporary file, and refuses an existing destination. Clone acceptance checks distinctness and reboot persistence. Tests execute the extracted script in a temporary filesystem and cover invalid input, unsafe layouts, write failures, and existing targets. |
| Sealing and QGA | Console recovery and full candidate inspection precede either path. Effective SSH configuration determines exact ports/key paths; both sshd and sshd-session plus listeners/connections are checked before identity mutation. Failures and reappearing identities block poweroff. Positive Proxmox Stopped state remains a separate prerequisite to conversion. No forced conversion, snapshot deletion, broad key glob, or automatic retry is introduced. Human preflight still matters: these are guided procedures, not an autonomous general-purpose sealing engine. |
| SSH trust | Trusted console/QGA public-key evidence precedes enrollment; a candidate SSH connection cannot authenticate itself. Isolated known_hosts, strict checking, disabled connection sharing, and `-F none` support a fresh explicitly configured connection. |
| TLS | The new guidance preserves verification, out-of-band authentication, SAN/issuer/validity/fingerprint checks, rotation sensitivity, and separate token-secret semantics. The lifecycle-shell omission above is the single identified integration defect. |
| Authority and cleanup | Runtime, administrator, template-builder, and validation-only actors are separated. Candidate PVE privileges are labeled unproven until installed/live confirmation. Propagated `/vms` authority is disclosed. Collision, denial, filtered inventory, and uncertain task outcomes block retries. Scratch state is isolated; ownership backup and independent cleanup confirmation precede revocation. Existing adapter limits are disclosed rather than silently asserted fixed. |
| Certification | Registry is unchanged in the reviewed range. Both reports bind current digests to reviewed content revision `c952e759…`, distinguish historical observations from current-digest proof, and leave live traversal/lifecycle/cleanup pending. Self-attestation is not promoted to certification. |

## Evidence and limits

The controller supplied fresh integration validation: **657 non-live tests passed, 1 live test deselected; Ruff and mypy passed**. The latest rerun had a pytest-cache write warning because the sandbox made that cache read-only; this is environmental, not a product failure. I did not rerun the complete suite or claim those results as independently executed. I reviewed its relevant added test coverage and inspected the local provider/HTTPX construction only to verify the concrete TLS handoff risk.

The fixed diff, both bootstrap specifications/plans, NixOS correction ledger, validation reports, and relevant source lines were inspected. The base/target commit IDs and 27-commit count were independently checked. The provider, lifecycle, CLI, and certification-registry paths have no changes in this comparison. No live/network, Proxmox, SSH, certificate-fetch, user-config, secret, ACL, VM, merge, or push operation was performed.

The NixOS report's current digest is `c1a124cf56f0ce19b8203926bde0d6e8305e71a175f823f90200318c3279dc82`; the provider-bootstrap report's is `92efd4934b2584f75e0acbc6260b8d66873f74a0da11f318e832632f2d72fda2`. These are the reviewed report values and are covered by the supplied passing digest regressions, not a new live acceptance result.

## Nonblocking documentation maintenance

Historical design headings and provider-plan checkboxes still read as planned/unchecked, while implementation/evidence documents describe completed offline work. The roadmap should reconcile those status surfaces with the committed reports without marking pending live work complete. This is status polish, not a second correctness blocker. Existing runtime limitations, unavailable current-digest live evidence, and release-specific installed permission validation are explicit scope boundaries rather than newly introduced defects.

## Scoped re-review — 2026-10-04 TLS correction

Reviewed only `.superpowers/sdd/bootstrap-tls-fix.diff`; no broad reread or test rerun. The controller reports 38 provider-bootstrap tests passing, zero catalog findings, and clean whitespace.

**Original P2 disposition: ADDRESSED.** Lesson 06 now restores independently authenticated trust before provider operations in the fresh shell, preserves it through start/recovery/destroy/reconciliation, requires restoration in a replacement shell, stops on certificate rotation/mismatch, and clears trust separately from the token secret only after independent cleanup. Verification remains enabled.

**Scoped spec verdict: TLS correction approved. Scoped quality verdict: TLS correction approved; report provenance correction still required.** The changed validation report now prints digest `d0a6c938d6c5542dcd87813b2f300283fe979df754df9f273e89a0146cbf24f1`, but its unchanged opening still calls `c952e759…` the current-digest content revision and says that revision's results and the digest below bind to those old course bytes. The new appended Oct 4 section does not remove that contradictory binding. Relabel the c952e759 results as historical and explicitly bind the new digest to the Oct 4 correction/final reviewed commit, with the new focused evidence distinguished from historical full-suite results. Live remains pending; no live action is required to correct this report.

### Final scoped disposition — provenance correction

Inspected only the validation report's first 45 lines after the header correction. The c952e759 results are now explicitly historical and excluded from the current digest; the new digest is attributed to the October 4 working-tree TLS correction with the subsequent commit to be recorded in the execution log. Current-content live acceptance remains pending. **Provenance concern: ADDRESSED. Final spec-compliance verdict: APPROVED. Final quality verdict: APPROVED.** No remaining actionable finding from this integration review. This approval covers offline integration, not live acceptance or certification; the original report and intermediate dispositions remain above as review history.
