#!/usr/bin/env python3
"""Detect port scans in VPC Flow Logs.

Reads flow log records (default format, version 2) from CloudWatch Logs,
or from a local file, and raises an alert for:

  * Vertical scans: one source trying many different ports on one host
  * Horizontal sweeps: one source trying many different hosts

Only connections to non-ephemeral ports (below 32768) are counted. Replies
from a server go to the client's ephemeral port, so counting those would
make every busy server look like a scanner.

Exits with status 1 when a scan is detected, so it can drive an alert.

Usage:
    python automation/detect_port_scan.py                 # last 15 minutes
    python automation/detect_port_scan.py --minutes 60 --threshold 10
    python automation/detect_port_scan.py --file flows.txt
"""
import argparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

LOG_GROUP = "/aws-hybrid-network-lab/cloud-vpc-flow-logs"
EPHEMERAL_START = 32768  # Linux default ephemeral port range starts here
FIELDS = ("version", "account_id", "interface_id", "srcaddr", "dstaddr", "srcport",
          "dstport", "protocol", "packets", "bytes", "start", "end", "action", "log_status")
PROTOCOLS = {"1": "ICMP", "6": "TCP", "17": "UDP"}


def parse_record(line):
    """Parse one default-format flow log line. Returns None for lines that
    carry no traffic (NODATA, SKIPDATA) or are not flow records."""
    parts = line.split()
    if len(parts) != len(FIELDS):
        return None
    rec = dict(zip(FIELDS, parts))
    if rec["log_status"] != "OK" or "-" in (rec["srcaddr"], rec["dstport"]):
        return None
    try:
        rec["dstport"] = int(rec["dstport"])
        rec["start"] = int(rec["start"])
        rec["end"] = int(rec["end"])
    except ValueError:
        return None
    return rec


def detect(records, threshold=15):
    """Return a list of alerts, most severe first."""
    ports = defaultdict(set)          # (src, dst) -> ports tried
    rejected = defaultdict(int)       # (src, dst) -> rejected flows
    hosts = defaultdict(set)          # src -> hosts tried
    seen = defaultdict(list)          # src -> timestamps

    for r in records:
        if r["dstport"] >= EPHEMERAL_START or r["protocol"] not in ("6", "17"):
            continue
        key = (r["srcaddr"], r["dstaddr"])
        ports[key].add(r["dstport"])
        hosts[r["srcaddr"]].add(r["dstaddr"])
        seen[r["srcaddr"]] += [r["start"], r["end"]]
        if r["action"] == "REJECT":
            rejected[key] += 1

    alerts = []
    for (src, dst), tried in ports.items():
        if len(tried) >= threshold:
            alerts.append({
                "type": "vertical port scan",
                "source": src,
                "target": dst,
                "count": len(tried),
                "rejected": rejected[(src, dst)],
                "sample": sorted(tried)[:10],
                "first_seen": min(seen[src]),
                "last_seen": max(seen[src]),
            })
    for src, targets in hosts.items():
        if len(targets) >= threshold:
            alerts.append({
                "type": "horizontal sweep",
                "source": src,
                "target": f"{len(targets)} hosts",
                "count": len(targets),
                "rejected": sum(n for (s, _), n in rejected.items() if s == src),
                "sample": sorted(targets)[:10],
                "first_seen": min(seen[src]),
                "last_seen": max(seen[src]),
            })
    return sorted(alerts, key=lambda a: a["count"], reverse=True)


def fetch_from_cloudwatch(minutes):
    import boto3

    logs = boto3.client("logs")
    start_ms = int((time.time() - minutes * 60) * 1000)
    pages = logs.get_paginator("filter_log_events").paginate(
        logGroupName=LOG_GROUP, startTime=start_ms)
    for page in pages:
        for event in page["events"]:
            yield event["message"]


def fmt_time(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%H:%M:%S UTC")


def main():
    parser = argparse.ArgumentParser(description="Detect port scans in VPC Flow Logs.")
    parser.add_argument("--minutes", type=int, default=15,
                        help="how far back to read from CloudWatch Logs (default 15)")
    parser.add_argument("--threshold", type=int, default=15,
                        help="distinct ports or hosts that count as a scan (default 15)")
    parser.add_argument("--file", help="read flow log lines from a file instead of AWS")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            lines = f.read().splitlines()
    else:
        lines = list(fetch_from_cloudwatch(args.minutes))

    records = [r for r in map(parse_record, lines) if r]
    accepted = sum(1 for r in records if r["action"] == "ACCEPT")
    print(f"Read {len(records)} flow records ({accepted} accepted, "
          f"{len(records) - accepted} rejected)")

    alerts = detect(records, args.threshold)
    if not alerts:
        print(f"No scans detected (threshold: {args.threshold} ports or hosts).")
        return
    for a in alerts:
        print(f"\nALERT: {a['type']} from {a['source']} against {a['target']}")
        print(f"  {a['count']} distinct {'ports' if 'port' in a['type'] else 'hosts'}, "
              f"{a['rejected']} rejected by the firewall")
        print(f"  sample: {', '.join(map(str, a['sample']))}")
        print(f"  seen {fmt_time(a['first_seen'])} to {fmt_time(a['last_seen'])}")
    sys.exit(1)


if __name__ == "__main__":
    main()
