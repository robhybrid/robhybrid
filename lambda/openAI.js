const AWS = require("aws-sdk");
const jwt = require("jsonwebtoken");
const https = require("https");

// AWS clients
const secretsManager = new AWS.SecretsManager({ region: process.env.REGION });

let openaiApiKeyCache = null;
let jwtSecretCache = null;

// Helper to get secret from Secrets Manager with caching
async function getSecret(secretName) {
  if (secretName === process.env.OPENAI_SECRET_NAME && openaiApiKeyCache) {
    return openaiApiKeyCache;
  }
  if (secretName === process.env.JWT_SECRET_NAME && jwtSecretCache) {
    return jwtSecretCache;
  }

  const data = await secretsManager
    .getSecretValue({ SecretId: secretName })
    .promise();

  const secretString =
    data.SecretString ||
    Buffer.from(data.SecretBinary, "base64").toString("utf-8");

  if (secretName === process.env.OPENAI_SECRET_NAME) {
    openaiApiKeyCache = secretString;
  }
  if (secretName === process.env.JWT_SECRET_NAME) {
    jwtSecretCache = secretString;
  }
  return secretString;
}

// Verify JWT, return decoded claims or null
async function verifyJwt(token) {
  if (!token) return null;
  try {
    const secret = await getSecret(process.env.JWT_SECRET_NAME);
    return jwt.verify(token, secret, { algorithms: ["HS256"] });
  } catch (err) {
    console.warn("JWT verification failed:", err.message);
    return null;
  }
}

// Helper to make HTTPS POST request
function httpsPost(url, headers, body) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      hostname: parsedUrl.hostname,
      path: parsedUrl.pathname + parsedUrl.search,
      method: "POST",
      headers,
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error("Invalid JSON response"));
          }
        } else {
          reject(new Error(`Status code: ${res.statusCode}, body: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

exports.handler = async function (event) {
  // Parse request body
  let body;
  try {
    body = JSON.parse(event.body || "{}");
  } catch {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Invalid JSON body" }),
    };
  }

  // Extract token from Authorization header or body.token
  const authHeader =
    event.headers?.Authorization || event.headers?.authorization || "";
  const token = authHeader.startsWith("Bearer ")
    ? authHeader.slice(7)
    : body.token;

  // Verify JWT or fallback to default tenant
  const claims = await verifyJwt(token);
  const tenantId = claims?.tenant_id || "default";

  // Validate prompt
  const prompt = body.prompt;
  if (!prompt) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Prompt is required" }),
    };
  }

  // Model & max tokens
  const model = body.model || "gpt-4.1-mini";
  const max_tokens = body.max_tokens || 512;

  // Get OpenAI API key
  let openaiApiKey;
  try {
    openaiApiKey = await getSecret(process.env.OPENAI_SECRET_NAME);
  } catch (err) {
    console.error("Error fetching OpenAI API key:", err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Failed to retrieve API key" }),
    };
  }

  // Build OpenAI request payload
  const openaiPayload = JSON.stringify({
    model,
    messages: [
      { role: "system", content: `You are serving tenant: ${tenantId}` },
      { role: "user", content: prompt },
    ],
    max_tokens,
  });

  // Call OpenAI API
  try {
    const response = await httpsPost(
      "https://api.openai.com/v1/chat/completions",
      {
        Authorization: `Bearer ${openaiApiKey}`,
        "Content-Type": "application/json",
      },
      openaiPayload
    );

    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId, response }),
    };
  } catch (err) {
    console.error("OpenAI API error:", err);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: "Failed to call OpenAI API" }),
    };
  }
};
