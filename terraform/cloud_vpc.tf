# The cloud VPC: the company's private network inside AWS.
resource "aws_vpc" "cloud" {
  cidr_block           = var.cloud_vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "cloud-vpc" }
}

# Every VPC comes with a default security group that allows all traffic
# between its members. Managing it here with no rules makes it deny
# everything, so nothing can accidentally use it.
resource "aws_default_security_group" "cloud" {
  vpc_id = aws_vpc.cloud.id
  tags   = { Name = "cloud-default-deny-all" }
}

# The VPC's door to the internet. Only the public subnet routes to it.
resource "aws_internet_gateway" "cloud" {
  vpc_id = aws_vpc.cloud.id
  tags   = { Name = "cloud-igw" }
}

resource "aws_subnet" "cloud_public" {
  vpc_id                  = aws_vpc.cloud.id
  cidr_block              = var.cloud_public_subnet_cidr
  availability_zone       = var.az
  map_public_ip_on_launch = false # no automatic public IPs, even here

  tags = { Name = "cloud-public" }
}

resource "aws_subnet" "cloud_private" {
  vpc_id            = aws_vpc.cloud.id
  cidr_block        = var.cloud_private_subnet_cidr
  availability_zone = var.az

  tags = { Name = "cloud-private" }
}

# Public route table: anything not inside the VPC goes to the internet.
resource "aws_route_table" "cloud_public" {
  vpc_id = aws_vpc.cloud.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.cloud.id
  }

  tags = { Name = "cloud-public-rt" }
}

# Private route table: no internet route at all. Only the VPC's own local
# route exists for now; the VPN will add the office's routes via BGP.
resource "aws_route_table" "cloud_private" {
  vpc_id = aws_vpc.cloud.id
  tags   = { Name = "cloud-private-rt" }
}

resource "aws_route_table_association" "cloud_public" {
  subnet_id      = aws_subnet.cloud_public.id
  route_table_id = aws_route_table.cloud_public.id
}

resource "aws_route_table_association" "cloud_private" {
  subnet_id      = aws_subnet.cloud_private.id
  route_table_id = aws_route_table.cloud_private.id
}
