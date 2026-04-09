output "secret_arns" {
  description = "Map of secret name to ARN"
  value       = { for key, secret in aws_secretsmanager_secret.this : key => secret.arn }
}
