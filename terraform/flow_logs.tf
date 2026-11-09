# ---------------------------------------------------------------------------
# VPC Flow Logs: a record of every connection attempt in the cloud VPC,
# accepted or rejected. The port scan detector reads these.
# ---------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_cloudwatch_log_group" "cloud_flow_logs" {
  name              = "/aws-hybrid-network-lab/cloud-vpc-flow-logs"
  retention_in_days = 1 # flow logs contain IP addresses; keep them briefly
}

resource "aws_iam_role" "flow_logs" {
  name = "cloud-vpc-flow-logs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
      # Only flow logs in this account may use the role (confused deputy protection).
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "write-cloud-flow-logs"
  role = aws_iam_role.flow_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = "${aws_cloudwatch_log_group.cloud_flow_logs.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
    ]
  })
}

resource "aws_flow_log" "cloud" {
  vpc_id                   = aws_vpc.cloud.id
  traffic_type             = "ALL" # accepted and rejected
  iam_role_arn             = aws_iam_role.flow_logs.arn
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.cloud_flow_logs.arn
  max_aggregation_interval = 60
  tags                     = { Name = "cloud-vpc-flow-logs" }
}
