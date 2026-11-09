# Phase 5: End to end verification

An app server (10.10.2.215) runs in the cloud private subnet with no
public IP. Its security group allows ICMP and HTTP only from the office
range (10.20.0.0/16), and its egress only to the office.

Tests run on the office router, sourcing traffic from its office
address (10.20.1.46):

| Test | Command | Result |
|---|---|---|
| Ping across the VPN | `ping -c 4 -I 10.20.1.46 10.10.2.215` | 4/4 received, 0% loss, ~1.5 ms |
| HTTP across the VPN | `curl --interface 10.20.1.46 http://10.10.2.215` | Page served by ip-10-10-2-215 |
| Path taken | `ip route get 10.10.2.215 from 10.20.1.46` | via 169.254.155.97 dev xfrm2 (tunnel 2) |
| Source outside the office range | `curl --max-time 5 http://10.10.2.215` | Timed out (blocked by the security group) |

BGP learned 10.10.0.0/16 on both tunnels and selected tunnel 2 as the
best path; tunnel 1 remains as a backup.
