# Phase 2: Network design

| Network | CIDR | Purpose |
|---|---|---|
| Cloud VPC | 10.10.0.0/16 | The company's AWS environment |
| Cloud public subnet | 10.10.1.0/24 | Reserved for later |
| Cloud private subnet | 10.10.2.0/24 | App server, no internet route |
| Office VPC | 10.20.0.0/16 | Simulated on-premises office |
| Office public subnet | 10.20.1.0/24 | Office router (FRR + IPsec), public IP |
| Office private subnet | 10.20.2.0/24 | Office workstation |

BGP: AWS virtual private gateway ASN 64512, office router ASN 65020
(both private ASNs).

## Decisions
- The two networks use non-overlapping ranges, so routes across the VPN
  are unambiguous.
- The office is simulated in a second VPC because a site-to-site VPN needs
  a customer router with a public IP, which a home connection cannot
  provide reliably.
- The cloud app server sits in a private subnet with no internet route;
  it is reachable only from the office across the VPN.
- Single availability zone (us-east-1a) to keep the lab small and cheap.
  A production design would span at least two.

## Verification: cloud VPC
Built with `terraform apply` (9 resources), then checked the route tables
with the AWS CLI rather than trusting the code:

| Route table | Routes |
|---|---|
| cloud-private-rt | 10.10.0.0/16 -> local |
| cloud-public-rt | 10.10.0.0/16 -> local, 0.0.0.0/0 -> internet gateway |

The private subnet has no default route, so any packet to an address
outside the VPC has no matching route and is dropped (longest prefix
match finds nothing). That missing route is what makes it private.
