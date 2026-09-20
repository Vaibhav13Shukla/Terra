# Terra — AWS deployment runbook

Every terminal command, in order, to stand up all of Terra's AWS services in your
own account, check that each one works, and tear it all down again.

> **Status — read this first.** The template, container build context, Lambda
> handler and static frontend were verified **offline** (cfn-lint with the SAM
> transform, a local SAM render, 137 backend tests, a real-browser run of the
> exported frontend). **Nothing here has been run against a real AWS account** —
> the SAM CLI and Docker were not available where this was written. Expect the
> first deploy to surface something. Each step below says what you should see and
> what to do if you don't; do not skip the checks.

Run everything in **Git Bash**, from the **repository root** (the folder that
contains `infra/`, `backend/` and `frontend/`). Keep one terminal open: several
steps store values in shell variables that a new terminal will not have.

---

## Decisions already made (so you don't have to)

| Question | Choice | Why |
|---|---|---|
| Region | `us-west-2` | Sentinel-2 imagery lives in `us-west-2`; running next to it avoids cross-region latency on every read. |
| Frontend hosting | **AWS Amplify Hosting** (manual zip deploy) | It is an AWS service, needs no Git connection, and the frontend is a static export. |
| Auth (Cognito) | **Off** for the demo (`AuthEnabled=false`) | The backend does not isolate jobs per user: any signed-in user can list every job. Turning auth on implies a privacy property that does not exist yet. See Part G. |
| Bedrock | **Optional**, off by default | Terra works without it. It only writes the *explanation text*; the question is parsed by a deterministic parser either way. See Part F. |
| Strands agents | **Not used** | The original design mentioned them; nothing in the code uses them. |
| Processing mode | Deploy **sync first**, then switch to **async** | One failure mode per step. Sync proves image → API → DynamoDB. Async then proves SQS → worker. Live Sentinel-2 runs need async: an API Gateway HTTP API cuts a request off at ~30 s. |

## Safety rules for this runbook

- **Every command names `--profile terra-hackathon` and `--region us-west-2`
  explicitly.** Never rely on your default profile. If your machine has other AWS
  profiles (work accounts, etc.) they must never be used for Terra.
- Nothing here needs, or should use, root credentials.
- Do not paste access keys into a command line, a chat, or a file in this repo.

---

## Part A — One-time setup

### A1. Create a deployer user (the only step done in the console)

You cannot use the CLI before you have credentials, so this one step is manual.
Sign in to your **personal** AWS account, then:

1. **Root user → Security credentials → enable MFA.** Two minutes; protects against the worst case.
2. **IAM → Users → Create user** named `terra-deployer`. Attach the
   `AdministratorAccess` policy directly. (Terra creates IAM roles, Lambda, API
   Gateway, ECR, DynamoDB, SQS, Cognito, S3, Amplify and Budgets resources; scoping a
   custom policy to that is real work. For a personal sandbox account, admin is the
   pragmatic choice — do not reuse this user for anything long-lived. The more secure
   alternative is IAM Identity Center with `aws configure sso`.)
3. **`terra-deployer` → Security credentials → Create access key → "Command Line
   Interface (CLI)".** Keep the page open; you paste these into the next step.

### A2. Install the tools

Docker is required: the Lambda functions are container images (rasterio/GDAL exceed
the 250 MB zip limit). Docker Desktop on Windows Home needs WSL 2; the installer
will tell you if a reboot is needed.

```bash
winget install --id Amazon.SAM-CLI -e
```

```bash
winget install --id Docker.DockerDesktop -e
```

**Close and reopen Git Bash** (so `PATH` refreshes), start Docker Desktop, then check:

```bash
sam --version
```

```bash
docker info --format '{{.ServerVersion}}'
```

```bash
aws --version
```

You should see three version numbers. If `docker info` errors, Docker Desktop is not
running yet — wait for its whale icon to stop animating.

### A3. Create the profile and confirm which account it is

```bash
aws configure --profile terra-hackathon
```

Paste the access key ID and secret from A1, region `us-west-2`, output `json`.

```bash
aws sts get-caller-identity --profile terra-hackathon
```

**Compare the `Account` number with the one shown at the top-right of your AWS
console. If it is not your personal account, stop.** Do not continue until it is.

### A4. Shell hygiene

```bash
export AWS_PAGER=""
```

(Stops the AWS CLI from opening a pager that blocks scripted output.)

---

## Part B — Cost guardrail (do this before creating anything)

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --profile terra-hackathon --query Account --output text)
```

Replace `you@example.com` with your email, then run:

```bash
aws budgets create-budget --account-id "$ACCOUNT_ID" --profile terra-hackathon --budget '{"BudgetName":"terra-monthly","BudgetLimit":{"Amount":"10","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' --notifications-with-subscribers '[{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":50,"ThresholdType":"PERCENTAGE"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]},{"Notification":{"NotificationType":"ACTUAL","ComparisonOperator":"GREATER_THAN","Threshold":100,"ThresholdType":"PERCENTAGE"},"Subscribers":[{"SubscriptionType":"EMAIL","Address":"you@example.com"}]}]'
```

```bash
aws budgets describe-budgets --account-id "$ACCOUNT_ID" --profile terra-hackathon --query "Budgets[].BudgetName"
```

You should see `["terra-monthly"]`. You get an email at $5 and $10 of actual spend.
(Budgets alerts; it does not stop anything from running.)

---

## Part C — Deploy the backend (sync mode)

### C1. Pre-flight checks (nothing is created)

```bash
sam validate --lint -t infra/template.yaml --region us-west-2 --profile terra-hackathon
```

Expected: `... is a valid SAM Template`. (SAM makes one read-only IAM call here, which
is why it needs the profile.)

If you have the project's Python virtualenv, also run the offline test suite:

```bash
(cd backend && ../.venv/Scripts/python -m pytest -q)
```

Expected: `137 passed`.

### C2. Build the container images

Docker Desktop must be running.

```bash
sam build -t infra/template.yaml
```

Expected: `Build Succeeded`. The first build takes several minutes (it pulls the Lambda
base image and installs rasterio/numpy). SAM builds two images from the same
`infra/Dockerfile` — one for the API function, one for the worker (which only
differs by its entry point). The build context is the repo root; `.dockerignore`
keeps `.venv`, `node_modules` and `.git` out of it.

Always run `sam build` and `sam deploy` from the repo root, both times, so `sam
deploy` finds `.aws-sam/build`.

### C3. Deploy

```bash
sam deploy --stack-name terra-dev --region us-west-2 --profile terra-hackathon --resolve-s3 --resolve-image-repos --capabilities CAPABILITY_IAM --confirm-changeset --tags Project=terra --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=false ProcessingMode=sync FrontendOrigin='*'
```

What each flag does — none of it is magic:

- `--resolve-s3` / `--resolve-image-repos`: SAM creates (and reuses) the S3 bucket for
  the template and one ECR repository per image, then pushes the images. There is
  deliberately no `ImageUri` in the template.
- `--capabilities CAPABILITY_IAM`: you are allowing the stack to create the Lambda
  execution roles.
- `--confirm-changeset`: shows the change set and asks `y/N`. On a first deploy, read
  the list of IAM roles and resources before typing `y`.
- `--parameter-overrides`: passed **explicitly every time**. Do not rely on a saved
  `samconfig.toml` (SAM would silently reset any parameter you forgot to repeat to
  its template default).

This takes a few minutes. Expected last line: `Successfully created/updated stack - terra-dev`.

### C4. Read the stack outputs

Define a helper once (redefine it if you open a new terminal):

```bash
tout() { aws cloudformation describe-stacks --stack-name terra-dev --profile terra-hackathon --region us-west-2 --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
```

```bash
API_URL=$(tout ApiUrl)
```

```bash
echo "$API_URL"
```

It must look like `https://abc123.execute-api.us-west-2.amazonaws.com` — **no**
`/dev` at the end and no trailing slash.

### C5. Smoke tests (fixtures — deterministic, no satellite data)

The first request after a deploy is a Lambda **cold start** of a large container
image: allow ~5–15 s. Later requests are fast.

```bash
curl -sS "$API_URL/health"
```

Expected: `{"status":"ok"}`.

```bash
curl -sS "$API_URL/v1/providers"
```

Expected: a JSON list containing `fixtures` and `sentinel-2-l2a`.

```bash
BODY_FIXTURES='{"aoi":{"type":"Polygon","coordinates":[[[-120.60,36.95],[-120.55,36.95],[-120.55,37.00],[-120.60,37.00],[-120.60,36.95]]]},"start_date":"2025-08-01","end_date":"2025-08-31","comparison_start_date":"2025-07-01","comparison_end_date":"2025-07-31","analysis":"ndvi_change","provider":"fixtures"}'
```

```bash
curl -sS -X POST "$API_URL/v1/analyses" -H 'Content-Type: application/json' -d "$BODY_FIXTURES" | grep -o '"status":"completed"\|"percentage_change":[^,]*'
```

Expected — exactly these two lines:

```
"status":"completed"
"percentage_change":-18.0
```

That single result proves: image built and pushed → Lambda runs → API Gateway routes
(`$default` stage, no path prefix) → the analysis pipeline runs → DynamoDB write
worked. If it does not, go to **Troubleshooting** before changing anything.

### C6. Confirm the data layer and the logs

```bash
aws dynamodb scan --table-name "$(tout AnalysesTableName)" --select COUNT --profile terra-hackathon --region us-west-2
```

Expected: `"Count": 1` (or more). Note: the app's own `GET /v1/analyses` uses a table
scan too — fine at demo scale, not for production.

```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/terra-api-dev --since 15m --profile terra-hackathon --region us-west-2
```

Expected: JSON lines including `"event": "analysis_completed"`. (`MSYS_NO_PATHCONV=1`
stops Git Bash from rewriting the leading `/aws/...` into a Windows path.)

---

## Part D — Switch to async mode (SQS + worker Lambda)

**This path has been unit-tested offline but has never run against a real SQS
queue.** That is why it is its own part, with the worker's log open beside it.

### D1. Open a second terminal and watch the worker

In a **second** Git Bash window (leave it open):

```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/terra-worker-dev --follow --profile terra-hackathon --region us-west-2
```

If it says the log group does not exist yet, it appears after the first worker
invocation — run the tail again then.

### D2. Redeploy with async on (no rebuild needed — the code did not change)

Back in your **first** terminal:

```bash
sam deploy --stack-name terra-dev --region us-west-2 --profile terra-hackathon --resolve-s3 --resolve-image-repos --capabilities CAPABILITY_IAM --confirm-changeset --tags Project=terra --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=false ProcessingMode=async FrontendOrigin='*'
```

### D3. A polling helper, then a fixtures job

```bash
poll() { for i in $(seq 1 60); do S=$(curl -sS "$API_URL/v1/analyses/$1" | grep -o '"status":"[a-z]*"' | head -1 | cut -d'"' -f4); echo "$(date +%T) $S"; case "$S" in completed|failed) break;; esac; sleep 5; done; }
```

```bash
JOB_ID=$(curl -sS -X POST "$API_URL/v1/analyses" -H 'Content-Type: application/json' -d "$BODY_FIXTURES" | grep -o '"job_id":"[^"]*"' | head -1 | cut -d'"' -f4)
```

```bash
poll "$JOB_ID"
```

Expected: `created` on the first line(s), then `completed`. The second terminal should
show the worker picking the message up. (`created` means "accepted and queued" — the
web UI labels it "queued".)

### D4. A live Sentinel-2 job (real satellite data)

```bash
BODY_LIVE="${BODY_FIXTURES/fixtures/sentinel-2-l2a}"
```

```bash
JOB_ID=$(curl -sS -X POST "$API_URL/v1/analyses" -H 'Content-Type: application/json' -d "$BODY_LIVE" | grep -o '"job_id":"[^"]*"' | head -1 | cut -d'"' -f4)
```

```bash
poll "$JOB_ID"
```

Expected: `completed` after roughly 30–90 s. Locally, this same area took ~20–30 s; on
Lambda add the cold start and network path to the S3 bucket. The number will differ
from the fixtures' −18 % — this is real imagery. If it ends `failed`, read the
`error` field: `curl -sS "$API_URL/v1/analyses/$JOB_ID"`.

### D5. Queue health

```bash
aws sqs get-queue-attributes --queue-url "$(tout AnalysesQueueUrl)" --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible --profile terra-hackathon --region us-west-2
```

```bash
aws sqs get-queue-attributes --queue-url "$(aws sqs get-queue-url --queue-name terra-analyses-dlq-dev --profile terra-hackathon --region us-west-2 --query QueueUrl --output text)" --attribute-names ApproximateNumberOfMessages --profile terra-hackathon --region us-west-2
```

Expected: the main queue at `0`/`0`, and the **dead-letter queue at `0`**. A non-zero
DLQ means a job failed three times.

---

## Part E — Frontend on Amplify Hosting

The frontend is a static export (`output: "export"`, plain files in `frontend/out/`).
The API URL is **baked in at build time**, so build after Part C.

### E1. Build it

```bash
npm --prefix frontend ci
```

```bash
NEXT_PUBLIC_API_URL="$API_URL" npm --prefix frontend run build
```

Expected: `Generating static pages ... (8/8)`. Because no `NEXT_PUBLIC_COGNITO_*` values
are set, the app builds in open **demo mode** (badge in the header, no sign-in), which
matches `AuthEnabled=false`. (If you have a `frontend/.env.local` containing
`NEXT_PUBLIC_COGNITO_*` values, remove them for this build — they would switch the
build into login mode.)

### E2. Zip the contents of `out/` (files at the zip root)

```bash
(cd frontend/out && ../../.venv/Scripts/python -m zipfile -c ../terra-frontend.zip *)
```

(Any Python 3 works; adjust the path if you do not have the project virtualenv.)

```bash
.venv/Scripts/python -m zipfile -l frontend/terra-frontend.zip | head -5
```

You must see `index.html` **at the root** of the archive, not under an `out/` folder.

### E3. Create the Amplify app and branch

```bash
APP_ID=$(aws amplify create-app --name terra-frontend --platform WEB --profile terra-hackathon --region us-west-2 --query app.appId --output text)
```

```bash
aws amplify create-branch --app-id "$APP_ID" --branch-name main --profile terra-hackathon --region us-west-2
```

### E4. Upload and start the deployment

```bash
read -r DEPLOY_JOB_ID UPLOAD_URL < <(aws amplify create-deployment --app-id "$APP_ID" --branch-name main --profile terra-hackathon --region us-west-2 --query '[jobId,zipUploadUrl]' --output text)
```

```bash
curl -sS -T frontend/terra-frontend.zip "$UPLOAD_URL"
```

```bash
aws amplify start-deployment --app-id "$APP_ID" --branch-name main --job-id "$DEPLOY_JOB_ID" --profile terra-hackathon --region us-west-2
```

```bash
aws amplify get-job --app-id "$APP_ID" --branch-name main --job-id "$DEPLOY_JOB_ID" --profile terra-hackathon --region us-west-2 --query job.summary.status --output text
```

Re-run that last command until it prints `SUCCEED` (usually under a minute).

### E5. Check the site

```bash
SITE="https://main.$(aws amplify get-app --app-id "$APP_ID" --profile terra-hackathon --region us-west-2 --query app.defaultDomain --output text)"
```

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "$SITE/workspace/"
```

Expected `200`. Then the slash-less form a person might paste:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "$SITE/workspace"
```

`200` or a `301` to `/workspace/` are both fine. If it is `404`, Amplify is not
mapping the bare route; add rewrite rules (these are unverified fallbacks):

```bash
aws amplify update-app --app-id "$APP_ID" --profile terra-hackathon --region us-west-2 --custom-rules 'source=/workspace,target=/workspace/index.html,status=200' 'source=/login,target=/login/index.html,status=200' 'source=/signup,target=/signup/index.html,status=200' 'source=/confirm,target=/confirm/index.html,status=200'
```

### E6. Lock CORS to your real origin, then test in a browser

So far the API allowed any origin (`*`) for testing. Now restrict it to the site
(repeat **every** parameter):

```bash
sam deploy --stack-name terra-dev --region us-west-2 --profile terra-hackathon --resolve-s3 --resolve-image-repos --capabilities CAPABILITY_IAM --confirm-changeset --tags Project=terra --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=false ProcessingMode=async FrontendOrigin="$SITE"
```

```bash
echo "$SITE"
```

Open that URL. In the workspace: **Use demo field → Run analysis** (Fixtures) should
give −18.0 %. Switch the data source to **Sentinel-2 L2A** and run again: you should
see *Queued* / *Analysing Sentinel-2 scenes…*, then a real result. If the request is
blocked with a CORS error in the browser console, `FrontendOrigin` does not exactly
match `$SITE` (scheme + host, no trailing slash).

---

## Part F — Optional: Bedrock (LLM-written explanation)

**What it does and does not do.** With Bedrock on, the *explanation paragraph* is
written by the model from the already-computed numbers. Numbers and evidence are
always computed in Python. The question is parsed by the deterministic parser
either way. If Bedrock is unavailable the app falls back to the template explanation
and **logs** `bedrock_explain_fallback` with the reason.

**Unverified:** availability of a given Claude model in your account/region. The
template's default model id may be retired — do not assume it works.

### F1. Find a model you can actually use

```bash
aws bedrock list-foundation-models --by-provider anthropic --profile terra-hackathon --region us-west-2 --query "modelSummaries[?modelLifecycle.status=='ACTIVE'].modelId" --output text
```

```bash
aws bedrock list-inference-profiles --profile terra-hackathon --region us-west-2 --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId" --output text
```

Pick one id (an inference-profile id like `us.anthropic.…` is fine — the template's
IAM policy allows both). Set it:

```bash
MODEL_ID='<paste-the-id-here>'
```

### F2. Test it directly

```bash
aws bedrock-runtime invoke-model --model-id "$MODEL_ID" --cli-binary-format raw-in-base64-out --body '{"anthropic_version":"bedrock-2023-05-31","max_tokens":20,"messages":[{"role":"user","content":"Reply with OK"}]}' --profile terra-hackathon --region us-west-2 bedrock-test.json
```

```bash
cat bedrock-test.json
```

Expected: JSON with a `content` text. If you get `AccessDeniedException` mentioning
model access or use-case details, that is an account-level Bedrock gate resolved in the
Bedrock console (Model catalog) — nothing in this repo can fix it. Delete the
scratch file when done:

```bash
rm bedrock-test.json
```

### F3. Turn it on

```bash
sam deploy --stack-name terra-dev --region us-west-2 --profile terra-hackathon --resolve-s3 --resolve-image-repos --capabilities CAPABILITY_IAM --confirm-changeset --tags Project=terra --parameter-overrides Stage=dev BedrockEnabled=true BedrockModelId="$MODEL_ID" AuthEnabled=false ProcessingMode=async FrontendOrigin="$SITE"
```

### F4. Prove it is really being used

Run any analysis (D3), then (in async mode the explanation is written by the worker;
if you are in sync mode, tail `/aws/lambda/terra-api-dev` instead):

```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/terra-worker-dev --since 10m --filter-pattern bedrock_explain --profile terra-hackathon --region us-west-2
```

`bedrock_explain_ok` → Bedrock wrote the text. `bedrock_explain_fallback` → it did
not; the `error` field says why (`AccessDenied…` = model access or IAM;
`ValidationException` = wrong or retired model id). No `bedrock_explain_*` line at
all means Bedrock is not enabled on that function.

---

## Part G — Optional: Cognito login

**Recommendation: leave this off for the demo.** The backend only checks that a
token is valid; it does not record *who* created a job. With auth on, any signed-in
user can still list and open **every** job. Login would imply a privacy property the
system does not have. Also: the web app's tokens expire after 1 hour with no
in-app refresh.

If you still want it (e.g. to show the login flow):

```bash
aws cognito-idp admin-create-user --user-pool-id "$(tout CognitoUserPoolId)" --username test@example.com --user-attributes Name=email,Value=test@example.com Name=email_verified,Value=true --message-action SUPPRESS --profile terra-hackathon --region us-west-2
```

```bash
aws cognito-idp admin-set-user-password --user-pool-id "$(tout CognitoUserPoolId)" --username test@example.com --password 'TerraTest2026pass' --permanent --profile terra-hackathon --region us-west-2
```

(Password policy: 12+ characters with upper, lower and a number.) Mint a token from the terminal
— this uses the admin auth flow, which needs your AWS credentials and cannot be
called from a browser:

```bash
TOKEN=$(aws cognito-idp admin-initiate-auth --auth-flow ADMIN_USER_PASSWORD_AUTH --user-pool-id "$(tout CognitoUserPoolId)" --client-id "$(tout CognitoAppClientId)" --auth-parameters USERNAME=test@example.com,PASSWORD='TerraTest2026pass' --query AuthenticationResult.IdToken --output text --profile terra-hackathon --region us-west-2)
```

Turn enforcement on (repeat every parameter):

```bash
sam deploy --stack-name terra-dev --region us-west-2 --profile terra-hackathon --resolve-s3 --resolve-image-repos --capabilities CAPABILITY_IAM --confirm-changeset --tags Project=terra --parameter-overrides Stage=dev BedrockEnabled=false AuthEnabled=true ProcessingMode=async FrontendOrigin="$SITE"
```

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "$API_URL/v1/analyses"
```

Expected `401`.

```bash
curl -sS -o /dev/null -w "%{http_code}\n" "$API_URL/v1/analyses" -H "Authorization: Bearer $TOKEN"
```

Expected `200`. To show login in the web app, rebuild the frontend with the pool ids
(E1, but with these two extra variables) and redeploy it (E2–E4):

```bash
NEXT_PUBLIC_API_URL="$API_URL" NEXT_PUBLIC_COGNITO_USER_POOL_ID="$(tout CognitoUserPoolId)" NEXT_PUBLIC_COGNITO_APP_CLIENT_ID="$(tout CognitoAppClientId)" npm --prefix frontend run build
```

---

## Part H — Operating it

### Redeploy after a code change

```bash
sam build -t infra/template.yaml
```

Then the same `sam deploy …` you last used, with **all** its parameters.

### Logs

```bash
MSYS_NO_PATHCONV=1 aws logs tail /aws/lambda/terra-api-dev --follow --profile terra-hackathon --region us-west-2
```

Log groups keep 30 days. Each line is a JSON event (`analysis_completed`,
`analysis_result`, `bedrock_explain_*`).

### ECR storage — the one place free tier can leak

Each image is pushed to its own ECR repository, and every `sam deploy` that changes
the code pushes new layers. **The image size has not been measured** (no Docker was
available where this was written). Private ECR's free allowance is small (check the
current figure on the Billing → Free Tier page); beyond it the rate is roughly
$0.10 per GB-month, so the worst case is cents, not dollars — but measure it.

```bash
aws ecr describe-repositories --profile terra-hackathon --region us-west-2 --query "repositories[].repositoryName" --output text
```

```bash
aws ecr describe-images --repository-name <repository-name-from-above> --profile terra-hackathon --region us-west-2 --query "imageDetails[].[imageTags,imageSizeInBytes]" --output table
```

Keep only the two newest images per repository (run once per repository):

```bash
aws ecr put-lifecycle-policy --repository-name <repository-name> --profile terra-hackathon --region us-west-2 --lifecycle-policy-text '{"rules":[{"rulePriority":1,"description":"keep last 2","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":2},"action":{"type":"expire"}}]}'
```

### What is and is not free (verify on your Billing → Free Tier page — terms change)

| Service | Expectation for Terra at demo scale |
|---|---|
| Lambda, SQS, CloudWatch Logs, DynamoDB | Well inside the free allowances at demo traffic. DynamoDB is on-demand (pay per request — pennies). |
| API Gateway (HTTP API) | Free allowance for new accounts for a limited period, then ~$1 per million requests. |
| Cognito | Free tier covers demo user counts. |
| S3 (results bucket) | Provisioned but **nothing writes to it** today. |
| ECR | Small free allowance — see above. |
| Amplify Hosting | Free tier covers a small static site; manual deploys use no build minutes. |
| Bedrock | **No free tier.** Pay per token; a short explanation is a fraction of a cent. |
| AWS Budgets | The first budgets are free. |

Newer AWS accounts may be on a credit-based free plan with its own restrictions; if
a step is refused for plan reasons, the error says so.

---

## Part I — Tear it all down

New terminal? Re-derive the two values these commands use (and redefine `tout` from C4):

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --profile terra-hackathon --query Account --output text)
```

```bash
APP_ID=$(aws amplify list-apps --profile terra-hackathon --region us-west-2 --query "apps[?name=='terra-frontend'].appId" --output text)
```

```bash
aws amplify delete-app --app-id "$APP_ID" --profile terra-hackathon --region us-west-2
```

```bash
sam delete --stack-name terra-dev --region us-west-2 --profile terra-hackathon
```

`sam delete` asks whether to delete the ECR repositories and the artifact bucket it
created — answer **yes** to both, or they keep costing. If it fails on the results
bucket (CloudFormation cannot delete a non-empty bucket), empty it and retry:

```bash
aws s3 rm "s3://$(tout ResultsBucketName)" --recursive --profile terra-hackathon --region us-west-2
```

```bash
aws budgets delete-budget --account-id "$ACCOUNT_ID" --budget-name terra-monthly --profile terra-hackathon
```

Verify nothing is left:

```bash
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE --profile terra-hackathon --region us-west-2 --query "StackSummaries[].StackName"
```

```bash
aws ecr describe-repositories --profile terra-hackathon --region us-west-2 --query "repositories[].repositoryName"
```

Finally, in the console: **IAM → `terra-deployer` → delete the access key** (and the
user if you are done).

---

## Known gaps (what this runbook does not claim)

- **Never deployed for real.** SAM/Docker builds and every AWS interaction above are unverified; the offline checks cover the template's structure, the Lambda handler and the frontend.
- **Async has never run against real SQS.** Watch the worker log (Part D).
- **Bedrock model availability is unverified**, and Bedrock only writes the explanation text.
- **No per-user job isolation.** Any signed-in user can see all jobs; keep `AuthEnabled=false` for public demos.
- **The S3 results bucket is unused.** Results live in DynamoDB.
- **Job listing is a DynamoDB scan.** Fine at demo scale only.
- **No in-app token refresh** (Cognito tokens last 1 hour).
- **ECR image size is unmeasured.**
- **Amplify's handling of slash-less routes is unverified** (E5 has a check and a fallback).
- **Live analyses of large areas are slow** (~200 s for ~47 km² locally) and concurrent live requests have been seen to fail with a GDAL read error.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `Unable to locate credentials` / wrong account | You omitted `--profile terra-hackathon`, or A3 was not completed. Re-run `aws sts get-caller-identity --profile terra-hackathon`. |
| `docker: command not found` / `Cannot connect to the Docker daemon` | Docker Desktop is not installed or not running (A2). |
| `aws logs tail /aws/...` says "Invalid log group" with a `C:/Program Files/Git/...` path | Git Bash rewrote the path. Prefix the command with `MSYS_NO_PATHCONV=1`. |
| `sam build` cannot find the Dockerfile | You ran it from a different directory. Run it from the repo root with `-t infra/template.yaml`. |
| Stack is in `ROLLBACK_COMPLETE` | The first create failed and the stack cannot be updated. Read the reason: `aws cloudformation describe-stack-events --stack-name terra-dev --profile terra-hackathon --region us-west-2 --max-items 15`. Then `sam delete --stack-name terra-dev …` and deploy again. |
| `curl "$API_URL/health"` → 404 or `{"message":"Not Found"}` | `API_URL` has a stage suffix (`/dev`) — re-read C4 — or the deploy did not finish. |
| 503 / `Service Unavailable` on a live analysis in **sync** mode | The 30 s API Gateway cap. Live runs need `ProcessingMode=async` (Part D). |
| Browser: CORS error | `FrontendOrigin` does not exactly match the site origin (E6). |
| Job stays `created` forever in async mode | The worker is not consuming. Check the worker log (D1), the DLQ (D5) and that `ProcessingMode=async` was deployed. |
| Job goes `failed` with a "Read failed" message on a live run | A known GDAL/network read failure on concurrent or very large reads. Retry with a smaller area, one at a time. |
