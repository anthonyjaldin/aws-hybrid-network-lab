# ---------------------------------------------------------------------------
# App server in the cloud private subnet: reachable only from the office,
# across the VPN. No public IP and no internet route.
# ---------------------------------------------------------------------------
resource "aws_security_group" "app_server" {
  name        = "cloud-app-server"
  description = "App server: ping and HTTP from the office network only"
  vpc_id      = aws_vpc.cloud.id
  tags        = { Name = "cloud-app-server-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "app_ping_from_office" {
  security_group_id = aws_security_group.app_server.id
  description       = "Ping from the office"
  cidr_ipv4         = var.office_vpc_cidr
  ip_protocol       = "icmp"
  from_port         = -1
  to_port           = -1
}

resource "aws_vpc_security_group_ingress_rule" "app_http_from_office" {
  security_group_id = aws_security_group.app_server.id
  description       = "HTTP from the office"
  cidr_ipv4         = var.office_vpc_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

resource "aws_vpc_security_group_egress_rule" "app_to_office" {
  security_group_id = aws_security_group.app_server.id
  description       = "Replies and traffic to the office only"
  cidr_ipv4         = var.office_vpc_cidr
  ip_protocol       = "-1"
}

resource "aws_instance" "app_server" {
  ami                    = data.aws_ssm_parameter.ubuntu.value
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.cloud_private.id
  vpc_security_group_ids = [aws_security_group.app_server.id]

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    encrypted   = true
    volume_type = "gp3"
    volume_size = 8
  }

  # Serve a small page with Python's built-in web server. Nothing is
  # downloaded, since this subnet has no internet access.
  user_data = <<-USERDATA
    #!/bin/bash
    mkdir -p /srv/app
    echo "Hello from the cloud app server ($(hostname)). You reached me over the VPN." > /srv/app/index.html
    systemd-run --unit=app-web python3 -m http.server 80 --directory /srv/app
  USERDATA

  tags = { Name = "cloud-app-server" }
}
