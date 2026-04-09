output "domain_endpoint" {
  description = "OpenSearch domain endpoint URL"
  value       = aws_opensearch_domain.this.endpoint
}

output "domain_arn" {
  description = "ARN of the OpenSearch domain"
  value       = aws_opensearch_domain.this.arn
}

output "domain_id" {
  description = "Unique identifier for the OpenSearch domain"
  value       = aws_opensearch_domain.this.domain_id
}
