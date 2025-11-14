# Cloud API (admin)
variable "confluent_cloud_api_key" {
  description = "Confluent Cloud API Key"
  type        = string
  sensitive   = true
}

variable "confluent_cloud_api_secret" {
  description = "Confluent Cloud API Secret"
  type        = string
  sensitive   = true
}

# Kafka credentials (existants)
variable "kafka_api_key" {
  description = "Kafka API Key"
  type        = string
  sensitive   = true
}

variable "kafka_api_secret" {
  description = "Kafka API Secret"
  type        = string
  sensitive   = true
}

# Schema Registry credentials (existants)
variable "schema_registry_api_key" {
  description = "Schema Registry API Key"
  type        = string
  sensitive   = true
}

variable "schema_registry_api_secret" {
  description = "Schema Registry API Secret"
  type        = string
  sensitive   = true
}

# Resource IDs
variable "environment_id" {
  description = "Confluent Cloud Environment ID"
  type        = string
}

variable "cluster_id" {
  description = "Kafka Cluster ID"
  type        = string
}