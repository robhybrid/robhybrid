import os
import json
import boto3
import base64
import jwt  # PyJWT
import requests

# Initialize AWS Secrets Manager client
secrets_client = boto3.client("secretsmanager", region_name=os.environ["REGION"])

# Cache API key to avoid repeated secrets fetch
OPENAI_API_KEY = None


def get_openai_api_key():
    global OPENAI_API_KEY
    if OPENAI_API_KEY:
        return OPENAI_API_KEY

    secret_name = os.environ["SECRET_NAME"]
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
        if "SecretString" in response:
            OPENAI_API_KEY = response["SecretString"]
        else:
            OPENAI_API_KEY = base64.b64decode(response["SecretBinary"]).decode("utf-8")
        return OPENAI_API_KEY
    except Exception as e:
        print(f"Error fetching OpenAI API key: {e}")
        raise


def verify_jwt_token(token):
    """
    Verify JWT and return decoded claims.
    If token is missing or invalid, return None (handled as default tenant).
    """
    if not token:
        return None
    try:
        secret = os.environ.get("JWT_SECRET", "replace_me")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded
    except jwt.InvalidTokenError:
        return None


def handler(event, context):
    # Parse body
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid JSON body"})}

    # Extract token
    auth_header = event.get("headers", {}).get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header else body.get("token")

    # Default tenant fallback
    claims = verify_jwt_token(token)
    tenant_id = claims.get("tenant_id") if claims else "default"

    # Extract prompt
    prompt = body.get("prompt")
    model = body.get("model", "gpt-4.1-mini")
    max_tokens = body.get("max_tokens", 512)

    if not prompt:
        return {"statusCode": 400, "body": json.dumps({"error": "Prompt is required"})}

    # Call OpenAI
    try:
        api_key = get_openai_api_key()
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": f"You are serving tenant: {tenant_id}"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling OpenAI API: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Failed to call OpenAI API"})}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"tenant_id": tenant_id, "response": data})
    }
