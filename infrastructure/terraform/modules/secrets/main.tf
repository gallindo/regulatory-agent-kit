################################################################################
# Secrets Manager Secrets
################################################################################

locals {
  secrets = {
    anthropic-api-key = "rak/${var.environment}/anthropic-api-key"
    openai-api-key    = "rak/${var.environment}/openai-api-key"
    github-token      = "rak/${var.environment}/github-token"
    gitlab-token      = "rak/${var.environment}/gitlab-token"
    db-credentials    = "rak/${var.environment}/db-credentials"
    signing-key       = "rak/${var.environment}/signing-key"
  }
}

resource "aws_secretsmanager_secret" "this" {
  for_each = local.secrets

  name        = each.value
  description = "RAK secret: ${each.key} (${var.environment})"

  tags = {
    Name        = each.value
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "this" {
  for_each = local.secrets

  secret_id     = aws_secretsmanager_secret.this[each.key].id
  secret_string = jsonencode({})
}
