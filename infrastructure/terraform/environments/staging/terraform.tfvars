# Staging environment — smaller instances, single AZ where possible.
environment        = "staging"
region             = "eu-west-1"
availability_zones = ["eu-west-1a", "eu-west-1b"]

# RDS — smaller instance for staging
rds_instance_class = "db.r6g.large"
rds_storage_size   = 50

# OpenSearch — smaller cluster
opensearch_instance_type  = "r6g.large.search"
opensearch_instance_count = 2
opensearch_ebs_volume     = 30

# EKS — reduced node counts
eks_app_desired       = 2
eks_app_min           = 1
eks_temporal_desired  = 1
eks_temporal_min      = 1
eks_monitoring_desired = 1
eks_monitoring_min    = 1
