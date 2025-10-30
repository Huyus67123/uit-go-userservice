# auth.py
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase Admin SDK
try:
    # Check if already initialized
    firebase_admin.get_app()
except ValueError:
    # Not initialized yet, so initialize it
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "./serviceAccountKey.json")
    
    if os.path.exists(service_account_path):
        # Option 1: Using service account JSON file (RECOMMENDED)
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        print(f"✓ Firebase Admin initialized with service account: {service_account_path}")
    else:
        # Option 2: Initialize with project ID from environment
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        
        if project_id:
            firebase_admin.initialize_app(options={
                'projectId': project_id,
            })
            print(f"✓ Firebase Admin initialized with project ID: {project_id}")
        else:
            raise Exception(
                "Firebase initialization failed. Please provide either:\n"
                "1. FIREBASE_SERVICE_ACCOUNT_PATH pointing to your serviceAccountKey.json\n"
                "2. FIREBASE_PROJECT_ID in your .env file"
            )

security = HTTPBearer()


async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Verify Firebase ID token from Authorization header.
    Returns the decoded token (user info).
    """
    if credentials:
        token = credentials.credentials
        try:
            # Verify the ID token
            decoded_token = auth.verify_id_token(token)
            return decoded_token
        except auth.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except auth.ExpiredIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_uid(
    token: dict = Security(verify_firebase_token)
) -> str:
    """
    Extract user UID from verified token.
    """
    return token.get("uid")


async def get_current_user_email(
    token: dict = Security(verify_firebase_token)
) -> Optional[str]:
    """
    Extract user email from verified token.
    """
    return token.get("email")
