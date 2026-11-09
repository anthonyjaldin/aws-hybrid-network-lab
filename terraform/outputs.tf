output "cloud_vpc_id" {
  value = aws_vpc.cloud.id
}

output "cloud_private_subnet_id" {
  value = aws_subnet.cloud_private.id
}
