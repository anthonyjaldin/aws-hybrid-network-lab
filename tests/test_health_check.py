import json

from health_check import (FAIL, PASS, WARN, evaluate_bgp, evaluate_http,
                          evaluate_ping, evaluate_routes, evaluate_tunnels,
                          split_sections)


# --- VPN tunnels ------------------------------------------------------------

def test_both_tunnels_up_passes():
    assert evaluate_tunnels([{"Status": "UP"}, {"Status": "UP"}])[0] == PASS


def test_one_tunnel_up_warns_about_redundancy():
    status, detail = evaluate_tunnels([{"Status": "UP"}, {"Status": "DOWN"}])
    assert status == WARN
    assert "no redundancy" in detail


def test_no_tunnels_up_fails():
    assert evaluate_tunnels([{"Status": "DOWN"}, {"Status": "DOWN"}])[0] == FAIL


def test_missing_vpn_fails():
    assert evaluate_tunnels([])[0] == FAIL


# --- Route propagation ------------------------------------------------------

LOCAL = {"DestinationCidrBlock": "10.10.0.0/16", "GatewayId": "local",
         "Origin": "CreateRouteTable", "State": "active"}


def test_route_learned_over_bgp_passes():
    bgp = {"DestinationCidrBlock": "10.20.0.0/16", "GatewayId": "vgw-1",
           "Origin": "EnableVgwRoutePropagation", "State": "active"}
    status, detail = evaluate_routes([LOCAL, bgp])
    assert status == PASS
    assert "vgw-1" in detail


def test_missing_office_route_fails():
    assert evaluate_routes([LOCAL])[0] == FAIL


def test_static_route_is_not_counted_as_bgp():
    static = {"DestinationCidrBlock": "10.20.0.0/16", "GatewayId": "vgw-1",
              "Origin": "CreateRoute", "State": "active"}
    assert evaluate_routes([LOCAL, static])[0] == FAIL


def test_blackholed_route_fails():
    dead = {"DestinationCidrBlock": "10.20.0.0/16", "GatewayId": "vgw-1",
            "Origin": "EnableVgwRoutePropagation", "State": "blackhole"}
    assert evaluate_routes([LOCAL, dead])[0] == FAIL


# --- BGP on the router ------------------------------------------------------

def bgp_json(*states):
    peers = {f"169.254.{i}.1": {"remoteAs": 64512, "state": s,
                                 "pfxRcd": 1 if s == "Established" else 0}
             for i, s in enumerate(states)}
    return json.dumps({"ipv4Unicast": {"routerId": "10.20.1.46", "peers": peers}})


def test_both_bgp_sessions_established_passes():
    status, detail = evaluate_bgp(bgp_json("Established", "Established"))
    assert status == PASS
    assert "2/2 established" in detail


def test_one_bgp_session_down_warns():
    assert evaluate_bgp(bgp_json("Established", "Active"))[0] == WARN


def test_no_bgp_sessions_fails():
    assert evaluate_bgp(bgp_json("Active", "Connect"))[0] == FAIL


def test_established_but_no_routes_received_warns():
    data = json.loads(bgp_json("Established"))
    data["ipv4Unicast"]["peers"]["169.254.0.1"]["pfxRcd"] = 0
    assert evaluate_bgp(json.dumps(data))[0] == WARN


def test_unreadable_bgp_output_fails():
    assert evaluate_bgp("% Unknown command")[0] == FAIL


# --- Ping and HTTP ----------------------------------------------------------

PING_OK = """PING 10.10.2.215 (10.10.2.215) from 10.20.1.46 : 56(84) bytes of data.
--- 10.10.2.215 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 1.418/1.497/1.664/0.099 ms"""

PING_DEAD = """--- 10.10.2.215 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2040ms"""


def test_ping_without_loss_passes():
    status, detail = evaluate_ping(PING_OK)
    assert status == PASS
    assert "avg 1.497 ms" in detail


def test_partial_loss_warns():
    assert evaluate_ping(PING_OK.replace(" 0% packet loss", " 33.3333% packet loss"))[0] == WARN


def test_total_loss_fails():
    assert evaluate_ping(PING_DEAD)[0] == FAIL


def test_http_page_passes():
    assert evaluate_http("Hello from the cloud app server (x). You reached me over the VPN.")[0] == PASS


def test_http_timeout_fails():
    assert evaluate_http("")[0] == FAIL


# --- Parsing router output --------------------------------------------------

def test_split_sections():
    text = "===BGP===\n{\"a\": 1}\n===PING===\nline1\nline2\n===HTTP===\nhello"
    assert split_sections(text) == {"BGP": '{"a": 1}', "PING": "line1\nline2", "HTTP": "hello"}
