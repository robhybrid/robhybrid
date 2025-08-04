output "api_url" {
  description = "Invoke URL of the API Gateway"
  value       = "${aws_api_gateway_deployment.proxy_deployment.invoke_url}/proxy"
}
