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
