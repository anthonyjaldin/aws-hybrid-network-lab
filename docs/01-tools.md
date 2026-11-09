# Phase 1: Tools

All tools run inside WSL (Ubuntu 26.04).

| Tool | Version | Purpose |
|---|---|---|
| AWS CLI | 2.39.6 | Control AWS from the terminal; provides credentials to Terraform |
| Terraform | 1.17.1 | Build and destroy the lab as code |
| Python | 3.14 | Network automation and detection scripts |

## Verifying downloads
Terraform was installed from the official zip instead of a package
repository, and verified before installing:
1. The SHA256SUMS file's GPG signature was checked against HashiCorp's
   public key (primary key fingerprint
   C874 011F 0AB4 0511 0D02 1055 3436 5D94 72D7 468F, matching the one
   published at hashicorp.com/security).
2. The zip's SHA-256 checksum was checked against that signed list.

This protects against a tampered download (a supply chain attack), which
matters because Terraform runs with admin access to the AWS account.
