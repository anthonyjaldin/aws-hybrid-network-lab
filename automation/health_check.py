#!/usr/bin/env python3
"""Check the hybrid network end to end and report PASS, WARN, or FAIL.

Checks, from the outside in:
  1. AWS reports both VPN tunnels UP
  2. The cloud private route table learned the office route over BGP
  3. The office router has both BGP sessions established
  4. The office can ping the cloud app server across the VPN
  5. The office can load the app server's web page across the VPN

Exits with status 1 if any check fails, so it can be used in scripts.

Usage:
    python automation/health_check.py
"""
import json
import re
import sys

import boto3

from configure_router import find_router, run_on_router

OFFICE_CIDR = "10.20.0.0/16"
CLOUD_PRIVATE_RT = "cloud-private-rt"
APP_SERVER_NAME = "cloud-app-server"
VPN_NAME = "office-vpn"

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


# --- Evaluation: pure functions, unit tested without AWS --------------------

def evaluate_tunnels(telemetry):
    """telemetry: the VgwTelemetry list from describe_vpn_connections."""
    up = sum(1 for t in telemetry if t.get("Status") == "UP")
    total = len(telemetry)
    detail = f"{up}/{total} tunnels UP"
    if total and up == total:
        return PASS, detail
    if up:
        return WARN, detail + " (no redundancy)"
    return FAIL, detail + " (AWS status can lag a few minutes)"


def evaluate_routes(routes, cidr=OFFICE_CIDR):
    """routes: the Routes list of a route table."""
    for r in routes:
        if r.get("DestinationCidrBlock") == cidr:
            learned = r.get("Origin") == "EnableVgwRoutePropagation"
            active = r.get("State") == "active"
            target = r.get("GatewayId", "?")
            if learned and active:
                return PASS, f"{cidr} via {target} (learned over BGP)"
            return FAIL, f"{cidr} via {target}, origin {r.get('Origin')}, state {r.get('State')}"
    return FAIL, f"no route to {cidr}"


def evaluate_bgp(summary_json):
    """summary_json: output of FRR's `show bgp summary json`."""
    try:
        peers = json.loads(summary_json)["ipv4Unicast"]["peers"]
    except (ValueError, KeyError, TypeError):
        return FAIL, "could not read BGP summary from the router"
    if not peers:
        return FAIL, "no BGP neighbors configured"
    established = {ip: p for ip, p in peers.items() if p.get("state") == "Established"}
    prefixes = ", ".join(f"{ip}: {p.get('pfxRcd', 0)} received"
                         for ip, p in sorted(established.items()))
    detail = f"{len(established)}/{len(peers)} established"
    if prefixes:
        detail += f" ({prefixes})"
    if len(established) == len(peers) and all(p.get("pfxRcd", 0) > 0 for p in established.values()):
        return PASS, detail
    if established:
        return WARN, detail
    return FAIL, detail


def evaluate_ping(output):
    """output: text from `ping -c N`."""
    loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", output)
    if not loss:
        return FAIL, "no ping result"
    loss_pct = float(loss.group(1))
    avg = re.search(r"= [\d.]+/([\d.]+)/", output)
    detail = f"{loss_pct:g}% loss" + (f", avg {avg.group(1)} ms" if avg else "")
    if loss_pct == 0:
        return PASS, detail
    if loss_pct < 100:
        return WARN, detail
    return FAIL, detail


def evaluate_http(output):
    """output: the body returned by curl."""
    if "You reached me over the VPN" in output:
        return PASS, "page served by the app server"
    return FAIL, "no response from the app server"


# --- Collection: talks to AWS -----------------------------------------------

def split_sections(text):
    """Split router output on ===NAME=== markers into a dict."""
    sections, current = {}, None
    for line in text.splitlines():
        marker = re.fullmatch(r"===(\w+)===", line.strip())
        if marker:
            current = marker.group(1)
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def find_app_server_ip(ec2):
    reservations = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": [APP_SERVER_NAME]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ])["Reservations"]
    instances = [i for r in reservations for i in r["Instances"]]
    return instances[0]["PrivateIpAddress"] if instances else None


def collect(ec2, ssm):
    results = []

    vpns = ec2.describe_vpn_connections(Filters=[
        {"Name": "tag:Name", "Values": [VPN_NAME]},
        {"Name": "state", "Values": ["available"]},
    ])["VpnConnections"]
    telemetry = vpns[0]["VgwTelemetry"] if vpns else []
    results.append(("VPN tunnels (AWS view)", *evaluate_tunnels(telemetry)))

    tables = ec2.describe_route_tables(Filters=[
        {"Name": "tag:Name", "Values": [CLOUD_PRIVATE_RT]},
    ])["RouteTables"]
    routes = tables[0]["Routes"] if tables else []
    results.append(("Cloud route to office", *evaluate_routes(routes)))

    router = find_router(ec2)
    src = router["PrivateIpAddress"]
    app_ip = find_app_server_ip(ec2)
    script = "\n".join([
        "echo '===BGP==='",
        "vtysh -c 'show bgp summary json'",
    ])
    if app_ip:
        script += "\n" + "\n".join([
            "echo '===PING==='",
            f"ping -c 3 -W 2 -I {src} {app_ip} || true",
            "echo '===HTTP==='",
            f"curl -s --max-time 5 --interface {src} http://{app_ip} || true",
        ])
    inv = run_on_router(ssm, router["InstanceId"], script)
    sections = split_sections(inv.get("StandardOutputContent", ""))

    results.append(("BGP sessions (router view)", *evaluate_bgp(sections.get("BGP", ""))))
    if app_ip:
        results.append((f"Ping office -> app {app_ip}", *evaluate_ping(sections.get("PING", ""))))
        results.append((f"HTTP office -> app {app_ip}", *evaluate_http(sections.get("HTTP", ""))))
    else:
        results.append(("App server", FAIL, f"no running instance named {APP_SERVER_NAME}"))
    return results


def print_report(results):
    width = max(len(name) for name, _, _ in results) + 2
    print(f"{'CHECK'.ljust(width)}STATUS  DETAIL")
    for name, status, detail in results:
        print(f"{name.ljust(width)}{status.ljust(8)}{detail}")
    failed = sum(1 for _, s, _ in results if s == FAIL)
    warned = sum(1 for _, s, _ in results if s == WARN)
    print(f"\n{len(results) - failed - warned} passed, {warned} warnings, {failed} failed")
    return failed


def main():
    results = collect(boto3.client("ec2"), boto3.client("ssm"))
    sys.exit(1 if print_report(results) else 0)


if __name__ == "__main__":
    main()
