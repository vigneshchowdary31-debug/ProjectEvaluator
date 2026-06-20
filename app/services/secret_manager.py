"""
Secret Manager Service — manages project credentials securely.
Authenticates with Google Secret Manager if configured, or falls back
to a local AES-encrypted key-value locker.
"""

import os
import json
import logging
import uuid
from typing import Dict, Optional
from cryptography.fernet import Fernet
from app.config import get_settings

logger = logging.getLogger(__name__)


class SecretManagerService:
    """Provides secure credential management with Google Secret Manager and local fallback."""

    def __init__(self):
        self.settings = get_settings()
        self.encryption_key = self._get_or_create_key()
        self.fernet = Fernet(self.encryption_key.encode())
        self.local_locker_path = "local_secrets.enc"
        
        # Google Secret Manager placeholders
        self.gsm_client = None
        self.gsm_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.gsm_enabled = False

        # Attempt to load Google Secret Manager if credentials exist
        if self.settings.GOOGLE_CREDENTIALS_JSON and self.gsm_project_id:
            try:
                from google.cloud import secretmanager
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.settings.GOOGLE_CREDENTIALS_JSON
                self.gsm_client = secretmanager.SecretManagerServiceClient()
                self.gsm_enabled = True
                logger.info("Google Secret Manager client initialized successfully.")
            except Exception as e:
                logger.debug("Google Secret Manager initialization skipped/failed: %s", str(e))

    def _get_or_create_key(self) -> str:
        """Get the encryption key from settings or generate a new one and write it to .env."""
        key = self.settings.SECRETS_ENCRYPTION_KEY
        if key:
            return key

        # Generate a new Fernet key
        new_key = Fernet.generate_key().decode()
        env_file_path = ".env"
        
        # Write to .env file
        if os.path.exists(env_file_path):
            try:
                with open(env_file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                key_exists = False
                for i, line in enumerate(lines):
                    if line.startswith("SECRETS_ENCRYPTION_KEY="):
                        lines[i] = f"SECRETS_ENCRYPTION_KEY={new_key}\n"
                        key_exists = True
                        break
                
                if not key_exists:
                    lines.append(f"\nSECRETS_ENCRYPTION_KEY={new_key}\n")
                
                with open(env_file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                
                logger.info("Generated new SECRETS_ENCRYPTION_KEY and appended to .env")
            except Exception as e:
                logger.error("Failed to write new encryption key to .env: %s", str(e))
        else:
            try:
                with open(env_file_path, "w", encoding="utf-8") as f:
                    f.write(f"SECRETS_ENCRYPTION_KEY={new_key}\n")
                logger.info("Created .env and seeded SECRETS_ENCRYPTION_KEY")
            except Exception as e:
                logger.error("Failed to create .env file: %s", str(e))

        return new_key

    def _read_local_locker(self) -> Dict[str, str]:
        """Read the local encrypted secrets locker file."""
        if not os.path.exists(self.local_locker_path):
            return {}
        try:
            with open(self.local_locker_path, "rb") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return {}
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to read/decrypt local secrets locker: %s", str(e))
            return {}

    def _write_local_locker(self, data: Dict[str, str]) -> None:
        """Write the local encrypted secrets locker file."""
        try:
            serialized = json.dumps(data).encode("utf-8")
            encrypted = self.fernet.encrypt(serialized)
            with open(self.local_locker_path, "wb") as f:
                f.write(encrypted)
        except Exception as e:
            logger.error("Failed to encrypt/write local secrets locker: %s", str(e))

    def save_credentials(self, project_id: str, admin_creds: dict, user_creds: dict) -> str:
        """
        Encrypt and save project credentials securely.
        Returns a secret reference UUID.
        """
        secret_id = str(uuid.uuid4())
        payload = {
            "project_id": project_id,
            "admin": admin_creds,
            "user": user_creds
        }
        payload_str = json.dumps(payload)

        # 1. Attempt Google Secret Manager
        if self.gsm_enabled and self.gsm_client and self.gsm_project_id:
            try:
                parent = f"projects/{self.gsm_project_id}"
                secret_name = f"project_credentials_{secret_id}"
                
                # Create the secret
                self.gsm_client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {"replication": {"automatic": {}}},
                    }
                )
                
                # Add payload version
                self.gsm_client.add_secret_version(
                    request={
                        "parent": f"{parent}/secrets/{secret_name}",
                        "payload": {"data": payload_str.encode("utf-8")},
                    }
                )
                logger.info("Saved credentials successfully to Google Secret Manager: %s", secret_name)
                return secret_id
            except Exception as e:
                logger.warning("Failed to save to Google Secret Manager: %s. Falling back to local locker.", str(e))

        # 2. Local Fallback (AES-encrypted file)
        locker = self._read_local_locker()
        # Encrypt individual entry inside locker
        encrypted_payload = self.fernet.encrypt(payload_str.encode("utf-8")).decode("utf-8")
        locker[secret_id] = encrypted_payload
        self._write_local_locker(locker)
        
        logger.info("Saved credentials successfully to local encrypted locker (Ref: %s)", secret_id)
        return secret_id

    def retrieve_credentials(self, secret_ref: str) -> Optional[dict]:
        """
        Retrieve and decrypt credentials using the secret reference UUID.
        """
        if not secret_ref:
            return None

        # 1. Attempt Google Secret Manager
        if self.gsm_enabled and self.gsm_client and self.gsm_project_id:
            try:
                secret_name = f"project_credentials_{secret_ref}"
                name = f"projects/{self.gsm_project_id}/secrets/{secret_name}/versions/latest"
                response = self.gsm_client.access_secret_version(request={"name": name})
                payload_str = response.payload.data.decode("utf-8")
                return json.loads(payload_str)
            except Exception as e:
                logger.warning("Failed to retrieve from Google Secret Manager: %s. Trying local locker.", str(e))

        # 2. Local Fallback
        locker = self._read_local_locker()
        encrypted_payload = locker.get(secret_ref)
        if not encrypted_payload:
            logger.warning("Secret reference %s not found in local locker.", secret_ref)
            return None
        
        try:
            decrypted = self.fernet.decrypt(encrypted_payload.encode("utf-8"))
            return json.loads(decrypted.decode("utf-8"))
        except Exception as e:
            logger.error("Failed to decrypt retrieved secret payload: %s", str(e))
            return None

    def delete_credentials(self, secret_ref: str) -> None:
        """
        Delete credentials from store if they are no longer needed.
        """
        if not secret_ref:
            return

        # 1. Attempt Google Secret Manager
        if self.gsm_enabled and self.gsm_client and self.gsm_project_id:
            try:
                secret_name = f"project_credentials_{secret_ref}"
                name = f"projects/{self.gsm_project_id}/secrets/{secret_name}"
                self.gsm_client.delete_secret(request={"name": name})
                logger.info("Deleted secret from Google Secret Manager: %s", secret_name)
                return
            except Exception as e:
                logger.warning("Failed to delete from Google Secret Manager: %s", str(e))

        # 2. Local Fallback
        locker = self._read_local_locker()
        if secret_ref in locker:
            del locker[secret_ref]
            self._write_local_locker(locker)
            logger.info("Deleted secret from local encrypted locker: %s", secret_ref)
