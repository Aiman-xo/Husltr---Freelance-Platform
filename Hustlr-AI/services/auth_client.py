import requests
from fastapi import HTTPException

# 'django_container' matches your docker-compose service name
DJANGO_AUTH_URL = "http://backend_api:8000/api/auth/internal-verify/"

def verify_user_with_django(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(DJANGO_AUTH_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json() # Returns {'user_id': 5, 'role': 'worker', ...}
        raise HTTPException(status_code=401, detail="Invalid Token")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=503, detail="Auth Service is down")