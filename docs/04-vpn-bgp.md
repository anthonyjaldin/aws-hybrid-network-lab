# Phase 4: Site-to-site VPN with BGP

## Design
- AWS virtual private gateway (ASN 64512) attached to the cloud VPC.
- Customer gateway record for the office router's Elastic IP (ASN 65020).
- One VPN connection with two tunnels to separate AWS endpoints.
- Crypto restricted to IKEv2, AES-256, SHA-256, DH group 20 (ecp384),
  so the tunnels cannot be negotiated down to weaker options.
- Route-based VPN on the router: one XFRM interface per tunnel, with BGP
  deciding which traffic goes into the tunnels.
- Route propagation writes BGP-learned routes into the cloud private
  route table.
- Router firewall accepts IKE (UDP 500) and NAT-T (UDP 4500) only from
  AWS's two tunnel endpoints.

## Automation
`automation/configure_router.py` reads the tunnel details (outside and
inside addresses, ASNs, pre-shared keys) from the AWS API, renders the
strongSwan and FRR configuration, and applies it on the router with SSM
Run Command. `--dry-run` prints the configuration with the keys hidden.
The keys are never stored in the repository or in Terraform outputs.

Bug found on the first real run: SSM executes commands with /bin/sh,
which on Ubuntu is dash, and dash rejects `set -o pipefail`. The script
now uses `set -eu`.

## Verification
On the router, `show bgp summary`:

| Neighbor | AS | Up/Down | Prefixes received |
|---|---|---|---|
| 169.254.104.185 | 64512 | up | 1 (10.10.0.0/16) |
| 169.254.155.97 | 64512 | up | 1 (10.10.0.0/16) |

strongSwan logs showed dead peer detection exchanges every 10 seconds
on UDP 4500 with both AWS endpoints.

Cloud private route table after BGP converged:

| Destination | Target | Origin |
|---|---|---|
| 10.10.0.0/16 | local | CreateRouteTable |
| 10.20.0.0/16 | vgw | EnableVgwRoutePropagation |

## Known issues and follow ups
- AWS tunnel telemetry lagged a few minutes behind the router, so the
  router (`show bgp summary`) is the faster source of truth.
- The router advertises 2 prefixes per session: its own 10.20.0.0/16 and
  the 10.10.0.0/16 learned from the other tunnel. AWS drops the second
  because its own ASN is in the AS path (loop prevention). An outbound
  prefix filter will fix this in the route filtering phase.
- SSM Run Command keeps command parameters in its history, which includes
  the pre-shared keys. Acceptable for a short lived lab; a production
  setup would have the router read them from Secrets Manager instead.
