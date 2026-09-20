# MVP Run Results (2026-08-18)

> 说明：以下数字记录的是 canonical Skill / Recipe 契约定稿前的链路原型实验，不代表这些
> JSONL 已通过正式 schema。原型数据保留作迁移输入；正式语料将从本地准确的 ALE 60 cards
> 重新抽取并验证。

> 当前边界：下文保留各次实验的实际配置，包括早期向 Solver 提供 Skills 的做法。正式生产现已采用 Recipe / Scientific Skills 不可见的容器内交互执行，见[第十二章](design/12-interactive-container-rollout.md)。

## ALE 60-card seed

| Measurement | Result |
| --- | ---: |
| Raw task cards | 60 |
| Scientific Skills | 60 |
| Procedure steps mapped directly | 260 |
| Input descriptors mapped directly | 247 |
| Explicit output paths extracted | 86 |
| Cards with no safely extractable output path | 14 |
| Candidate tasks | 240 (60 per TaskGen mode) |

ALE tier labels in the seed are 24 `near-term`, 21 `full-spectrum`, 14 `last-exam`, and one
unlabelled card. Domains are 23 `computing_math`, 21 `business_finance`, 10 `engineering`, four
`education_info`, and two `agriculture_env`.

All 240 generated tasks remain drafts because no public card supplies an executable evaluator in
metadata. The conservative authoring findings are:

- 240 `missing_executable_evaluator`;
- 60 `missing_control_variable` for the controlled-variable overlay;
- 60 `missing_recovery_playbook` for diagnostic-recovery;
- three `insufficient_procedure_stages` for multi-stage generation.

This is a useful result rather than a conversion failure: it identifies exactly which scientific
authoring work is needed instead of filling gaps with model guesses.

## Executable smoke task

The bundled two-group statistics task passed the implemented `reference_execution_mvp` gate:

- hidden reference ran from a clean workspace and scored `1.0`;
- solver workspace received only `visible/` and `skills/`, never `hidden/`;
- two independent retries received different `fresh_context_id` values;
- trajectory achieved full evaluator credit and normal termination;
- required skill was accessed before its declared formula/ordering affected computation;
- output artifact hash and event trace were retained;
- verified trajectory exported with assistant tokens trainable and context/tool observations masked.

The full task-side semantic LLM verifier, paired skill-dependence test, N=5 difficulty controller,
and production trajectory LLM validator remain `not_run`; passing the smoke profile is not presented
as passing full SKT qualification.

## Canonical Chapter 6 trajectory (2026-08-21)

The current file-first pipeline has replaced the earlier generic smoke trajectory for production
experiments. Verified Task Package `sha256:b1dad93e…c35595` was given to a fresh
`gpt-5.6-sol` Solver through `codex-batch-docker/0.1.0`. The first attempt authored an independent
Python submission from the public Task Card, controlled inputs, and two Scientific Skills, then ran
that submission once in the verified no-network Docker runtime.

- the Solver session completed normally and produced 39 native events;
- all 14 started tool calls had completed results and no verifier-only path access was observed;
- Docker execution returned `0` and produced the two required artifacts;
- all eight evaluator checks passed with score `1.0`;
- all 12 deterministic trajectory components passed;
- a fresh Trajectory Reviewer accepted task-result correspondence, scientific process validity,
  and trace credibility with no blockers;
- the promoted trajectory digest is `sha256:0582b2a6…b81325b`.

The complete immutable attempt and independent verification evidence are stored in
`runs/chapter-06/ale-ndvi-trajectory-001`. The current batch adapter's model-authoring session is
audited with Codex `workspace-write`; task-program execution has strict Docker isolation. Strong
read-namespace isolation for the authoring session remains an explicit adapter improvement.

## Canonical Chapter 7 dataset release (2026-08-24)

The Chapter 6 promotion record was curated into the first immutable Raw + SFT release without a new
LLM judgment. Eligibility rechecked the frozen attempt, full evaluator score, accepted scientific
process review, prompt digest, Task Package digest, Accepted Knowledge digest, native trace, and
artifact bytes. The Raw layer stores workspace-relative locators and digests, while the target SFT
layer contains 34 ordered messages rendered with `o200k_base` and a token-level loss mask.

- one input trajectory produced one Raw record and one SFT record;
- 39 native events, 42 public events, and two output artifacts remain linked by digest;
- the record contains 18,106 tokens: 5,614 supervised and 12,492 conditioning tokens;
- two path-only Codex file-change events are represented by the exact frozen terminal batch
  submission, including the authored UTF-8 file content;
- no record exceeded the 65,536-token limit, and no truncation occurred;
- all 11 release qualification components passed, including information-boundary and tamper checks;
- release digest: `sha256:058419d48ddae3c522638c3209714d2f5c745199c1ae4f3b21a68ef16006e3d8`.

The release is stored at `runs/chapter-07/scientific-agent-trajectories-0.1.0` and remains marked
`internal_research_only`. This one-task release validates the data contract and serializer; it does
not measure training gains or scientific-domain coverage.

## 20-source scientific batch (2026-08-25)

The repository-source batch has now exercised the complete Knowledge → Task Author → Task
Verification/Repair → Fresh Rollout → Trajectory Verification → Dataset path on real scientific
software tasks. The resumable downstream manifest currently records:

| Stage | Passed | Blocked | Failed | Pending |
| --- | ---: | ---: | ---: | ---: |
| Task authoring | 14 | 0 | 0 | 6 |
| Task verification | 10 | 4 | 0 | 6 |
| Trajectory | 9 | 0 | 1 | 10 |

The nine verified trajectories cover Astropy, celerite2, MDAnalysis, MDTraj, RDKit, SELFIES,
Harmonica, Xarray, and QuTiP recipes. MDAnalysis demonstrated a complete semantic repair loop: the
Task Reviewer found that JSON booleans could compare equal to integer identifiers, TaskRepair added
type-aware evaluator checks and a dedicated mutation, the repaired task passed executable and
semantic verification, and a fresh Solver received score `1.0` before Trajectory Reviewer
acceptance. SELFIES separately exercised repeated failed-rollout diagnosis followed by task repair
and a successful fresh rollout.

The four blocked task verifications are Scanpy PBMC, MetPy sounding visualization, Matminer, and
Pymatgen. They retain their complete repair histories and stop at explicit repair budgets. Phonopy
passed Task Verification; two fresh Solvers exhausted the rollout budget, and both Trajectory
Reviewers attributed failure to incomplete Solver recovery rather than a Task Package defect.

MetPy exposed a reusable verification-policy requirement. Evaluator cases now support
`maximum_score` for invalid outputs that must be rejected and `minimum_score` for scientifically
valid equivalence outputs that must be accepted. Existing policies remain compatible. Generated
Python caches are removed from candidate packages before authoring qualification, preventing
runtime self-check artifacts from appearing as intentional task changes.

## Batch dataset release 0.1.2 (2026-08-25)

All nine verified trajectories were curated into an immutable Raw + SFT release. No blocked or
failed item enters the release.

- 9 verified trajectories produced 9 SFT records;
- 31 artifacts, 209 native events, and 236 public events remain linked by digest;
- the release contains 123,445 tokens: 40,321 supervised and 83,124 conditioning tokens;
- no duplicate, per-task-limit, or overlength exclusion occurred;
- all 11 qualification components passed during build and independent disk verification;
- release digest: `sha256:a0e097f204f6aae206203d5939e0eea51309ec16e045b31622ceeb0e51428133`.

The release is stored at
`runs/batches/scientific-20-v1/07-dataset/scientific-agent-trajectories-20-mvp-0.1.2` and remains
`internal_research_only` while source-specific redistribution status is reviewed.
