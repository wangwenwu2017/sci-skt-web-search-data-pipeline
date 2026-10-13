---
name: sci-task-synthesis
description: Explore related papers, code, data and scientific notes to generate source-grounded Harbor tasks through Author, Builder and Reviewer. Prepare PACKAGE.md packages and real Harbor pipeline inputs.
---

# Sci task synthesis

## Capability

Choose Sci when the supplied scientific material supports exploring a verifiable problem, without a preselected reference solution or KG. Related PDFs, code, measurements and notes can be combined. Prefer SAF for inheriting a concrete reference method, Omega for its paper/KG workflow, or TB Science for abstract workflow transfer. A topic without usable supporting content is not a prepared package.

## Prepare inputs

Create one or more package directories under the run, each with `PACKAGE.md` identifying topic, sources/licenses, entry files, data conventions and relationships. Include supplied papers, code and data or accessible authorized sources; Markdown has no fixed field schema. Preserve provenance and separate source facts from design suggestions.

Write seeds JSONL with exactly one string field per row:

```json
{"package_uri":"scientific-material"}
```

Use a dedicated input root, for example `source_root: seed/sci-skt/packages` with the package in `seed/sci-skt/packages/scientific-material/`. Do not use the run root (`.`) or its ancestor: it would include native outputs in the input snapshot. Relative URIs resolve against this input root; absolute URIs must resolve to supplied packages. Place seeds JSONL at `seed/sci-skt/seeds.jsonl` and config at `seed/sci-skt/config.json`. Create JSON configuration using `mode: harbor`, `generate_skills: false`, a bounded `tasks_per_package`, and native review/revision/time budgets. See [Harbor configuration](../../../examples/pipeline/harbor.json) for supported options. Package count times `tasks_per_package` is a generation target, not guaranteed yield.

This task-synthesis integration does not expose `sci-source` discovery as a host operation. If materials are missing, report the needed sources or use an already-authorized preparation method; do not switch to mock or claim links were read when unavailable. No credentials belong in packages or JSON config.

## End-to-end entrypoint

In TTF hosted mode, submit `sci.run` with `config`, `seeds`, `source_root`, then `tasks.collect` with `pipeline: sci-skt`. The host executes the native entrypoint in the Sci environment; the planner does not run it directly. Native command semantics are:

```bash
sci-pipeline --config "$CONFIG" --seeds "$SEEDS"   --source-root "$SOURCE_ROOT" --output-root "$OUT" --env-file "$ABSENT_ENV"
```

Keep `ABSENT_ENV` nonexistent so the injected host environment is used instead of a checkout-local `.env`. The adapter enforces real Harbor mode and disables skill generation. Author designs instructions, reference solution and tests; Builder constructs and runs reference/empty/incorrect controls; Reviewer checks source grounding and evidence, with native feedback revisions. Author-only output is not completion.

## Results

Use the actual native run directory reported by the CLI. `tasks/<task-id>/result.json` provides `status`, `validated` and `task_package_uri`. Eligible results must be `accepted`, `validated: true`, and real Harbor mode, with actual Builder/Reviewer evidence. Preserve native logs, controls, rejections and partial yield. Mock success and source packages are not verified tasks. In TTF, evidence remains under `sci-skt/`; the host collects eligible tasks into `tasks/` and writes `task_manifest.json`. This is native task validation, not an independent Codex solver trajectory.
