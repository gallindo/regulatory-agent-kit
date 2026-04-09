################################################################################
# Local: IRSA Trust Policy Builder
################################################################################

locals {
  roles = {
    worker   = "rak-worker"
    api      = "rak-api"
    litellm  = "litellm"
    mlflow   = "mlflow"
    temporal = "temporal"
  }
}

################################################################################
# IRSA Trust Policy (shared pattern)
################################################################################

data "aws_iam_policy_document" "irsa_trust" {
  for_each = local.roles

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${each.value}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

################################################################################
# RAK Worker Role
################################################################################

resource "aws_iam_role" "worker" {
  name               = "rak-worker-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["worker"].json

  tags = {
    Name        = "rak-worker-role-${var.environment}"
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid    = "S3ReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:DeleteObject",
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "SecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:*:*:secret:rak/${var.environment}/*"]
  }

  statement {
    sid    = "SESSend"
    effect = "Allow"
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "rak-worker-policy-${var.environment}"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

################################################################################
# RAK API Role
################################################################################

resource "aws_iam_role" "api" {
  name               = "rak-api-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["api"].json

  tags = {
    Name        = "rak-api-role-${var.environment}"
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "api" {
  statement {
    sid    = "SecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:*:*:secret:rak/${var.environment}/*"]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "rak-api-policy-${var.environment}"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

################################################################################
# LiteLLM Role
################################################################################

resource "aws_iam_role" "litellm" {
  name               = "litellm-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["litellm"].json

  tags = {
    Name        = "litellm-role-${var.environment}"
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "litellm" {
  statement {
    sid    = "SecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = ["arn:aws:secretsmanager:*:*:secret:rak/${var.environment}/*"]
  }

  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "litellm" {
  name   = "litellm-policy-${var.environment}"
  role   = aws_iam_role.litellm.id
  policy = data.aws_iam_policy_document.litellm.json
}

################################################################################
# MLflow Role
################################################################################

resource "aws_iam_role" "mlflow" {
  name               = "mlflow-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["mlflow"].json

  tags = {
    Name        = "mlflow-role-${var.environment}"
    Environment = var.environment
  }
}

data "aws_iam_policy_document" "mlflow" {
  statement {
    sid    = "S3MlflowArtifacts"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:DeleteObject",
    ]
    resources = [
      var.s3_bucket_arn,
      "${var.s3_bucket_arn}/mlflow-artifacts/*",
    ]
  }
}

resource "aws_iam_role_policy" "mlflow" {
  name   = "mlflow-policy-${var.environment}"
  role   = aws_iam_role.mlflow.id
  policy = data.aws_iam_policy_document.mlflow.json
}

################################################################################
# Temporal Role
################################################################################

resource "aws_iam_role" "temporal" {
  name               = "temporal-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["temporal"].json

  tags = {
    Name        = "temporal-role-${var.environment}"
    Environment = var.environment
  }
}
