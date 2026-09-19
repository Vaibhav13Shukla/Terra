# Terra — AWS deployment

Infrastructure is defined as code in [`template.yaml`](template.yaml) (AWS SAM).
**Deploy is pending the team's AWS credentials — this has been written and
reviewed but not applied from this environment.** The steps below are exact
and reproducible once credentials are available; nothing here is checked off
that hasn't actually been run (§66).

## Prerequisites

- AWS account with credentials configured (`aws configure` or environment vars)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Docker (for the container-image Lambda build)
- Bedrock model access requested in the target region, if `BedrockEnabled=true`
  ([AWS docs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html))

## Deploy

```bash
cd infra
sam build --use-container
sam deploy --guided \
  --stack-name terra-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=false ProcessingMode=sync
```

See [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for the full, step-by-step
account setup (Bedrock model access, Cognito console steps, first deploy,
smoke test, cost controls) — this file stays a quick reference.

`sam deploy --guided` prompts for region and confirms the change set before
applying anything. The first deploy creates an ECR repository for the API
container image; `sam build` pushes to it automatically.

Outputs include `ApiUrl` — the base URL the frontend and demo scripts should
target.

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
bucket, plus `bedrock:InvokeModel` only (and the API's role can additionally
only `sqs:SendMessage` to its own queue) — never `AdministratorAccess` (§31, §91).

## Validating without deploying

```bash
sam validate --template template.yaml
```

(Not run in this environment — no AWS CLI/SAM CLI installed here. Run this
before the first real deploy.)

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
