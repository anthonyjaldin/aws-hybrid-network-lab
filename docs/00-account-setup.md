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
- (done, see below)
- (done, see below)

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

## Budget alert
- Monthly cost budget "lab-monthly-5usd" at $5, with email alerts at 85%
  actual spend, 100% forecasted spend, and 100% actual spend.
- The forecast alert is the early warning if lab resources are left running.

## Region
- All lab resources are built in us-east-1 (N. Virginia). Keeping
  everything in one region means the pieces can connect and nothing is
  left running somewhere I am not looking.
- The region is also pinned in the Terraform provider and AWS CLI config,
  so it does not depend on what the console happens to show.
