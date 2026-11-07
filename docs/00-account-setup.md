# Phase 0: AWS account setup

Goal: secure the AWS account before building anything in it.

## Done
- Root user: added a passkey and a backup authenticator app (MFA), and
  confirmed root has no access keys. Root can do anything, including
  closing the account, so it is locked away and not used day to day.
- IAM users: Anthony (admin, for my own daily work) and s3-auditor
  (read only S3 access for my S3 auditor tool, following least privilege).

## To do
- Confirm Anthony has AdministratorAccess and MFA
- Budget alert at $5
- Use us-east-1 (N. Virginia) as the default region
