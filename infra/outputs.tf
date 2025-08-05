output "api_url" {
  description = "Invoke URL of the API Gateway"
  value       = "${aws_api_gateway_stage.proxy_stage.invoke_url}/proxy"
}