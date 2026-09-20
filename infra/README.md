# Terra — AWS deployment

Infrastructure is defined as code in [`template.yaml`](template.yaml) (AWS SAM).
**Deploy is pending the team's AWS credentials — this has been written and
reviewed but not applied from this environment.** The steps below are exact
and reproducible once credentials are available; nothing here is checked off
that hasn't actually been run (§66).

## Deploy

**One source of truth: [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md)** — every
command in order (profile setup, budget, build, deploy, smoke tests, async,
Amplify frontend, optional Bedrock/Cognito, teardown). This file only explains
how the template is put together; it deliberately does not repeat the commands,
so they cannot drift apart.

Things that are easy to get wrong and are handled in the template:

- The API uses API Gateway's `$default` stage, so `ApiUrl` has **no stage prefix**.
  A named stage makes every route 404 (the app does not strip `/dev`).
- Neither function has an `ImageUri`. `sam build` builds the image from each
  function's `Metadata` (Dockerfile `infra/Dockerfile`, build context = repo root,
  trimmed by the root `.dockerignore`) and `sam deploy --resolve-image-repos`
  creates the ECR repositories and pushes to them.
- Timeouts: API 30 s (an HTTP API cuts an integration off at ~30 s anyway), worker
  300 s, SQS visibility timeout 1800 s (>= 6x the worker's).

## What gets created

See [`template.yaml`](template.yaml) for the authoritative definition. Summary:

| Resource | Purpose |
|---|---|
| API Gateway HTTP API | public `/v1/analyses`, `/health`, etc. |
| Lambda (container image) | the FastAPI app via Mangum — see `../backend/app/api/main.py` |
| Lambda (container image, same image, different entry point) | `WorkerFunction` — SQS-triggered async processing, see `../backend/app/worker/handler.py` |
| SQS queue + dead-letter queue | job hand-off when `ProcessingMode=async` |
| Cognito User Pool + App Client | end-user auth; enforced only when `AuthEnabled=true` |
| DynamoDB table (pay-per-request, TTL enabled) | job state |
| S3 bucket (encrypted, public access blocked, 30-day lifecycle) | results/evidence |
| CloudWatch log groups (30-day retention) | structured logs, API + worker |

IAM: each Lambda's role is scoped to CRUD on its own DynamoDB table and S3
bucket, plus `bedrock:InvokeModel` only — and only when `BedrockEnabled=true`
(a `Condition` in the template; the resources are foundation models plus this
account's inference profiles). The API's role can additionally only
`sqs:SendMessage` to its own queue. Never `AdministratorAccess` (§31, §91).

## Validating without deploying

From the repo root:

```bash
cfn-lint infra/template.yaml
```

Install `aws-sam-translator` alongside `cfn-lint` (`pip install cfn-lint aws-sam-translator`)
so it runs the real SAM transform rather than only checking the syntax. Note that
`aws-sam-translator` depends on `boto3`: the backend test suite guards against that
(`backend/tests/conftest.py` hides real AWS credentials and blocks botocore HTTP).
`sam validate --lint -t infra/template.yaml` needs the SAM CLI and an AWS profile;
see the runbook (Part C1).

## Cost (§67)

DynamoDB is pay-per-request (no idle cost), S3 has a 30-day expiry lifecycle
rule, and CloudWatch log retention is capped at 30 days. Lambda and API
Gateway are pay-per-invocation. For hackathon-scale traffic this should stay
within or close to AWS's free tier; Bedrock (if enabled) is the one
genuinely usage-priced component — see the root [`README.md`](../README.md#ai-coding-tools)
and set a billing alert regardless.

## Processing mode

`ProcessingMode=sync` (default) runs the analysis inline inside the API
Lambda request — simplest to demo, and measured to work (18.6-26.1s for the
canonical demo request across live runs) but close enough to API Gateway's
29-second integration timeout that a slow network day could exceed it (see
[`docs/adr/002-processing-runtime.md`](../docs/adr/002-processing-runtime.md)).

`ProcessingMode=async` has the API enqueue to SQS and return immediately
(job status `created`); `WorkerFunction` (same container image, invoked via
`app.worker.handler.handler`) dequeues and resolves the job through the same
`JobStore`, so `GET /v1/analyses/{id}` behaves identically either way. The
queue, DLQ, and worker Lambda are always deployed, so switching modes is a
stack-parameter change, not a new deploy. This is unit-tested offline (see
`backend/tests/unit/test_worker.py`, `test_analysis_queue.py`) but — like
every AWS integration in this repo — not yet exercised against a real SQS
queue; treat it as verified logic, not a verified deployment, until the
first `ProcessingMode=async` deploy is smoke-tested.
