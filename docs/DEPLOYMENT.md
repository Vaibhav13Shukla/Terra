# Terra — AWS Deployment Runbook

Everything you (the non-frontend teammate) need to do in AWS, in order, to
get Terra's backend live for the hackathon. Follow it top to bottom on first
deploy; later sections are reference for re-deploys and demo day.

Nothing in this file has been run from this environment — no AWS account is
reachable here. Every command is exact and copy-pasteable; run them from your
own machine with your own AWS credentials.

---

## 0. What you're deploying

- API Gateway (HTTP API) → Lambda (container image, FastAPI) → DynamoDB + S3
- Cognito User Pool (auth, off by default) — see [Section 6](#6-turn-on-cognito-auth-when-the-frontend-is-ready)
- SQS + a second Lambda (async worker, off by default) — see [Section 7](#7-switch-to-async-processing-optional)
- Optional Bedrock (LLM intent/explain) — see [Section 5](#5-optional-turn-on-bedrock)

Full resource list: [`infra/README.md`](../infra/README.md). Architecture
rationale: [`docs/architecture.md`](architecture.md) and `docs/adr/`.

---

## 1. AWS account setup

1. **Get an AWS account.** If the hackathon issued AWS credits/an account,
   use that. Otherwise create one at [aws.amazon.com](https://aws.amazon.com).
2. **Don't deploy as the account root user.** In the AWS Console:
   IAM → Users → Create user → attach `AdministratorAccess` (fastest path for
   a hackathon; tighten later if this becomes a real product) → create an
   access key (IAM → your user → Security credentials → Create access key →
   choose "Command Line Interface (CLI)").
3. **Enable MFA on the root account** (IAM → root user → Security credentials).
   Takes two minutes, prevents the worst-case scenario if credentials leak.
4. **Pick a region.** Bedrock model availability varies by region; `us-west-2`
   or `us-east-1` are safe defaults with broad model access. Use the same
   region everywhere below.

## 2. Local tooling

Install on the machine you'll deploy from:

```bash
# AWS CLI v2 — https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
aws --version

# SAM CLI — https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
sam --version

# Docker — required, the Lambda is a container image (rasterio/GDAL exceed
# the 250MB zip-deployment limit)
docker --version
```

Configure credentials:

```bash
aws configure
# AWS Access Key ID: <from step 1.2>
# AWS Secret Access Key: <from step 1.2>
# Default region name: us-west-2   (or your chosen region)
# Default output format: json
```

Verify: `aws sts get-caller-identity` should print your account id and user ARN.

## 3. Request Bedrock model access (do this early — it's not instant)

Even if you deploy with Bedrock disabled first, request access now so it's
ready when you want it:

1. Console → **Amazon Bedrock** → **Model access** (left sidebar).
2. Click **Manage model access** (or **Enable specific models**).
3. Check **Anthropic Claude 3.5 Haiku** (matches `BedrockModelId` default in
   `infra/template.yaml`) — or any Claude model you prefer, just update the
   parameter to match.
4. Submit. Approval is usually instant to a few minutes for Anthropic models
   on Bedrock, but budget time for surprises (per `HANDOFF.md`).
5. Confirm: Model access page shows "Access granted" next to the model.

## 4. First deploy (sync mode, no auth, no Bedrock)

Deploy the simplest working configuration first — this is what a judge sees
if they hit the API directly.

```bash
cd infra
sam build --use-container
```

`sam build` reads `Dockerfile`, builds the container image with your backend
code baked in, and stages it for deploy.

```bash
sam deploy --guided \
  --stack-name terra-dev \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=false ProcessingMode=sync
```

`--guided` walks you through:
- Stack name: `terra-dev` (or accept the default from `--stack-name`)
- AWS region: your chosen region
- Confirm changes before deploy: **Y**
- Allow SAM to create IAM roles: **Y** (required — `CAPABILITY_IAM`)
- Save arguments to `samconfig.toml`: **Y** (so future `sam deploy` with no
  flags reuses these settings)

This is the **first real deploy** of `DynamoDBJobStore.from_table_name`, the
container build, and the Cognito/SQS resources — expect this run to surface
issues fixtures/mocks couldn't catch (per `HANDOFF.md`, budget time here).

When it finishes, note the **Outputs** block:

```
ApiUrl                 https://xxxxxxxxxx.execute-api.us-west-2.amazonaws.com/dev
CognitoUserPoolId       us-west-2_XXXXXXXXX
CognitoAppClientId      xxxxxxxxxxxxxxxxxxxxxxxxxx
AnalysesQueueUrl        https://sqs.us-west-2.amazonaws.com/123456789012/terra-analyses-dev
AnalysesTableName       terra-analyses-dev
ResultsBucketName       terra-results-123456789012-dev
```

Save these — the frontend needs `ApiUrl`, `CognitoUserPoolId`, and
`CognitoAppClientId`; you need `AnalysesQueueUrl` only if you turn on async mode.

### Smoke test

```bash
API_URL=<ApiUrl from outputs>

curl "$API_URL/health"
# {"status":"ok"}

curl "$API_URL/v1/providers"
# {"providers":["sentinel-2-l2a","fixtures"]}

curl -X POST "$API_URL/v1/analyses" \
  -H 'Content-Type: application/json' \
  -d '{
    "aoi": {"type":"Polygon","coordinates":[[[-120.60,36.95],[-120.55,36.95],[-120.55,37.00],[-120.60,37.00],[-120.60,36.95]]]},
    "start_date": "2025-08-01", "end_date": "2025-08-31",
    "comparison_start_date": "2025-07-01", "comparison_end_date": "2025-07-31",
    "analysis": "ndvi_change", "provider": "fixtures"
  }'
# job with status "completed", ~-18% NDVI change (the deterministic demo fixture)
```

Then try `"provider": "sentinel-2-l2a"` with the same AOI/dates for a live
Sentinel-2 run (see `HANDOFF.md` for the verified demo AOI/dates) — this is
the "prove it's real, not just fixtures" step for your demo video.

If this fails, check CloudWatch Logs first (Section 8) before re-deploying blind.

## 5. Optional: turn on Bedrock

Once model access (Section 3) is granted:

```bash
sam deploy --parameter-overrides Stage=dev BedrockEnabled=true \
  BedrockModelId=anthropic.claude-3-5-haiku-20241022-v1:0 \
  AuthEnabled=false ProcessingMode=sync
```

(`sam deploy` with no `--guided` reuses the saved config from Section 4 plus
whatever `--parameter-overrides` you pass — you must repeat *every*
parameter you care about, since omitted ones reset to their template default.)

Test that natural-language questions now go through the LLM: `POST
/v1/analyses` with `{"question": "How has vegetation changed here?", ...}`
instead of `"analysis": "ndvi_change"`. The deterministic fallback still
covers you if Bedrock throttles or the model isn't enabled in this region —
verify by checking response `explanation` reads naturally either way.

## 6. Turn on Cognito auth (when the frontend is ready)

The User Pool and App Client exist from the very first deploy — this section
only flips enforcement on and gets your frontend teammate what they need.

1. Hand your frontend teammate `CognitoUserPoolId` and `CognitoAppClientId`
   from the Outputs. If they're using AWS Amplify or `amazon-cognito-identity-js`,
   these two values plus the region are all their auth SDK needs.
2. **Create a test user** (so you can test protected endpoints before the
   frontend's signup flow exists):
   ```bash
   aws cognito-idp admin-create-user \
     --user-pool-id <CognitoUserPoolId> \
     --username test@example.com \
     --user-attributes Name=email,Value=test@example.com Name=email_verified,Value=true \
     --temporary-password 'TempPass123!' \
     --message-action SUPPRESS

   aws cognito-idp admin-set-user-password \
     --user-pool-id <CognitoUserPoolId> \
     --username test@example.com \
     --password 'RealPass123!' \
     --permanent
   ```
3. **Get a token for manual testing:**
   ```bash
   aws cognito-idp initiate-auth \
     --auth-flow USER_PASSWORD_AUTH \
     --client-id <CognitoAppClientId> \
     --auth-parameters USERNAME=test@example.com,PASSWORD='RealPass123!'
   ```
   This requires `ALLOW_USER_PASSWORD_AUTH` on the app client for CLI
   testing; the deployed client only allows `ALLOW_USER_SRP_AUTH` +
   `ALLOW_REFRESH_TOKEN_AUTH` (secure default for a real frontend SDK, which
   does SRP itself). For a quick CLI test, temporarily add
   `ALLOW_USER_PASSWORD_AUTH` via the Cognito console (User pool → App
   integration → your app client → Edit → Authentication flows), test, then
   remove it again.
   The response's `AuthenticationResult.IdToken` (or `AccessToken`) is your bearer token.
4. **Enable enforcement:**
   ```bash
   sam deploy --parameter-overrides Stage=dev AuthEnabled=true \
     BedrockEnabled=<keep your current value> ProcessingMode=<keep your current value> \
     FrontendOrigin=<your deployed frontend's exact origin, e.g. https://app.example.com>
   ```
5. Verify: `GET $API_URL/v1/analyses` with no header now returns 401; with
   `-H "Authorization: Bearer <IdToken>"` it returns 200.

Do this *after* the frontend's login flow works, not before — flipping
`AuthEnabled=true` early just blocks your own testing and demo prep for no
benefit.

## 7. Switch to async processing (optional)

Only worth doing if sync mode's latency becomes a real problem (see
`infra/README.md` "Processing mode"). To switch:

```bash
sam deploy --parameter-overrides Stage=dev ProcessingMode=async \
  BedrockEnabled=<keep> AuthEnabled=<keep> FrontendOrigin=<keep>
```

`POST /v1/analyses` now returns immediately with `status: "created"`; poll
`GET /v1/analyses/{job_id}` until `status` is `completed` or `failed`. Watch
`WorkerFunction`'s CloudWatch Logs (Section 8) on first use — this path is
unit-tested offline but has never run against a real SQS queue (see
`infra/README.md`).

## 8. CloudWatch — logs and debugging

Console → CloudWatch → Log groups:
- `/aws/lambda/terra-api-dev` — every API request (structured JSON, one line
  per event — see `app/observability/logging.py`)
- `/aws/lambda/terra-worker-dev` — async worker processing (only has entries
  once you've used `ProcessingMode=async`)

Or via CLI:

```bash
aws logs tail /aws/lambda/terra-api-dev --follow
```

Every log line is JSON (`{"event": ..., "job_id": ..., "status": ..., "duration_ms": ...}`)
— filterable in CloudWatch Logs Insights, e.g.:

```
fields @timestamp, event, job_id, status, duration_ms
| filter event = "analysis_completed"
| sort @timestamp desc
```

## 9. Cost controls (set this up before you forget)

1. Console → **Billing and Cost Management** → **Budgets** → **Create budget**.
2. Choose **Zero-based budget** or a small fixed amount (e.g. $10) appropriate
   for a hackathon — DynamoDB/S3/Lambda/API Gateway are pay-per-use with no
   idle cost by design (see `infra/README.md` "Cost"), so a real bill here
   almost always means Bedrock usage or a runaway test loop.
3. Add an **alert** at 50% and 100% of the budget, email notification to
   yourself.
4. Optional but recommended: Console → Bedrock → check your region's default
   quota isn't something you'll blow through accidentally during demo prep.

## 10. Frontend integration checklist

Give your frontend teammate:
- `ApiUrl` — the API base URL
- `CognitoUserPoolId`, `CognitoAppClientId`, and your chosen region — for
  their auth SDK (Amplify, `amazon-cognito-identity-js`, or a plain OAuth
  flow against the Cognito Hosted UI if you configure one)
- `docs/openapi.json` — the API contract (regenerate after any API change:
  `python scripts/export_openapi.py` from `backend/`)
- Once they have a real deployed origin, redeploy with
  `FrontendOrigin=https://their-actual-domain` (Section 6, step 4) — CORS
  defaults to `*` only for early development.

## 11. Redeploying after a code change

```bash
cd infra
sam build --use-container
sam deploy   # reuses samconfig.toml from the first --guided run
```

If you changed `--parameter-overrides` values you want to keep, pass them
again explicitly — SAM does not remember overrides between plain `sam deploy`
calls, only the values saved via `--guided`.

## 12. Tear down (end of hackathon, or to stop all charges)

```bash
cd infra
sam delete --stack-name terra-dev
```

This deletes every resource the stack created (Lambdas, API Gateway,
DynamoDB table, SQS queues, Cognito User Pool, log groups). **The S3 results
bucket must be empty before CloudFormation can delete it** — if `sam delete`
fails on the bucket, empty it first: `aws s3 rm s3://<ResultsBucketName> --recursive`,
then re-run `sam delete`.

## 13. Pre-submission security/production checklist

- [ ] No `.env` file or credentials committed (`git status` clean, `.env` is
      gitignored — verify with `git check-ignore .env`)
- [ ] `FrontendOrigin` set to your real deployed origin, not `*`, if the API
      is public and you want CORS actually restrictive
- [ ] `AuthEnabled=true` if the hackathon's judging criteria reward real
      user auth (check the rubric) and your frontend's login flow works
      end-to-end
- [ ] AWS Budget alert is live (Section 9)
- [ ] CloudWatch log groups have the 30-day retention set (they do, by
      default, from `template.yaml` — verify in the console if you edited it)
- [ ] `sam validate --template infra/template.yaml` and `cfn-lint
      infra/template.yaml` both pass (CI runs `cfn-lint` on every push — see
      `.github/workflows/ci.yml`)
- [ ] IAM roles are least-privilege, not `AdministratorAccess` (the Lambda
      execution roles are scoped automatically by the SAM policies in
      `template.yaml` — this only matters for the *human* IAM user you
      created in Section 1, which is fine to keep broad for the hackathon
      timeline, but don't attach it to anything long-lived afterward)
