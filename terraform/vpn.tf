# ---------------------------------------------------------------------------
# Site-to-site VPN between the cloud VPC and the office router, with BGP.
# ---------------------------------------------------------------------------

# AWS's VPN router, attached to the cloud VPC.
resource "aws_vpn_gateway" "cloud" {
  vpc_id          = aws_vpc.cloud.id
  amazon_side_asn = 64512
  tags            = { Name = "cloud-vgw" }
}

# AWS's record of the office router: its public IP and BGP ASN.
resource "aws_customer_gateway" "office" {
  bgp_asn    = 65020
  ip_address = aws_eip.office_router.public_ip
  type       = "ipsec.1"
  tags       = { Name = "office-cgw" }
}

# The VPN itself. AWS builds two tunnels to two separate endpoints.
# Only strong algorithms are allowed; AWS's defaults also accept weaker
# options such as SHA-1, which a downgrade attack could force.
resource "aws_vpn_connection" "office" {
  vpn_gateway_id      = aws_vpn_gateway.cloud.id
  customer_gateway_id = aws_customer_gateway.office.id
  type                = "ipsec.1"
  static_routes_only  = false # routes are exchanged with BGP

  tunnel1_ike_versions                 = ["ikev2"]
  tunnel1_phase1_encryption_algorithms = ["AES256"]
  tunnel1_phase1_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase1_dh_group_numbers      = [20]
  tunnel1_phase2_encryption_algorithms = ["AES256"]
  tunnel1_phase2_integrity_algorithms  = ["SHA2-256"]
  tunnel1_phase2_dh_group_numbers      = [20]

  tunnel2_ike_versions                 = ["ikev2"]
  tunnel2_phase1_encryption_algorithms = ["AES256"]
  tunnel2_phase1_integrity_algorithms  = ["SHA2-256"]
  tunnel2_phase1_dh_group_numbers      = [20]
  tunnel2_phase2_encryption_algorithms = ["AES256"]
  tunnel2_phase2_integrity_algorithms  = ["SHA2-256"]
  tunnel2_phase2_dh_group_numbers      = [20]

  tags = { Name = "office-vpn" }
}

# Let BGP-learned routes appear in the cloud's private route table.
resource "aws_vpn_gateway_route_propagation" "cloud_private" {
  vpn_gateway_id = aws_vpn_gateway.cloud.id
  route_table_id = aws_route_table.cloud_private.id
}

locals {
  # AWS's two tunnel endpoints, used to lock down the router's firewall.
  aws_tunnel_cidrs = [
    "${aws_vpn_connection.office.tunnel1_address}/32",
    "${aws_vpn_connection.office.tunnel2_address}/32",
  ]
}
