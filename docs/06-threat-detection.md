# Phase 6: Threat detection

VPC Flow Logs record every connection attempt in the cloud VPC (accepted
and rejected) to CloudWatch Logs, in 60 second batches with 1 day
retention. The flow logs role can only be assumed by the flow logs
service on behalf of this account (aws:SourceAccount condition).

`automation/detect_port_scan.py` reads the records and alerts on:
- vertical scans: one source trying 15+ ports on one host
- horizontal sweeps: one source trying 15+ hosts

Destination ports of 32768 and above are ignored. Servers reply to the
client's ephemeral port, so counting those would make any busy server
look like a scanner. A unit test covers this false positive case.

## Test: scanning the app server from the office
Simulated a compromised office host with SSM Run Command on the router:

    nc -z -w 1 -s 10.20.1.46 10.10.2.215 20-50

Flow log records, about 2 minutes later:

    10.20.1.46 10.10.2.215 36749 49 6 1 60 ... REJECT OK
    10.20.1.46 10.10.2.215 42521 45 6 1 60 ... REJECT OK

Detector output:

    Read 37 flow records (6 accepted, 31 rejected)
    ALERT: vertical port scan from 10.20.1.46 against 10.10.2.215
      32 distinct ports, 31 rejected by the firewall

The 31 rejected flows are the scanned ports; the 32nd distinct port is
port 80 from the health check. The 6 accepted health check flows alone
did not trigger an alert. Detection latency was about 1 to 3 minutes,
set by the flow log batching interval.
