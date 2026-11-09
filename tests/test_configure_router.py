import pytest

from configure_router import parse_tunnels, render_frr, render_swanctl


def tunnel_xml(i, psk):
    return f"""
  <ipsec_tunnel>
    <customer_gateway>
      <tunnel_outside_address><ip_address>54.0.0.1</ip_address></tunnel_outside_address>
      <tunnel_inside_address>
        <ip_address>169.254.{i}.2</ip_address>
        <network_mask>255.255.255.252</network_mask>
        <network_cidr>30</network_cidr>
      </tunnel_inside_address>
      <bgp><asn>65020</asn><hold_time>30</hold_time></bgp>
    </customer_gateway>
    <vpn_gateway>
      <tunnel_outside_address><ip_address>3.0.0.{i}</ip_address></tunnel_outside_address>
      <tunnel_inside_address>
        <ip_address>169.254.{i}.1</ip_address>
        <network_cidr>30</network_cidr>
      </tunnel_inside_address>
      <bgp><asn>64512</asn><hold_time>30</hold_time></bgp>
    </vpn_gateway>
    <ike><pre_shared_key>{psk}</pre_shared_key></ike>
  </ipsec_tunnel>"""


def vpn_xml(*tunnels):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<vpn_connection id="vpn-test">'
            + "".join(tunnels) + "\n</vpn_connection>")


SAMPLE = vpn_xml(tunnel_xml(10, "key_one.A"), tunnel_xml(20, "key_two.B"))


def test_parse_reads_both_tunnels():
    t1, t2 = parse_tunnels(SAMPLE)
    assert t1["vgw_outside"] == "3.0.0.10"
    assert t1["cgw_inside"] == "169.254.10.2"
    assert t1["vgw_inside"] == "169.254.10.1"
    assert t1["inside_prefix"] == "30"
    assert t1["vgw_asn"] == "64512"
    assert t2["psk"] == "key_two.B"


def test_parse_rejects_incomplete_config():
    with pytest.raises(SystemExit):
        parse_tunnels(vpn_xml(tunnel_xml(10, "only_one")))


def test_swanctl_uses_strong_proposals_and_one_interface_per_tunnel():
    conf = render_swanctl(parse_tunnels(SAMPLE), "10.20.1.46")
    assert conf.count("\n    proposals = aes256-sha256-ecp384") == 2  # IKE
    assert conf.count("esp_proposals = aes256-sha256-ecp384") == 2       # IPsec
    assert "if_id_in = 1" in conf and "if_id_in = 2" in conf
    assert "id = 54.0.0.1" in conf  # local identity is the public IP, not the private one


def test_frr_peers_with_both_aws_endpoints():
    conf = render_frr(parse_tunnels(SAMPLE), "10.20.1.46", "10.20.1.1")
    assert "neighbor 169.254.10.1 remote-as 64512" in conf
    assert "neighbor 169.254.20.1 remote-as 64512" in conf
    assert "network 10.20.0.0/16" in conf
    assert "ip route 10.20.0.0/16 10.20.1.1" in conf
