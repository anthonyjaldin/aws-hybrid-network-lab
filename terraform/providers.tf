provider "aws" {
  region = var.region

  # Every resource gets these tags automatically, so the lab's resources
  # are easy to find in the console and in the bill.
  default_tags {
    tags = {
      Project   = "aws-hybrid-network-lab"
      ManagedBy = "terraform"
    }
  }
}
