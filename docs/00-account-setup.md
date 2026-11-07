# Phase 0: AWS account setup

Goal: secure the AWS account before building anything in it.

## Done
- Root user: added a passkey and a backup authenticator app (MFA), and
  confirmed root has no access keys. Root can do anything, including
  closing the account, so it is locked away and not used day to day.
- IAM users: Anthony (admin, for my own daily work) and s3-auditor
  (read only S3 access for my S3 auditor tool, following least privilege).

## To do
- (done, see below)
- Budget alert at $5
- Use us-east-1 (N. Virginia) as the default region

## Cost plan
- No AWS credits on this account, so the lab runs on pay-as-you-go pricing.
- Main cost is the Site-to-Site VPN (about $0.05 per hour) plus a small
  EC2 instance for the office router.
- The lab is built with Terraform and destroyed at the end of every session,
  keeping the estimated total cost around $5 to $15.
- No NAT gateway in the design, since it bills hourly even when idle.

## Admin user
- Anthony has AdministratorAccess through the "admin" IAM group, so
  permissions are managed at the group level rather than per user.
- Console access was enabled without MFA. Added an authenticator app MFA
  device so a stolen password alone cannot be used to sign in.
- No long lived access keys on this user yet.
