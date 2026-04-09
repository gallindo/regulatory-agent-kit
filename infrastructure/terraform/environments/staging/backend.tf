terraform {
  backend "s3" {
    bucket         = "rak-terraform-state"
    key            = "staging/terraform.tfstate"
    region         = "eu-west-1"
    encrypt        = true
    dynamodb_table = "rak-terraform-locks"
  }
}
