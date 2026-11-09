#!/usr/bin/env python3
"""Configure the office router's IPsec tunnels and BGP sessions.

Reads the site-to-site VPN's tunnel details from the AWS API, renders the
strongSwan (IPsec) and FRR (BGP) configuration for the office router, and
applies it on the router with SSM Run Command.

The tunnel pre-shared keys are fetched at runtime. They are never written
to the repository, to Terraform outputs, or to this script's output.

Usage:
    python automation/configure_router.py --dry-run   # show config, keys hidden
    python automation/configure_router.py             # apply to the router
"""
import argparse
import ipaddress
import sys
import time
import xml.etree.ElementTree as ET

import boto3

VPN_NAME = "office-vpn"
ROUTER_NAME = "office-router"
OFFICE_CIDR = "10.20.0.0/16"
OFFICE_ASN = 65020
# Must match the algorithms allowed on the AWS side (vpn.tf):
# AES-256, SHA-256, Diffie-Hellman group 20 (ecp384).
PROPOSAL = "aes256-sha256-ecp384"


def find_vpn(ec2):
    conns = ec2.describe_vpn_connections(Filters=[
        {"Name": "tag:Name", "Values": [VPN_NAME]},
        {"Name": "state", "Values": ["available"]},
    ])["VpnConnections"]
    if len(conns) != 1:
        sys.exit(f"Expected 1 available VPN named {VPN_NAME}, found {len(conns)}")
    return conns[0]


def find_router(ec2):
    reservations = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [ROUTER_NAME]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])["Reservations"]
    instances = [i for r in reservations for i in r["Instances"]]
    if len(instances) != 1:
        sys.exit(f"Expected 1 running instance named {ROUTER_NAME}, found {len(instances)}")
    return instances[0]


def parse_tunnels(config_xml):
    """Extract each tunnel's addresses, BGP ASN, and pre-shared key."""
    root = ET.fromstring(config_xml)
    tunnels = []
    for n, t in enumerate(root.findall("ipsec_tunnel"), start=1):
        tunnels.append({
            "n": n,
            "cgw_outside": t.findtext("customer_gateway/tunnel_outside_address/ip_address"),
            "cgw_inside": t.findtext("customer_gateway/tunnel_inside_address/ip_address"),
            "inside_prefix": t.findtext("customer_gateway/tunnel_inside_address/network_cidr"),
            "vgw_outside": t.findtext("vpn_gateway/tunnel_outside_address/ip_address"),
            "vgw_inside": t.findtext("vpn_gateway/tunnel_inside_address/ip_address"),
            "vgw_asn": t.findtext("vpn_gateway/bgp/asn"),
            "psk": t.findtext("ike/pre_shared_key"),
        })
    if len(tunnels) != 2 or not all(all(t.values()) for t in tunnels):
        sys.exit("Could not read two complete tunnels from the VPN configuration")
    return tunnels


def render_swanctl(tunnels, private_ip):
    """strongSwan config: one IKEv2 connection per AWS tunnel endpoint."""
    public_ip = tunnels[0]["cgw_outside"]
    lines = ["connections {"]
    for t in tunnels:
        n = t["n"]
        lines += [
            f"  aws-tunnel{n} {{",
            "    version = 2",
            f"    local_addrs = {private_ip}",
            f"    remote_addrs = {t['vgw_outside']}",
            f"    proposals = {PROPOSAL}",
            "    dpd_delay = 10s",
            "    local {",
            "      auth = psk",
            f"      id = {public_ip}",
            "    }",
            "    remote {",
            "      auth = psk",
            f"      id = {t['vgw_outside']}",
            "    }",
            "    children {",
            f"      aws-tunnel{n} {{",
            "        local_ts = 0.0.0.0/0",
            "        remote_ts = 0.0.0.0/0",
            f"        esp_proposals = {PROPOSAL}",
            f"        if_id_in = {n}",
            f"        if_id_out = {n}",
            "        start_action = start",
            "        dpd_action = restart",
            "      }",
            "    }",
            "  }",
        ]
    lines += ["}", "", "secrets {"]
    for t in tunnels:
        lines += [
            f"  ike-tunnel{t['n']} {{",
            f"    id = {t['vgw_outside']}",
            f"    secret = \"{t['psk']}\"",
            "  }",
        ]
    lines.append("}")
    return "\n".join(lines)


def render_frr(tunnels, private_ip, gateway):
    """FRR config: an eBGP session to AWS over each tunnel."""
    lines = [
        "configure terminal",
        # Route the whole office range to the VPC router, so it can be
        # announced with BGP and return traffic reaches the office subnets.
        f"ip route {OFFICE_CIDR} {gateway}",
        f"router bgp {OFFICE_ASN}",
        f" bgp router-id {private_ip}",
        # FRR refuses to exchange routes with eBGP peers unless policy is
        # configured; route filtering is added in the BGP hijack phase.
        " no bgp ebgp-requires-policy",
    ]
    for t in tunnels:
        lines += [
            f" neighbor {t['vgw_inside']} remote-as {t['vgw_asn']}",
            f" neighbor {t['vgw_inside']} timers 10 30",
        ]
    lines += [
        " address-family ipv4 unicast",
        f"  network {OFFICE_CIDR}",
        " exit-address-family",
        "end",
        "write memory",
    ]
    return "\n".join(lines)


def render_script(tunnels, private_ip, gateway):
    """The shell script that runs on the router."""
    parts = [
        "set -eu",  # SSM runs scripts with /bin/sh (dash), which has no pipefail
        "export DEBIAN_FRONTEND=noninteractive",
        "# Use the swanctl-based strongSwan service instead of the legacy starter.",
        "dpkg -s charon-systemd >/dev/null 2>&1 || apt-get install -y charon-systemd",
        "systemctl disable --now strongswan-starter 2>/dev/null || true",
        "# Route-based VPN: XFRM interfaces and BGP decide what goes into the",
        "# tunnels, so strongSwan must not install its own routes.",
        "cat > /etc/strongswan.d/zz-aws-lab.conf <<'CONF'",
        "charon {",
        "  install_routes = no",
        "}",
        "CONF",
        "umask 077",
        "cat > /etc/swanctl/conf.d/aws.conf <<'CONF'",
        render_swanctl(tunnels, private_ip),
        "CONF",
        "DEV=$(ip route show default | awk '{print $5; exit}')",
    ]
    for t in tunnels:
        n = t["n"]
        parts += [
            f"ip link del xfrm{n} 2>/dev/null || true",
            f"ip link add xfrm{n} type xfrm dev \"$DEV\" if_id {n}",
            f"ip addr add {t['cgw_inside']}/{t['inside_prefix']} dev xfrm{n}",
            f"ip link set xfrm{n} mtu 1400 up",
        ]
    parts += [
        "systemctl restart strongswan",
        "sleep 3",
        "swanctl --load-all",
        "vtysh <<'VTY'",
        render_frr(tunnels, private_ip, gateway),
        "VTY",
        "echo CONFIGURED",
    ]
    return "\n".join(parts)


def run_on_router(ssm, instance_id, script):
    """Run the script on the router with SSM and wait for the result."""
    cmd_id = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Comment="Configure IPsec tunnels and BGP",
        Parameters={"commands": [script]},
    )["Command"]["CommandId"]
    while True:
        time.sleep(3)
        try:
            inv = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            return inv


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="print the generated configuration with keys hidden")
    args = parser.parse_args()

    ec2 = boto3.client("ec2")
    vpn = find_vpn(ec2)
    router = find_router(ec2)
    tunnels = parse_tunnels(vpn["CustomerGatewayConfiguration"])

    private_ip = router["PrivateIpAddress"]
    subnet = ec2.describe_subnets(SubnetIds=[router["SubnetId"]])["Subnets"][0]
    # AWS's VPC router is always the first host address in a subnet.
    gateway = str(next(ipaddress.ip_network(subnet["CidrBlock"]).hosts()))

    print(f"VPN {vpn['VpnConnectionId']} -> router {router['InstanceId']} ({private_ip})")
    for t in tunnels:
        print(f"  tunnel {t['n']}: AWS {t['vgw_outside']}, inside "
              f"{t['cgw_inside']} <-> {t['vgw_inside']} (AWS ASN {t['vgw_asn']})")

    if args.dry_run:
        hidden = [dict(t, psk="<hidden>") for t in tunnels]
        print("\n" + render_script(hidden, private_ip, gateway))
        return

    inv = run_on_router(boto3.client("ssm"), router["InstanceId"],
                        render_script(tunnels, private_ip, gateway))
    print(f"\nRouter command status: {inv['Status']}")
    print(inv["StandardOutputContent"][-3000:])
    if inv["Status"] != "Success":
        print(inv["StandardErrorContent"][-3000:], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
