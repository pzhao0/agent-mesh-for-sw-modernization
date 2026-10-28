# Muse Glimmer 30B FP8

Deploys `RedHatAI/Muse-Glimmer-30B-FP8-block` with vLLM on one NVIDIA L40S.
The chart creates a KServe `ServingRuntime`, `InferenceService`, ServiceAccount,
and persistent cache PVC. KServe manages the Deployment and Services.
Dashboard labels and display names are included for OpenShift AI.

Requires OpenShift AI/KServe model serving, the NVIDIA device plugin, and an
available L40S node. Defaults in [values.yaml](values.yaml):


| Setting                        | Default                           |
| ------------------------------ | --------------------------------- |
| GPUs / tensor parallel size    | 1 / 1                             |
| Context limit (input + output) | 16,384 tokens                     |
| Host memory request / limit    | 32 GiB / 48 GiB                   |
| CPU request / limit            | 4 / 8                             |
| Node toleration                | `g6e-gpu=true:NoSchedule`         |
| Cache                          | 50 GiB, ReadWriteOnce, `gp3-csi` |


Override the toleration and storage class to match your cluster. Set
`nodeSelector` to restrict placement to a specific GPU pool. The public model
requires no Hugging Face token; leave `huggingFace.existingSecret` empty.

Run from the repository root:

```sh
export NAMESPACE=your-model-project
helm upgrade --install muse-glimmer-30b-fp8 resources/helm/muse-glimmer-30b-fp8 \
  --namespace "$NAMESPACE" --create-namespace
oc wait --for=condition=Ready inferenceservice/muse-glimmer-30b-fp8 \
  -n "$NAMESPACE" --timeout=60m
```

The default deployment mode is `RawDeployment`. For KServe versions that use
`Standard`, add `--set serving.deploymentMode=Standard` to the Helm command.

The first startup downloads the weights. Subsequent pod replacements reload
them from the PVC. One replica stays running; Recreate updates stop it before
starting its replacement, so upgrades interrupt serving while the model loads.

Get the endpoint:

```sh
oc get inferenceservice muse-glimmer-30b-fp8 -n "$NAMESPACE" \
  -o jsonpath='{.status.url}{"\n"}'
```

Append `/v1` for OpenAI clients and use
`RedHatAI/Muse-Glimmer-30B-FP8-block` as the model ID. Reachability depends on
cluster routing. The vLLM container has no API-key authentication by default.

For local access:

```sh
oc port-forward -n "$NAMESPACE" deployment/muse-glimmer-30b-fp8-predictor 8000:8000
```

Then, in another terminal:

```sh
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"RedHatAI/Muse-Glimmer-30B-FP8-block","messages":[{"role":"user","content":"Hello!"}],"max_tokens":1024}'
```

The output budget includes reasoning tokens. If `finish_reason` is `length`  
and `content` is empty, increase `max_tokens` to leave room for a final answer.