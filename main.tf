terraform {
  required_version = ">= 1.0"
  
  required_providers {
    confluent = {
      source  = "confluentinc/confluent"
      version = "~> 2.1"
    }
  }
}

# Provider avec Cloud API
provider "confluent" {
  cloud_api_key    = var.confluent_cloud_api_key
  cloud_api_secret = var.confluent_cloud_api_secret
}

# === DATA SOURCES ===

data "confluent_environment" "demo_env" {
  id = var.environment_id
}

data "confluent_kafka_cluster" "demo_cluster" {
  id = var.cluster_id
  environment {
    id = data.confluent_environment.demo_env.id
  }
}

data "confluent_schema_registry_cluster" "demo_sr" {
  environment {
    id = data.confluent_environment.demo_env.id
  }
}

# === TOPIC KAFKA ===

resource "confluent_kafka_topic" "order_created" {
  kafka_cluster {
    id = data.confluent_kafka_cluster.demo_cluster.id
  }

  topic_name       = "order-created"
  partitions_count = 3

  rest_endpoint = data.confluent_kafka_cluster.demo_cluster.rest_endpoint

  # Utilise tes credentials Kafka existants
  credentials {
    key    = var.kafka_api_key
    secret = var.kafka_api_secret
  }

  config = {
    "retention.ms"     = "604800000"  # 7 jours
    "cleanup.policy"   = "delete"
    "compression.type" = "gzip"
  }
}

# === SCHEMA AVRO ===

resource "confluent_schema" "order_created_value" {
  schema_registry_cluster {
    id = data.confluent_schema_registry_cluster.demo_sr.id
  }

  rest_endpoint = data.confluent_schema_registry_cluster.demo_sr.rest_endpoint

  subject_name = "order-created-value"
  format       = "AVRO"
  
  schema = file("${path.module}/schemas/order-created-value.avsc")

  # Utilise tes credentials Schema Registry existants
  credentials {
    key    = var.schema_registry_api_key
    secret = var.schema_registry_api_secret
  }

  depends_on = [confluent_kafka_topic.order_created]
}