output "worker_role_arn" {
  description = "ARN of the RAK worker IAM role"
  value       = aws_iam_role.worker.arn
}

output "api_role_arn" {
  description = "ARN of the RAK API IAM role"
  value       = aws_iam_role.api.arn
}

output "litellm_role_arn" {
  description = "ARN of the LiteLLM IAM role"
  value       = aws_iam_role.litellm.arn
}

output "mlflow_role_arn" {
  description = "ARN of the MLflow IAM role"
  value       = aws_iam_role.mlflow.arn
}

output "temporal_role_arn" {
  description = "ARN of the Temporal IAM role"
  value       = aws_iam_role.temporal.arn
}
