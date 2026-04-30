AUTHORIZE_URL = 'https://auth.openai.com/oauth/authorize'
TOKEN_URL = 'https://auth.openai.com/oauth/token'
RESPONSES_URL = (
    'https://chatgpt.com/backend-api/codex/responses'
)
CLIENT_ID = 'app_EMoamEEZ73f0CkXaXp7hrann'
REDIRECT_URI = 'http://localhost:1455/auth/callback'
SCOPE = 'openid profile email offline_access'
JWT_CLAIM_PATH = 'https://api.openai.com/auth'

TOKEN_REFRESH_WINDOW = 60
DEFAULT_MODEL = 'gpt-5.4'
DEFAULT_REASONING_EFFORT = 'medium'
DEFAULT_AUTH_KEY = 'auth:codex'
