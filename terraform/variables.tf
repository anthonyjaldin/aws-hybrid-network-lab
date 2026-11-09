variable "region" {
  description = "AWS region for the whole lab"
  type        = string
  default     = "us-east-1"
}

variable "az" {
  description = "Availability zone for the subnets"
  type        = string
  default     = "us-east-1a"
}

variable "cloud_vpc_cidr" {
  description = "Address range of the cloud VPC"
  type        = string
  default     = "10.10.0.0/16"
}

variable "cloud_public_subnet_cidr" {
  type    = string
  default = "10.10.1.0/24"
}

variable "cloud_private_subnet_cidr" {
  type    = string
  default = "10.10.2.0/24"
}

variable "office_vpc_cidr" {
  description = "Address range of the simulated office network"
  type        = string
  default     = "10.20.0.0/16"
}

variable "office_public_subnet_cidr" {
  type    = string
  default = "10.20.1.0/24"
}

variable "office_private_subnet_cidr" {
  type    = string
  default = "10.20.2.0/24"
}
