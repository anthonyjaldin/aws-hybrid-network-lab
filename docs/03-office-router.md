# Phase 3: Office router

An Ubuntu 24.04 EC2 instance in the office public subnet acts as the
company's on-premises router.

| Setting | Value | Why |
|---|---|---|
| Software | FRR 8.4.4 (BGP), strongSwan (IPsec) | Open source routing and VPN, used in production networks |
| Public IP | Elastic IP | Stays fixed, so the VPN configuration remains valid |
| source_dest_check | false | AWS drops traffic an instance did not send or receive; a router forwards other hosts' traffic |
| net.ipv4.ip_forward | 1 | Lets Linux forward packets between networks |
| Admin access | Session Manager only, no SSH rule | No inbound admin port, no SSH keys, every session logged with the IAM identity |
| Instance metadata | IMDSv2 required | Protects the instance role's credentials from SSRF |
| Disk | Encrypted gp3 | Encryption at rest baseline |

The office private route table sends 10.10.0.0/16 (the cloud) to the
router's network interface.

## Verification
Connected with `aws ssm start-session` and confirmed on the instance
(ip-10-20-1-198): cloud-init finished, `net.ipv4.ip_forward = 1`, FRR
active. strongSwan packages installed by the first-boot script; the VPN
service is configured in Phase 4.

Note: the first attempt ran the checks in the local WSL terminal instead
of on the router. The prompt (`ajalding@DESKTOP` vs `ssm-user@ip-10-20-1-x`)
shows which machine a command runs on.
