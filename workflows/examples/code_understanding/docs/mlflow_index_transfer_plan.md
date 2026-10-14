# MLflow index import and export plan

## Current implementation scope

Implement `make list-indexes`, `make export-indexes`, and `make import-indexes`, with a local CLI and transfer wrapper. Share local MLflow gateway resolution with `make run-console-app` and remove its MLflow port-forward. Console downloads/uploads, console index discovery, the existing upload Job and prebuilt uploader, pipeline/container dependencies, and query-loader behavior are deferred. Do not change their current archive formats or behavior in this phase.

Use `mlflow-export-import` to transfer a single indexing artifact run. Adopt its native `run.json` plus `artifacts/` directory as the transfer format, packaged into a `.tar.gz`. Native archives from these targets are separate from the existing uploader's application-specific `manifest.json` format.

The wrapper owns index validation, namespace mapping, safe archive handling, limits, retry deduplication, provenance, structured output, and failure propagation. The package exports and imports run metadata and artifacts through MLflow APIs. This phase includes local tooling dependencies, Make help, documentation, and focused tests.

## Storage and selected-run scope

Indexes live in `<namespace>/code-refactoring/assets/result-directories`. Single-repository indexes use `results/datasets/repos/<git_slug>` and combined indexes use `results/datasets/repos/multi-repo`. Runs carry `category=indexing`, `git_slug`, and `multi_repo` tags. A git slug includes owner, repository, and branch, for example `agapebondservant-tic-tac-toe-sample-main`.

Export only the selected result-directory run. Preserve its parameters, metric histories, tags, supported dataset inputs, and entire artifact tree, including complete nested LanceDB files. Separate telemetry, evaluation, pipeline/status runs, registered/logged models, and Databricks notebooks are outside scope. Import does not convert GraphRAG, LanceDB, or embedding formats.

## Make targets and input contract

| Target | Inputs | Result |
| --- | --- | --- |
| `list-indexes` | Source namespace and tracking URI | Display all active `FINISHED` indexing runs in a table with repository, single/combined type, latest marker, UTC start time, and full run ID. |
| `export-indexes` | Exactly one of `INDEX_GIT_SLUG` or `INDEX_RUN_ID`; optional `INDEX_BUNDLE` | Select and validate one run, export it, and publish a native archive. |
| `import-indexes` | Required `INDEX_BUNDLE`; optional `INDEX_FORCE=true` | Validate the archive and import it, or return an existing completed destination import. |

`INDEX_GIT_SLUG` selects the active `FINISHED` single-repository indexing run with the newest start time matching the exact slug. Break equal-time ties by run ID ascending. Do not select combined indexes by repository slug. If no eligible run exists, fail clearly. If the selected run has missing/invalid artifacts, fail rather than silently falling back to an older index.

`INDEX_RUN_ID` selects that exact run, whether single-repository or combined. Validate the same experiment, lifecycle, status, tags, and artifacts. Both selectors supplied, or neither supplied, is an error. Record the resolved source run ID in the export result.

Listing marks the first run for each `(git_slug, multi_repo)` identity as latest using the same ordering. It validates metadata; export performs the full artifact validation.

`INDEX_BUNDLE` means the local archive path: optional output location on export and required input file on import. Import derives the slug and combined flag from native metadata; it does not require a selector. Default export paths are `artifacts/indexes/<git_slug>-<run_id>.tar.gz` and `artifacts/indexes/multi-repo-<run_id>.tar.gz`. Refuse to overwrite existing output, including races at publication.

Use the existing `KFP_NAMESPACE` for workspace routing. The experiment is always `<KFP_NAMESPACE>/code-refactoring/assets/result-directories`; there is no experiment override. The three index Make targets and `run-console-app` always discover the external `data-science-gateway` OpenShift Route in `openshift-ingress` and export `MLFLOW_TRACKING_URI=https://<route-host>/mlflow`, regardless of the configured tracking URI. Select the source or destination cluster with `oc login` before running these local commands. The transfer Python script simply reads its environment. Keep discovery lazy and derived variables unexported so other targets do not query Routes. Leave the existing installation `GATEWAY_HOST` unchanged, add nothing to `.env.template`, and fail clearly if Route discovery returns no host. Preserve configured token, authentication, and TLS environment settings. The 5 GiB transfer limit is fixed in the Python module.

```bash
make list-indexes KFP_NAMESPACE=source \

# Latest completed index for an exact repository-and-branch slug.
make export-indexes KFP_NAMESPACE=source \
  INDEX_GIT_SLUG=agapebondservant-tic-tac-toe-sample-main

# A specific older or combined index run.
make export-indexes KFP_NAMESPACE=source \
  INDEX_RUN_ID=<source-run-id> \
  INDEX_BUNDLE=artifacts/indexes/combined.tar.gz

make import-indexes KFP_NAMESPACE=destination \
  INDEX_BUNDLE=artifacts/indexes/combined.tar.gz
```

Each invocation uses credentials for its chosen cluster. A local import reads the archive directly; it does not stage files for the existing installation Job.

## Native archive format

Package the native directory at the archive root without an enclosing folder:

```text
run.json
artifacts/
  results/datasets/repos/<git_slug>/
    communities.parquet
    entities.parquet
    context.json
    lancedb/
      ... complete nested files ...
    ... remaining index files ...
```

Combined indexes instead use `artifacts/results/datasets/repos/multi-repo/`. Do not flatten the hierarchy or introduce an application manifest. Require a nonempty index directory; specific GraphRAG files depend on the version and indexing configuration.

The pinned package writes export schema version `2`, with top-level `system` and `mlflow` envelopes. Validate this version, source run info/status/lifecycle, indexing tags, string parameters/tags, metric histories, and supported dataset inputs before importing. Reject missing, malformed, unsupported, or duplicate JSON fields.

## Wrapper and CLI

Implement `code_understanding.utils.index_transfer` and `scripts/transfer_index.py` with `list`, `export`, and `import` commands. Read namespace and endpoint from `KFP_NAMESPACE` and `MLFLOW_TRACKING_URI`, derive the standard experiment, and enforce fixed limits in Python; do not import console or FastAPI modules or perform endpoint discovery in Python. The CLI reads exported Make variables and also accepts selector/bundle/force command-line options. Listing displays a table and ignores pipeline `ARGS`. Export retains the download progress bar and displays index identity, type, source run ID, namespace, and `Index saved to "<path>"`; suppress routine package logging and dependency installation chatter. Import results remain JSON. The wrapper still returns structured results internally. Suppress `InsecureRequestWarning` in the transfer CLI without changing TLS verification settings. Diagnostics go to stderr; export errors have no success details or saved-path message. Failures exit nonzero and propagate through Make.

### Export

1. Resolve the selector and validate the selected run.
2. Recursively inventory all run artifacts. Require a nonempty canonical index path and reject unsafe paths, unknown file sizes, too many entries, or an oversized tree.
3. Call `export_run()` with the supplied client, `raise_exception=True`, and logged-model export disabled. A `None` result is failure.
4. Validate native metadata and compare the downloaded artifact paths/sizes with the source inventory. Bound the full directory including metadata.
5. Archive the complete export directory in a temporary workspace beside the destination. Check compressed size, compute SHA-256, and atomically publish without overwriting another file.

### Import

1. Bound compressed size, scan the entire archive before extraction, and reject traversal/absolute paths, duplicate members, links, special files, unexpected root entries, too many members, oversized metadata, and oversized extracted contents. Enforce the fixed 5 GiB limit for compressed and extracted transfer size. Allow adequate temporary disk space.
2. Validate native schema, source run readiness, indexing tags, and nonempty canonical artifacts before creating any destination run or experiment. Hash the original archive before metadata changes.
3. Unless forced, search for an active completed destination import with the same archive hash, slug, combined flag, destination experiment, and destination namespace. Return its run ID after verifying index artifacts exist. Failed/running imports do not deduplicate. This covers sequential retries; concurrent identical imports may create separate runs.
4. Strip `mlflow.parentRunId`, preserving its value as provenance. Replace inherited application transfer tags with `uploaded=true`, `bundle_sha256`, `index_transfer.source_run_id`, `index_transfer.source_experiment_id`, and `index_transfer.destination_namespace`. Preserve source start/end times as provenance. Inject these tags into temporary native metadata before calling the importer.
5. Call `import_run()` with the destination client and experiment, `import_source_tags=True`, logged-model import disabled, and `mlmodel_fix=False` to preserve artifact bytes.
6. Re-fetch the destination run; require a fresh run ID, active lifecycle, `FINISHED` status, expected experiment/identity/provenance, no source parent reference, and matching artifact inventory. Mark it `FAILED` if post-import validation fails, then propagate the error.

The package creates a fresh destination run with current timestamps and supported source provenance; it does not restore original start/end times. Its normal import exceptions mark the new run `FAILED`; interruptions can leave `RUNNING` runs. These targets treat only active `FINISHED` runs as completed. Updating console/query discovery readiness is deferred, so existing consumers retain their current behavior during this phase.

## Dependencies and connectivity

Pin `mlflow-export-import` commit `05ec457fc0b4acfd3cfc24433eaaab5870ac69cd`, `mlflow[kubernetes]==3.14.0`, `mlflow-skinny==3.14.0`, and `kubernetes==30.1.0` in `scripts/requirements-index-transfer.txt`. Run locally using `uv run --no-project --python 3.12 --with-requirements ...`. The Kubernetes client is pinned to the repository's pre-31 range because MLflow 3.14.0 expects kubeconfig bearer tokens under `configuration.api_key["authorization"]`; Kubernetes 37 uses `BearerToken` instead. Do not update container or console dependency sets in this phase.

Set `MLFLOW_WORKSPACE` to the selected namespace before constructing clients, and set `MLFLOW_NAMESPACE` consistently for experiment naming. Default authentication to `kubernetes-namespaced` using local kubeconfig; retain explicit auth and TLS settings.

The pinned package probes Databricks using its auxiliary HTTP client without all SDK authentication/workspace/TLS settings. A narrow self-hosted adapter temporarily sets its cached Databricks-detection result to false. With notebooks, logged models, and MLmodel rewriting disabled, native run transfer uses SDK requests and does not require auxiliary HTTP calls. Keep this package-internal adaptation tied to the reviewed commit.

Verify actual artifact URIs and gateway connectivity. Proxied artifacts use server storage access; direct S3 artifact URIs require local storage connectivity and credentials. Cluster-only artifact storage needs a later staging/Job execution design; the existing upload Job is not changed here.

## Implementation and acceptance checks

1. Update this plan for Make-only scope and dual selection.
2. Review/pin the package and implement the standalone wrapper/CLI.
3. Add Make targets, help, environment examples, ignored generated output, and transfer usage documentation.
4. Add focused unit and local MLflow REST round-trip tests; expose them through `make test-index-transfer` and include them in `make test-all`.
5. Validate source/destination configuration and available gateway connectivity. Record any checks that require cluster write access or application runtime configuration and were not performed.

Cover latest slug selection, exact run selection, combined indexes, old runs, pagination, equal-time ordering, invalid selector combinations, wrong experiment/category, deleted/unfinished runs, empty/missing artifacts, nested LanceDB preservation, selected-run parameters/metric histories/tags, fresh destination ID/timing, repeated/forced import, parent stripping, unsafe/oversized archives, invalid metadata, exporter `None`, import exceptions, and failed post-import validation. Verify listing/export presentation, import JSON, preserved download progress, suppressed routine export logs, and nonzero Make exits.

For a deployment-level acceptance check, round-trip through the actual gateway between namespaces and compare artifact hashes plus metadata, allowing intended destination/provenance changes. Query the imported index using the destination's GraphRAG, LanceDB, and embedding configuration. These checks establish deployment compatibility beyond local transfer tests; file transfer does not convert index formats or vectors.

## Initial implementation verification on 2026-10-12

These checks preceded the configuration simplification below; the separate validation experiment is no longer available as a command option. Local endpoint discovery was subsequently restored through the shared resolver.

- `make test-index-transfer`: 46 passing checks, including real local MLflow REST transfers between separate source and destination workspaces, successful Make export/import with a path containing spaces, and kubeconfig authentication compatibility.
- Flake8, Black, isort, and `git diff --check`: passed for the implementation.
- Actual OpenShift gateway: listed the existing completed indexes; exported the latest sample single-repository index by slug and a combined index by explicit run ID.
- Actual gateway import: imported the combined native archive into a separate validation experiment in the existing `agent-mesh-demo` workspace. Verified sequential retry deduplication, source parameters/metric histories, and all 29 artifact file hashes. Soft-deleted the validation run and experiment after verification.
- Cross-workspace isolation was tested locally. An actual gateway transfer between different namespaces and an application GraphRAG query were not performed.

## Configuration simplification verification

At this stage, the commands used only `KFP_NAMESPACE` and `MLFLOW_TRACKING_URI` for routing, derived the standard result-directory experiment, and enforced `MAX_BYTES = 5 * 1024**3` in Python. The namespace, endpoint, experiment, and size CLI overrides were removed along with their Make variables and environment examples. Endpoint discovery was subsequently restored through the shared resolver below.

`make test-index-transfer`: 47 passing checks after this simplification, including local REST round trips through the standard experiments, Make commands using the existing namespace/endpoint settings, and both internal and external tracking URI configuration. Flake8, Black, isort, and `git diff --check` passed. Live gateway transfers were not repeated for this configuration-only change.

## Shared gateway and listing presentation verification

- `make test-index-transfer`: 59 passing checks, including external endpoint precedence, cluster-local gateway discovery, actionable discovery failures, console launcher behavior without port-forwarding, token/TLS preservation, listing presentation, and TLS warning suppression.
- Console unit tests: 40 passed. Flake8, Black, isort, and `git diff --check` passed for the changed implementation.
- Live `make list-indexes` resolved the cluster-local URI and displayed all four indexing runs in a table with empty stderr.
- Live `make run-console-app` started using the gateway with the existing cluster-local configuration, without an MLflow port-forward. The console page and `/api/indexes` returned HTTP 200; the index API returned two indexes without an error. Stopped the temporary console instance after verification.

## Make-owned endpoint resolution verification

Moved endpoint resolution into derived Make variables and removed the Python resolver module. The four local targets receive the resolved URI through a target-specific exported `MLFLOW_TRACKING_URI`; the original installation `GATEWAY_HOST` is unchanged. Route lookup is lazy, occurs once per local invocation, and is skipped for external URIs and unrelated Make targets. No entries were added to `.env.template`.

`make test-index-transfer`: 61 passing checks, including all four local targets with configured external URIs, cluster-local URIs, and discovery failures; installation gateway independence; and help/test targets avoiding Route discovery. Flake8, Black, isort, and `git diff --check` passed. Live table listing succeeded through the Make-resolved gateway with no TLS warnings. Live console page and index API again returned HTTP 200; stopped the temporary instance after verification.

Export presentation was subsequently simplified to progress plus index details and the quoted saved path. Verified with 61 passing tests and a live single-repository export: progress remained visible, routine package/dependency logs and TLS warnings were absent, and failures remained nonzero without a saved-path success message. Formatting and lint checks passed.

## Reviewed primary sources

- [Pinned exporter](https://github.com/mlflow/mlflow-export-import/blob/05ec457fc0b4acfd3cfc24433eaaab5870ac69cd/mlflow_export_import/run/export_run.py)
- [Pinned importer](https://github.com/mlflow/mlflow-export-import/blob/05ec457fc0b4acfd3cfc24433eaaab5870ac69cd/mlflow_export_import/run/import_run.py)
- [Native envelope/version](https://github.com/mlflow/mlflow-export-import/blob/05ec457fc0b4acfd3cfc24433eaaab5870ac69cd/mlflow_export_import/common/io_utils.py)
- [Databricks detection](https://github.com/mlflow/mlflow-export-import/blob/05ec457fc0b4acfd3cfc24433eaaab5870ac69cd/mlflow_export_import/common/utils.py)
- [MLflow Kubernetes authentication](https://www.mlflow.org/docs/latest/self-hosting/security/kubernetes/)

## Integration with main's root project

Rebased onto main's shared root `pyproject.toml`. The root project retains main's test and lint groups and Python >=3.11 support, adds the pinned index transfer runtime dependencies, and runs the transfer script directly without a package build or console entry point. Pytest adds `workflows/examples` to its import path for the index tests. The root `uv.lock` is regenerated from the merged configuration. Index tests live in `tests/unit/index`; `test-all` includes UI, workflow, and index transfer targets. Local index commands use the frozen root project.
