# Qwen3.5 9B FP8 Dynamic

Deploys `RedHatAI/Qwen3.5-9B-FP8-dynamic` with vLLM on OpenShift AI/KServe,
configured for one NVIDIA A10G. Serving is text only, using the FP8 dynamic checkpoint.
On A10G, vLLM uses weight-only FP8 with BF16 computation through Marlin.

The chart creates a `ServingRuntime`, `InferenceService`, ServiceAccount, and
persistent model cache. KServe manages the Deployment and Services.

Requires OpenShift AI/KServe model serving, the NVIDIA device plugin, an
available A10G node, and a CUDA-compatible R580+ driver. Defaults in
[values.yaml](values.yaml):

| Setting                       | Default                        |
| ----------------------------- | ------------------------------ |
| GPUs / tensor parallel size    | 1 / 1                          |
| Context limit (input + output) | 16,384 tokens                  |
| Concurrent sequences          | 1                              |
| Host memory request / limit   | 20 GiB / 26 GiB                 |
| CPU request / limit           | 4 / 8                          |
| Node toleration               | `g5-gpu=true:NoSchedule`        |
| Cache                         | 50 GiB, ReadWriteOnce, `gp3-csi` |

Override the toleration and storage class to match your cluster. Set
`nodeSelector` to restrict placement to a specific GPU pool. The public model
requires no Hugging Face token; leave `huggingFace.existingSecret` empty.
Eager execution is enabled. The vLLM image and model revision are pinned.

Run from the repository root:

```sh
export NAMESPACE=your-model-project
helm upgrade --install qwen3-5-9b-fp8-dynamic resources/helm/qwen3.5-9b-fp8-dynamic \
  --namespace "$NAMESPACE" --create-namespace
oc wait --for=condition=Ready inferenceservice/qwen3-5-9b-fp8-dynamic \
  -n "$NAMESPACE" --timeout=60m
```

The default deployment mode is `RawDeployment`. For KServe versions that use
`Standard`, add `--set serving.deploymentMode=Standard` to the Helm command.
Resource names are fixed, so install once per namespace.

The first startup downloads the weights; later starts reuse the cache.
The chart runs one replica, and upgrades interrupt serving while the replacement
loads. A10G memory fit has not yet been validated. If startup runs out of GPU
memory, reduce `model.maxModelLen` to 8192.

Get the endpoint:

```sh
oc get inferenceservice qwen3-5-9b-fp8-dynamic -n "$NAMESPACE" \
  -o jsonpath='{.status.url}{"\n"}'
```

Append `/v1` for OpenAI clients and use
`RedHatAI/Qwen3.5-9B-FP8-dynamic` as the model ID. Reachability depends on
cluster routing. The vLLM container has no API-key authentication by default.

For local access:

```sh
oc port-forward -n "$NAMESPACE" deployment/qwen3-5-9b-fp8-dynamic-predictor 8000:8000
```

Then, in another terminal:

```sh
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"RedHatAI/Qwen3.5-9B-FP8-dynamic","messages":[{"role":"user","content":"Hello!"}],"max_tokens":512,"chat_template_kwargs":{"enable_thinking":false}}'
```

Tool calls use the `qwen3_coder` parser; reasoning uses `qwen3`. The example
disables thinking. When enabled, reasoning tokens count toward the output
budget; if `finish_reason` is `length` and `content` is empty, increase
`max_tokens` or disable thinking.
