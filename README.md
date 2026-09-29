# Agent Mesh for Software Engineering - Code Understanding

Analyze legacy code, build a GraphRAG knowledge graph, and generate an
evidence-based modernization plan on Red Hat OpenShift AI.

Contents
---

- [Overview](#overview)
- [Required Software / Tested with](#tested-with)
- [Installing the Code Understanding Workflow](#installing-the-code-understanding-workflow)
  - [Integrating the Models](#integrating-the-models)
  - [Preparing the Environment](#preparing-the-environment)
  - [(Optional) Building the Container Images](#optional-building-the-container-images)
  - [Installing via Makefile](#installing-via-makefile)
  - [S4 Object Storage](#s4-object-storage)
  - [Configuration](#configuration)
  - [Verifying the Deployment](#verifying-the-deployment)
  - [Uninstalling](#uninstalling)
- [Running the Code Understanding Workflow](#running-the-code-understanding-workflow)
- [Running Adhoc Queries](#running-adhoc-queries)
- [Integrating with other tools](#integrating-with-other-tools)
- [More About the Code Understanding Workflow](#more-about-the-code-understanding-workflow)
  - [1. Data Generation](#1-data-generation)
  - [2. Data Indexing](#2-data-indexing)
  - [3. Data Analysis](#3-data-analysis)
- [Add-ons (Optional)](#add-ons)
  - [Code Understanding UI](#code-understanding-ui)
  - [Code Understanding Console Plugin (requires cluster-admin permissions)](#code-understanding-console-plugin)
- [Tags](#tags)

<a id="overview"></a>
## 🧭 Overview

This demonstrates the **Code Understanding** phase of the Agent Mesh for Software Modernization, a framework pattern 
for continuous legacy code which uses a federated, multi-harness, multi-agent 
system (MAS) to support iterative agent-driven development for brownfield applications.

(NOTE: The Agent Mesh consists of two main **workflows**: **Code 
Understanding** and **Code Migration**. This repository demonstrates the **Code Understanding** workflow.)

<a id="tested-with"></a>
## Required Software / Tested with

- Red Hat OpenShift 4.18+ (requires Openshift 4.21+ for UI add-ons)
- Red Hat OpenShift AI 2.22+
- 1X NVIDIA H200 GPU, 1X NVIDIA H100 GPU, 1X NVIDIA L40S GPU
- 8+ vCPUs / 24+ GiB RAM
- A default StorageClass capable of provisioning a 200 GiB ReadWriteOnce PVC for object storage
- MLflow (assumes Openshift AI 3.4+) [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_with_mlflow/installing-mlflow_mlflow)
- Openshift AI Model Registry [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/2.25/html-single/enabling_the_model_registry_component/index)
- Openshift AI Model Catalog [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_the_model_catalog/index)
- Openshift AI Pipelines [Installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/openshift_ai_tutorial_-_fraud_detection_example/setting-up-a-project-and-storage#enabling-ai-pipelines)
- OpenShift CLI (`oc`)
- Helm CLI (`helm`)
- Make (`make`)
- uv CLI (`uv`)
- (**Optional**) Red Hat build of OpenTelemetry operator [Installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/distributed_tracing/distributed-tracing-otel-install)
- (**Optional**) Tempo Operator [Installation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/distributed_tracing/distributed-tracing-tempo-install)

The installer requires a user who can create the target projects and their
workloads. Deploying project workbench image streams, OpenTelemetry resources,
or the OpenShift console plugin requires cluster-admin access or equivalent
delegated permissions.

<a id="documentation"></a>

## Installing the Code Understanding Workflow

### Integrating the Models
Ensure that you have access to OpenAI-compatible endpoints for the following models:

| # | Role | Model | Additional Instructions | Links |
|---|------|-------|------------------------|-------|
| 1 | GraphRAG "chat" model | gpt-oss-120b | [Deploying gpt-oss-120b](resources/models/deploying-gpt-oss-120b.md) | <a href="https://microsoft.github.io/graphrag/config/yaml" target="_blank">GraphRAG Docs</a> |
| 2 | GraphRAG "embedding" model | e5-mistral-7b-instruct | [Deploying e5-mistral-7b-instruct](resources/models/deploying-e5-mistral-7b-instruct.md) | <a href="https://microsoft.github.io/graphrag/config/yaml" target="_blank">GraphRAG Docs</a> |
| 3 | Coding agent** | **(Option A)** Gemma-4-31B-it | [Deploying Gemma-4-31B-it](resources/models/deploying-gemma-4-31b.md) | N/A |
| 4 | Coding agent** | **(Option B)** gpt-oss-120b | [Deploying gpt-oss-120b](resources/models/deploying-gpt-oss-120b.md) | N/A |

<sub>**Optional: Used for "Integrating with other tools" (below)</sub>

### Preparing the Environment

1. Create an environment variables file `.env` using `.env.template` as a guide.

### (Optional) Building the Container Images
1. To build the container images, run the following: `make build-images`

### Installing via Makefile

Run the verified installation command:

```sh
make install DEPLOY_EMBEDDING_MODEL=true DEPLOY_OTEL=true
```

Omit `DEPLOY_EMBEDDING_MODEL=true` to use an externally hosted embedding
model. Omit `DEPLOY_OTEL=true` when OpenTelemetry and Tempo are not required.

OpenTelemetry and Tempo are optional and disabled by default.

### S4 Object Storage

The Helm release deploys [S4 (Super Simple Storage
Service)](https://github.com/rh-aiservices-bu/s4) as its S3-compatible object
store. The pipeline server connects to the internal endpoint
`http://s4:7480` using the `s4-credentials` Secret. The S3 API is not exposed
outside the cluster.

Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S4_UI_USERNAME`, and
`S4_UI_PASSWORD` in `.env` before installation. `make install` enables the S4
web UI Route on port 5000 with authentication. Find the `s4` Route in the
OpenShift console under **Networking → Routes**.

A regular bootstrap Job waits for S4 and creates the application bucket from
`AWS_S3_BUCKET` plus the `demopipelines` pipeline bucket. When OpenTelemetry is
enabled, it also creates the `tempo` bucket. The pipeline and Tempo bucket names
can be changed through `pipelineStorage.bucket` and `otel.tempo.bucket` in
`resources/helm/values.yaml`.

### Configuration

Copy `.env.template` to `.env` and replace every placeholder required for the
features you deploy. The file is ignored by Git and must not be committed.

| Variables | Purpose |
|-----------|---------|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET` | S4 credentials and the application artifact bucket |
| `S4_UI_USERNAME`, `S4_UI_PASSWORD` | Credentials for the authenticated S4 web UI |
| `GIT_USERNAME`, `GIT_TOKEN` | Credentials used by jobs to clone the implementation and analyzed repositories |
| `GIT_REPO`, `GIT_BRANCH`, `GIT_REPO_LIST` | Repository input for single- and multi-repository runs |
| `GRAPHRAG_LLM_*` | Chat model used to build and query the GraphRAG index |
| `EMBED_LLM_*` | Embedding model endpoint, identifier, token, and provider |
| `GROUND_TRUTH_LLM_*`, `JUDGE_LLM_*` | Models used by pipeline evaluation |
| `CODE_LLM_*` | Optional coding-agent model used by integrations |
| `KFP_NAMESPACE` | OpenShift project containing the Data Science Pipelines Application |
| `KFP_DATA_GENERATION_OUTPUT_PATH`, `KFP_DATA_INDEXING_OUTPUT_PATH` | Pipeline artifact paths |
| `KFP_IMAGE_REGISTRY`, `KFP_*_IMAGE_NAME`, `KFP_*_IMAGE_TAG` | Registry coordinates for pipeline component images |
| `CONSOLE_APP_IMAGE_NAME`, `CONSOLE_PLUGIN_IMAGE_NAME`, `CONSOLE_IMAGE_TAG` | Registry coordinates for optional console images |
| `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_INSECURE_TLS`, `MLFLOW_TRACKING_AUTH` | MLflow connection and authentication settings |
| `ASSET_LOADER`, `INSTALL_PREBUILT_INDEX` | Asset source and optional prebuilt-index installation |
| `CUSTOM_EVALUATOR` | Evaluation implementation: `basic` or `mlflow` |
| `LOGLEVEL` | Application and pipeline log level |
| `OTEL_SERVICE_NAME`, `OTEL_NAMESPACE`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER` | Optional OpenTelemetry deployment and export settings |
| `MLFLOW_TRACE_ENABLE_OTLP_DUAL_EXPORT`, `OTEL_SEMCONV_STABILITY_OPT_IN` | Optional MLflow/OpenTelemetry trace behavior |

GraphRAG chat and embedding concurrency is capped at two simultaneous requests
to reduce model endpoint rate limiting.

### Verifying the Deployment

After installation, run the same checks used for this quickstart:

```sh
make helm-lint
make helm-template
make verify-deploy DEPLOY_EMBEDDING_MODEL=true DEPLOY_OTEL=true
```

The verification checks the Helm release, S4 health and credentials, the Data
Science Pipelines Application, and the optional embedding and observability
resources without printing secret values.

### Uninstalling

Run:

```sh
make uninstall
```

Uninstall stops project upload/run/query Jobs, removes Kubeflow pipeline
Workflows and their task pods, removes the optional `e5-mistral` release,
uninstalls `agent-mesh-for-sw`, removes the project workbench ImageStreams,
manually created secrets, and operator-generated storage, and deletes the
application's PVC-backed data. The application and OpenTelemetry namespaces are
preserved. OpenTelemetry variables are not required when telemetry was not
deployed.

The uninstall target supports deployments created with the current Helm
ownership model. It does not remove externally stored MLflow data, externally
pushed container images, or the optional cluster-wide OpenShift console plugin.

## Running the Code Understanding Workflow

1. To run the **Code Understanding** pipeline for a single repository, run:

   ```sh
   make run-pipelines ARGS="--single-repo"
   ```

   To override the default repository or branch:
    - Update `GIT_REPO` and `GIT_BRANCH` in `.env` to the desired repository and branch.
    - Run the following: 
   ```sh
   make apply-secrets
   make run-pipelines ARGS="--single-repo"
   ```

   OR without modifying `.env`:
   ```sh
   make run-pipelines ARGS="--single-repo" PIPELINE_GIT_REPO=https://github.com/org/repo PIPELINE_GIT_BRANCH=main
   ```

2. To run the **Code Understanding** pipeline for multiple repositories:
    - Update `workflows/examples/code_understanding/assets/repos/repo_list.json` with the list of repositories to be processed.
    - Run the following command:
   ```sh
   make run-pipelines ARGS="--multi-repo"
   ```

## Running Adhoc Queries
1. To run adhoc queries about the indexed code, run the following:
```wrappers/adhoc.sh <query>```
   - For example: 
     - `wrappers/adhoc.sh "What migration order would be recommended when refactoring to reduce breaking changes?."`
     - `wrappers/adhoc.sh "Which modules or components would be riskiest to refactor first?" --git-repo https://github.com/org/repo` 
     - `wrappers/adhoc.sh "What are the data stores in this codebase?" --git-repo https://github.com/org/repo --git-branch develop`

## Integrating with other tools

External tools — such as vulnerability scanners, dependency analysers, 
static code parsers, etc. — can contribute metadata to the data-generation 
workflow by writing their output as JSON file(s) into a `.code_metadata` directory at the 
root of the repository being analysed. Any files present there are automatically picked up and merged into the generated dataset before indexing. 
Each JSON file must conform to the code metadata schema at [`workflows/examples/code_understanding/assets/schemas/code_metadata_schema.json`](workflows/examples/code_understanding/assets/schemas/code_metadata_schema.json); 
fields not relevant to a given tool can be omitted.

## More About the Code Understanding Workflow

![High Level Overview](code_understanding.jpg)

The **Code Understanding** workflow is the initial **iteration** in the AI 
software modernization process. It is a **tool-driven workflow** which generates artifacts for the 
**refactoring catalog**. These artifacts are optionally combined with 
other tools (organizational vulnerability scanners, static rules engines, 
etc) to build the **migration plan** for the **Code Migration** workflow.

There are three main sub-workflows in the **Code Understanding** workflow:

#### 1. Data Generation

The **Data Generation** sub-workflow is used to generate metadata that will be 
used for GraphRAG-based indexing. For each relevant file in the original 
codebase, it will generate a `.txt` version of the file and a new metadata 
file. This enriched fileset will then be passed as input to the **Data Indexing** workbench in the next step.

#### 2. Data Indexing

The **Data Indexing** sub-workflow is used to index the fileset from the 
**Data Generation** step using GraphRAG. It will generate a graph-based 
representation of the codebase that can be used for querying.

#### 3. Data Analysis

The **Data Analysis** sub-workflow is used to query the generated GraphRAG index using the GraphRAG SDK.
It includes both canned and adhoc queries that can be used to explore the
code and generate assets for the refactoring catalog, including a migration plan.

<a id="add-ons"></a>
## Add-ons (Optional)

Console add-ons use prebuilt images from `KFP_IMAGE_REGISTRY`. Before deploying
either add-on, set `CONSOLE_IMAGE_TAG` in `.env` to the same tag used to build
and push the console images; for the manual GitHub Actions image workflow, this
is the `version` input.

<a id="code-understanding-ui"></a>
### Code Understanding Console App

The Code Understanding Console App is a standalone web interface for managing and running the Code Understanding workflow. 

To deploy the app to your Openshift cluster:
```
make deploy-console-app
# https://code-understanding-console-<namespace>.apps.<cluster-domain>
```

To run the app locally:
```
make run-console-app
# or: ./wrappers/console.sh
# http://127.0.0.1:8080
```

OR port-forward the cluster deployment:

```
make port-forward-console-app
# http://localhost:8080
```

<a id="code-understanding-console-plugin"></a>
### Code Understanding Console Plugin (requires cluster-admin permissions)

The Code Understanding Console Plugin is an OpenShift web-console dynamic 
plugin backed by a FastAPI service. 

Deploy the console plugin:

```
make deploy-console-plugin
```

Then launch:

- **Application launcher** (grid menu, top right) → **Code Understanding**
- Direct URL: `https://<openshift-console-host>/code-understanding`

Navigation also appears under **Administrator** → **Home** → **Code Understanding**. 

**NOTE**: The plugin is enabled cluster-wide through `consoles.operator.openshift.io/cluster`. If it does not appear at first, run `make enable-console-plugin`.

## Tags

- **Title:** Agent Mesh for Software Engineering - Code Understanding
- **Description:** Analyze legacy code with GraphRAG and generate an evidence-based modernization plan on Red Hat OpenShift AI.
- **Industry:** Cross-industry
- **Product:** Red Hat OpenShift AI
- **Use case:** Application modernization, code understanding, generative AI
- **Contributor organization:** Red Hat
