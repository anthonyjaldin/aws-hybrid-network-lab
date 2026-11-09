# The simulated office: stands in for a company's on-premises network.
resource "aws_vpc" "office" {
  cidr_block           = var.office_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "office-vpc" }
}

resource "aws_default_security_group" "office" {
  vpc_id = aws_vpc.office.id
  tags   = { Name = "office-default-deny-all" }
}

resource "aws_internet_gateway" "office" {
  vpc_id = aws_vpc.office.id
  tags   = { Name = "office-igw" }
}

# The office router lives here. It needs a public IP so AWS can reach it
# to build the VPN tunnels.
resource "aws_subnet" "office_public" {
  vpc_id                  = aws_vpc.office.id
  cidr_block              = var.office_public_subnet_cidr
  availability_zone       = var.az
  map_public_ip_on_launch = false

  tags = { Name = "office-public" }
}

# Office workstations. Their traffic to the cloud will go through the
# office router and across the VPN.
resource "aws_subnet" "office_private" {
  vpc_id            = aws_vpc.office.id
  cidr_block        = var.office_private_subnet_cidr
  availability_zone = var.az

  tags = { Name = "office-private" }
}

resource "aws_route_table" "office_public" {
  vpc_id = aws_vpc.office.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.office.id
  }

  tags = { Name = "office-public-rt" }
}

# No internet route. A route to the cloud (10.10.0.0/16) through the
# office router is added once the router exists.
resource "aws_route_table" "office_private" {
  vpc_id = aws_vpc.office.id
  tags   = { Name = "office-private-rt" }
}

resource "aws_route_table_association" "office_public" {
  subnet_id      = aws_subnet.office_public.id
  route_table_id = aws_route_table.office_public.id
}

resource "aws_route_table_association" "office_private" {
  subnet_id      = aws_subnet.office_private.id
  route_table_id = aws_route_table.office_private.id
}
