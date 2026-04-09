# Production environment — full-size, Multi-AZ, matching docs/infrastructure.md.
# Estimated monthly cost: ~$1,860 (without MSK).
environment        = "production"
region             = "eu-west-1"
availability_zones = ["eu-west-1a", "eu-west-1b"]

# RDS — production size
rds_instance_class = "db.r6g.xlarge"
rds_storage_size   = 100

# OpenSearch — 3-node cluster
opensearch_instance_type  = "r6g.large.search"
opensearch_instance_count = 3
opensearch_ebs_volume     = 50

# EKS — full node counts
eks_app_desired       = 3
eks_app_min           = 2
eks_temporal_desired  = 2
eks_temporal_min      = 1
eks_monitoring_desired = 2
eks_monitoring_min    = 1
