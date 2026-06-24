"""
Supabase Storage Service for uploading Project Audit Reports and Evidences.
"""
import os
import logging
import mimetypes
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)


from app.config import get_settings

class SupabaseStorageService:
    def __init__(self):
        settings = get_settings()
        self.supabase_url = settings.SUPABASE_URL
        self.supabase_key = settings.SUPABASE_KEY
        self.bucket_name = "reports"
        self.client: Optional[Client] = None

        if self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
                logger.info(f"Supabase client initialized. Bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        else:
            logger.warning("SUPABASE_URL and SUPABASE_KEY are not set. Supabase storage will be disabled.")

    def upload_file(self, file_path: str, destination_path: str, content_type: Optional[str] = None) -> Optional[str]:
        """
        Uploads a local file to Supabase Storage and returns the public URL.
        """
        if not self.client:
            logger.warning("Supabase storage is disabled. Cannot upload file.")
            return None

        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            content_type = content_type or "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                response = self.client.storage.from_(self.bucket_name).upload(
                    path=destination_path,
                    file=f,
                    file_options={"content-type": content_type, "upsert": "true"}
                )
            
            # Construct public URL
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(destination_path)
            logger.info(f"Successfully uploaded {destination_path} to Supabase: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Failed to upload {file_path} to Supabase Storage: {e}")
            return None

    def upload_bytes(self, file_bytes: bytes, destination_path: str, content_type: str) -> Optional[str]:
        """
        Uploads bytes directly to Supabase Storage and returns the public URL.
        """
        if not self.client:
            logger.warning("Supabase storage is disabled. Cannot upload bytes.")
            return None

        try:
            response = self.client.storage.from_(self.bucket_name).upload(
                path=destination_path,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            
            # Construct public URL
            public_url = self.client.storage.from_(self.bucket_name).get_public_url(destination_path)
            logger.info(f"Successfully uploaded {destination_path} to Supabase: {public_url}")
            return public_url
        except Exception as e:
            logger.error(f"Failed to upload bytes to Supabase Storage: {e}")
            return None
