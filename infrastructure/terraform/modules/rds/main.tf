resource "aws_db_subnet_group" "this" {
  name       = "rak-${var.environment}-db-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name        = "rak-${var.environment}-db-subnet-group"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_db_parameter_group" "postgres16" {
  name   = "rak-${var.environment}-postgres16-params"
  family = "postgres16"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  tags = {
    Name        = "rak-${var.environment}-postgres16-params"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "random_password" "master_password" {
  length  = 32
  special = true

  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_instance" "this" {
  identifier = "rak-${var.environment}-postgres"

  engine         = "postgres"
  engine_version = "16"
  instance_class = var.instance_class

  allocated_storage = var.storage_size
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.master_password.result

  multi_az            = true
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.postgres16.name

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"

  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "rak-${var.environment}-postgres-final-snapshot"

  tags = {
    Name        = "rak-${var.environment}-postgres"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
