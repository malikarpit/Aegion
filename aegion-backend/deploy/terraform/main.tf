# Aegion Auto-Scaling Infrastructure (AWS)
# Scalability

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ========== Auto-Scaling Group (Compute) ==========

resource "aws_launch_template" "aegion_backend" {
  name_prefix   = "aegion-backend-"
  image_id      = var.ami_id
  instance_type = "t3.medium"

  user_data = base64encode(<<-EOF
              #!/bin/bash
              docker run -d \
                --name aegion-backend \
                -p 8000:8000 \
                -e GRAPH_BACKEND=neo4j \
                -e DB_BACKEND=postgres \
                ${var.docker_image}
              EOF
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "aegion_asg" {
  name                = "aegion-backend-asg"
  vpc_zone_identifier = var.subnet_ids
  target_group_arns   = [aws_lb_target_group.aegion_tg.arn]
  health_check_type   = "ELB"

  min_size         = 2
  max_size         = 10
  desired_capacity = 2

  launch_template {
    id      = aws_launch_template.aegion_backend.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "aegion-backend"
    propagate_at_launch = true
  }
}

# CPU-based Scaling Policy
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "scale_on_cpu"
  autoscaling_group_name = aws_autoscaling_group.aegion_asg.name
  policy_type            = "TargetTrackingScaling"

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }
    target_value = 60.0  # Scale when CPU > 60%
  }
}

# ========== Load Balancer (Session Affinity) ==========

resource "aws_lb" "aegion_alb" {
  name               = "aegion-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.subnet_ids
}

resource "aws_lb_target_group" "aegion_tg" {
  name     = "aegion-backend-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  # Stickiness for WebSocket session affinity
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    timeout             = 5
    interval            = 30
  }
}

# ========== Redis Cluster (Shared State) ==========

resource "aws_elasticache_replication_group" "aegion_redis" {
  replication_group_id       = "aegion-redis"
  description                = "Aegion Shared State (Session, Graph Cache)"
  node_type                  = "cache.t3.medium"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  engine_version             = "7.0"
  parameter_group_name       = "default.redis7"
  port                       = 6379
  security_group_ids         = [var.redis_sg_id]
  subnet_group_name          = var.redis_subnet_group

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
}

# ========== Variables ==========

variable "aws_region" { default = "us-east-1" }
variable "vpc_id" {}
variable "subnet_ids" { type = list(string) }
variable "ami_id" {}
variable "docker_image" {}
variable "alb_sg_id" {}
variable "redis_sg_id" {}
variable "redis_subnet_group" {}
