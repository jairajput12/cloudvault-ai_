# IAM Policies — cloudvault-lambda-role

All Lambda functions in this project share one execution role,
`cloudvault-lambda-role`, built up in layers of least-privilege inline
policies as features were added.

## AWSLambdaBasicExecutionRole (AWS managed)
Lets Lambda write logs to CloudWatch. Attached by default when creating
any Lambda function.

## cloudvault-dynamodb-write
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowDynamoDBWrite",
            "Effect": "Allow",
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Scan",
                "dynamodb:GetItem",
                "dynamodb:DeleteItem"
            ],
            "Resource": "arn:aws:dynamodb:ap-southeast-2:187494036675:table/cloudvault-documents"
        }
    ]
}
```

## cloudvault-s3-read (also covers write, despite the name)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowS3ReadWrite",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::cloudvault-ai-jai-2026/*"
        }
    ]
}
```

## cloudvault-nova-invoke
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowNovaInvoke",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": "arn:aws:bedrock:ap-southeast-2::foundation-model/amazon.nova-lite-v1:0"
        }
    ]
}
```

## cloudvault-textract
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowTextract",
            "Effect": "Allow",
            "Action": ["textract:DetectDocumentText"],
            "Resource": "*"
        }
    ]
}
```
Textract does not support resource-level (ARN) restriction for this
action, so `"*"` is expected here — the *action* itself is still scoped
to text detection only, nothing else in the account.

## Notes / lessons learned
- IAM roles are **global**, but the resources they reference (DynamoDB
  tables, S3 buckets) are **regional** — a mismatched region in a
  `Resource` ARN causes `AccessDenied` even when the policy looks
  correct at a glance.
- Anthropic models on Bedrock bill through AWS Marketplace and require
  a verified payment method; Amazon's own models (Nova) are first-party
  and bill directly, avoiding that requirement — relevant if testing
  without a card on file.
