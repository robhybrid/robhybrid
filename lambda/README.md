## Deployment Steps

Zip the function:

```bash
cd lambda
pip install -r requirements.txt --target .
zip -r ../lambda.zip .
```

Terraform will upload lambda.zip when applied.

Store OpenAI key in Secrets Manager:

```bash
aws secretsmanager put-secret-value \
  --secret-id openai-private-gateway-openai-api-key \
  --secret-string "sk-xxxx..."
```
