# ---------------------------------------------------------------------------
# Office router: Ubuntu running strongSwan (IPsec) and FRR (BGP).
# ---------------------------------------------------------------------------

# Look up the latest Ubuntu 24.04 LTS image from Canonical's official
# public parameter, instead of hardcoding an image ID that goes stale.
data "aws_ssm_parameter" "ubuntu" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

# --- Access through Session Manager instead of SSH --------------------------
resource "aws_iam_role" "router" {
  name = "office-router-ssm"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "router_ssm" {
  role       = aws_iam_role.router.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "router" {
  name = "office-router-ssm"
  role = aws_iam_role.router.name
}

# --- Firewall ---------------------------------------------------------------
resource "aws_security_group" "office_router" {
  name        = "office-router"
  description = "Office router: IPsec from the internet, all traffic from the office"
  vpc_id      = aws_vpc.office.id

  # IKE (key exchange) and IPsec NAT traversal, used to build the tunnels.
  # Open to any address for now; narrowed to AWS's two tunnel endpoints
  # once the VPN exists (Phase 4).
  ingress {
    description = "IKE"
    from_port   = 500
    to_port     = 500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "IPsec NAT traversal"
    from_port   = 4500
    to_port     = 4500
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Office machines send their cloud-bound traffic through the router.
  ingress {
    description = "Traffic from the office network"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.office_vpc_cidr]
  }

  # No SSH (port 22) rule: admin access is through Session Manager.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "office-router-sg" }
}

# --- The router itself ------------------------------------------------------
resource "aws_instance" "office_router" {
  ami                    = data.aws_ssm_parameter.ubuntu.value
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.office_public.id
  vpc_security_group_ids = [aws_security_group.office_router.id]
  iam_instance_profile   = aws_iam_instance_profile.router.name

  # A router forwards traffic that is not addressed to itself, which AWS
  # drops by default. Turn that check off for this instance.
  source_dest_check = false

  # Require IMDSv2 tokens to protect the instance's credentials from SSRF.
  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 8
  }

  # Runs once on first boot: turn the server into a router and install
  # the VPN and routing software. Their configuration comes in Phase 4.
  user_data = <<-USERDATA
    #!/bin/bash
    set -euxo pipefail
    echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-router.conf
    sysctl --system
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y frr strongswan strongswan-swanctl
    sed -i 's/^bgpd=no/bgpd=yes/' /etc/frr/daemons
    systemctl restart frr
  USERDATA

  tags = { Name = "office-router" }
}

# A public IP that does not change, so the VPN configuration stays valid.
resource "aws_eip" "office_router" {
  domain   = "vpc"
  instance = aws_instance.office_router.id
  tags     = { Name = "office-router-eip" }
}

# Office workstations reach the cloud network through the router.
resource "aws_route" "office_to_cloud" {
  route_table_id         = aws_route_table.office_private.id
  destination_cidr_block = var.cloud_vpc_cidr
  network_interface_id   = aws_instance.office_router.primary_network_interface_id
}
