from detect_port_scan import detect, parse_record

ROUTER = "10.20.1.46"
APP = "10.10.2.215"


def flow(src, dst, srcport, dstport, action="ACCEPT", proto=6, start=1000):
    return (f"2 123456789012 eni-abc {src} {dst} {srcport} {dstport} {proto} "
            f"1 60 {start} {start + 30} {action} OK")


def records(lines):
    return [r for r in map(parse_record, lines) if r]


# --- Parsing ----------------------------------------------------------------

def test_parse_valid_record():
    r = parse_record(flow(ROUTER, APP, 51000, 80))
    assert r["srcaddr"] == ROUTER
    assert r["dstport"] == 80
    assert r["action"] == "ACCEPT"


def test_parse_skips_nodata_and_garbage():
    assert parse_record("2 123456789012 eni-abc - - - - - - - 1000 1060 - NODATA") is None
    assert parse_record("not a flow log line") is None


# --- Detection --------------------------------------------------------------

def test_vertical_scan_is_detected():
    lines = [flow(ROUTER, APP, 40000 + p, p, "REJECT") for p in range(20, 51)]
    [alert] = detect(records(lines), threshold=15)
    assert alert["type"] == "vertical port scan"
    assert alert["source"] == ROUTER
    assert alert["target"] == APP
    assert alert["count"] == 31
    assert alert["rejected"] == 31


def test_normal_web_traffic_is_not_a_scan():
    # Many requests to port 80, plus the server's replies to ephemeral ports.
    lines = []
    for i in range(50):
        lines.append(flow(ROUTER, APP, 40000 + i, 80))
        lines.append(flow(APP, ROUTER, 80, 40000 + i))
    assert detect(records(lines), threshold=15) == []


def test_replies_to_ephemeral_ports_are_ignored():
    lines = [flow(APP, ROUTER, 80, 33000 + i) for i in range(100)]
    assert detect(records(lines), threshold=15) == []


def test_below_threshold_is_not_a_scan():
    lines = [flow(ROUTER, APP, 40000 + p, p, "REJECT") for p in range(20, 34)]  # 14 ports
    assert detect(records(lines), threshold=15) == []


def test_horizontal_sweep_is_detected():
    lines = [flow(ROUTER, f"10.10.2.{h}", 40000 + h, 22, "REJECT") for h in range(1, 21)]
    alerts = detect(records(lines), threshold=15)
    assert [a["type"] for a in alerts] == ["horizontal sweep"]
    assert alerts[0]["count"] == 20


def test_icmp_is_not_counted_as_ports():
    lines = [flow(ROUTER, APP, 0, p, proto=1) for p in range(0, 40)]
    assert detect(records(lines), threshold=15) == []
