terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.aws_region
}

# ---------- IAM Role for Lambda ----------
resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.project_name}-lambda-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  lifecycle {
    create_before_destroy = true
    ignore_changes = [name]
  }
}

resource "aws_iam_policy_attachment" "lambda_basic_execution" {
  name       = "${var.project_name}-lambda-basic-execution"
  roles      = [aws_iam_role.lambda_exec_role.name]
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Allow Lambda to read secret
resource "aws_iam_policy" "lambda_secret_access" {
  name        = "${var.project_name}-lambda-secret-access"
  description = "Allow Lambda to access OpenAI API key in Secrets Manager"
  policy      = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Resource = aws_secretsmanager_secret.openai_api_key.arn
      }
    ]
  })
}

resource "aws_iam_policy_attachment" "attach_secret_access" {
  name       = "${var.project_name}-lambda-secret-attach"
  roles      = [aws_iam_role.lambda_exec_role.name]
  policy_arn = aws_iam_policy.lambda_secret_access.arn
}

# ---------- Secrets Manager ----------
resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${var.project_name}-openai-api-key"
}

# The value will be manually added or via GitHub Actions at deployment

# ---------- Lambda Function ----------
resource "aws_lambda_function" "proxy_lambda" {
  function_name = "${var.project_name}-proxy"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec_role.arn
  handler       = "lambda_function.handler"

  # Zip file created separately (GitHub Actions will build & upload)
  filename      = "${path.module}/lambda.zip"

  environment {
    variables = {
      SECRET_NAME = aws_secretsmanager_secret.openai_api_key.name
      REGION      = var.aws_region
    }
  }
}

# ---------- API Gateway ----------
resource "aws_api_gateway_rest_api" "proxy_api" {
  name        = "${var.project_name}-api"
  description = "Private API Gateway proxying OpenAI requests"
}

resource "aws_api_gateway_resource" "proxy_resource" {
  rest_api_id = aws_api_gateway_rest_api.proxy_api.id
  parent_id   = aws_api_gateway_rest_api.proxy_api.root_resource_id
  path_part   = "proxy"
}

resource "aws_api_gateway_method" "proxy_method" {
  rest_api_id   = aws_api_gateway_rest_api.proxy_api.id
  resource_id   = aws_api_gateway_resource.proxy_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "proxy_integration" {
  rest_api_id = aws_api_gateway_rest_api.proxy_api.id
  resource_id = aws_api_gateway_resource.proxy_resource.id
  http_method = aws_api_gateway_method.proxy_method.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.proxy_lambda.invoke_arn
}

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.proxy_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.proxy_api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "proxy_deployment" {
  depends_on = [
    aws_api_gateway_integration.proxy_integration
  ]
  rest_api_id = aws_api_gateway_rest_api.proxy_api.id

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "proxy_stage" {
  deployment_id = aws_api_gateway_deployment.proxy_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.proxy_api.id
  stage_name    = "prod"
}

