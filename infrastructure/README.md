# Infrastructure

Terraform for the whole stack. The pipeline in `.github/workflows/deploy.yml`
applies it and publishes the frontend on every push to `main`.

## What it creates

| File | Resources |
|---|---|
| `storage.tf` | Private uploads bucket (with CORS for the browser's direct uploads), private site bucket |
| `cdn.tf` | CloudFront distribution in front of the site bucket (HTTPS, default `*.cloudfront.net` domain) |
| `database.tf` | Three on-demand DynamoDB tables: documents, folders, shares |
| `auth.tf` | Cognito user pool and web client |
| `iam.tf` | The Lambda execution role, scoped to this stack's tables, bucket and model |
| `lambda.tf` | The 14 functions from `backend/`, their log groups, and the S3 upload trigger |
| `api.tf` | HTTP API, Cognito JWT authorizer, routes, throttling |

Everything bills per use (Lambda, DynamoDB, API Gateway, Cognito, CloudFront all
have free tiers that cover a POC), so an idle stack costs close to nothing. The
spend that scales with use is Bedrock (Nova Lite) and Textract, and the API is
throttled (`api_throttle_rate`, `api_throttle_burst`) so a public link cannot
run that up quickly. Log groups keep 14 days.

## Region and where data lives

Everything is created in Sydney (`ap-southeast-2`) unless `aws_region` says
otherwise. Files, document records, accounts and the functions stay in that
region.

CloudFront is the one global piece. The origin bucket is in Sydney, and the
`PriceClass_200` setting serves from edge locations that include India.

`bedrock_model_id` defaults to the cross-region Nova Lite profile
(`apac.amazon.nova-lite-v1:0`). Bedrock may run the model in another Asia
Pacific region, so the text sent for summaries, chat and study material can be
processed outside Sydney. The profile has its own daily token quota, which is
usually higher than the in-region model's on a new account. Set the variable to
`amazon.nova-lite-v1:0` to keep the model calls in the region, if the quota
allows it. An organisation policy that limits regions can block the profile.

## One-time setup

The pipeline needs somewhere to keep state and a role to sign in as. Both come
from `bootstrap/`, which a person with admin rights in the AWS account runs to
create them. They then stay in place, and every later deployment uses them with
no further AWS login. It can be run from a machine or from AWS CloudShell:

```bash
cd infrastructure/bootstrap
terraform init
terraform apply
```

If the account already has a GitHub OIDC provider, add
`-var create_oidc_provider=false`. To deploy from a different repository or
region, pass `-var github_repository=owner/name` and `-var aws_region=...`.

Then add the three outputs as repository variables (Settings, Secrets and
variables, Actions, Variables). No AWS keys are stored in GitHub: the pipeline
signs in with the role through GitHub's OIDC token.

| Repository variable | From the bootstrap output |
|---|---|
| `AWS_REGION` | `aws_region` |
| `AWS_DEPLOY_ROLE_ARN` | `deploy_role_arn` |
| `TF_STATE_BUCKET` | `state_bucket` |

GitHub writes the repository into its sign-in token either by name
(`repo:owner/name`) or, for newer repositories, with numeric IDs
(`repo:owner@id/name@id`). The role trusts both exact forms. If a run fails with
"Not authorized to perform sts:AssumeRoleWithWebIdentity", print the token's
`sub` claim in a workflow step and set `github_subject_prefix` in `bootstrap/`
to match it, then apply the bootstrap again.

The deploy job runs in a GitHub environment called `poc`. Add required
reviewers to it (Settings, Environments) if applies should wait for approval.

## Deploying

- **Pull request:** plan only. The plan is in the job summary.
- **Push to `main`:** apply, write `frontend/config.js` from the outputs, sync
  `frontend/` to the site bucket, invalidate CloudFront. The app URL is in the
  job summary.
- **Tear down:** run the Destroy workflow and type `poc` to confirm.

Sign-up verification codes go out through Cognito's built-in email, which is
limited to 50 a day. That is enough for a POC. The model in `bedrock_model_id`
has to be offered by Bedrock in the chosen region; check the model catalog in
the Bedrock console if a deploy works but the AI features return errors.

## Running Terraform locally

```bash
cd infrastructure
terraform init \
  -backend-config="bucket=<state bucket>" \
  -backend-config="key=cloudvault/terraform.tfstate" \
  -backend-config="region=<region>"
terraform plan
```

Use `terraform init -backend=false` and `terraform validate` to check changes
without AWS access. Run `terraform fmt -recursive` before pushing, because the
pull request check fails on unformatted files.

## Moving off the console-built stack

`docs/iam/` holds the policies the original console-built stack used. This
Terraform creates its own resources under the `cloudvault-poc-` prefix and does
not import the old ones, so the two can run side by side.
