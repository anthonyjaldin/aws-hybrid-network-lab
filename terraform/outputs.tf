output "cloud_vpc_id" {
  value = aws_vpc.cloud.id
}

output "cloud_private_subnet_id" {
  value = aws_subnet.cloud_private.id
}

output "office_vpc_id" {
  value = aws_vpc.office.id
}

output "office_router_public_ip" {
  value = aws_eip.office_router.public_ip
}

output "office_router_instance_id" {
  value = aws_instance.office_router.id
}

output "vpn_connection_id" {
  value = aws_vpn_connection.office.id
}

output "vpn_tunnel_endpoints" {
  description = "AWS's public IPs for the two tunnels"
  value       = [aws_vpn_connection.office.tunnel1_address, aws_vpn_connection.office.tunnel2_address]
}

output "app_server_private_ip" {
  value = aws_instance.app_server.private_ip
}
