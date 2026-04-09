terraform {
  backend "s3" {
    bucket         = "rak-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "rak-terraform-locks"
  }
}
