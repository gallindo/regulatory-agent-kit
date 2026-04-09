output "endpoint" {
  description = "RDS instance endpoint (hostname)"
  value       = aws_db_instance.this.address
}

output "port" {
  description = "RDS instance port"
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Name of the default database"
  value       = aws_db_instance.this.db_name
}

output "instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.this.id
}
