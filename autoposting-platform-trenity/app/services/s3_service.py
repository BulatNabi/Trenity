import boto3
from botocore.config import Config
from app.config import settings
import os
from typing import BinaryIO
from app.logger import service_logger as logger


class S3Service:
    def __init__(self):
        self._s3_client = None
        self._bucket_name = None
    
    @property
    def s3_client(self):
        """Ленивая инициализация S3 клиента"""
        if self._s3_client is None:
            # Проверяем настройки S3 только при первом использовании
            settings.validate_s3_settings()
            self._s3_client = boto3.client(
                's3',
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=Config(signature_version='s3v4')
            )
        return self._s3_client
    
    @property
    def bucket_name(self):
        """Ленивое получение имени bucket"""
        if self._bucket_name is None:
            settings.validate_s3_settings()
            self._bucket_name = settings.s3_bucket_name
        return self._bucket_name

    def upload_file(self, file_path: str, s3_key: str) -> str:
        """Загружает файл в S3 и возвращает URL"""
        try:
            file_size = os.path.getsize(file_path)
            logger.info(f"Загрузка файла в S3: {s3_key} (размер: {file_size} байт)")
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key
            )
            # Формируем публичный URL
            url = f"{settings.s3_endpoint_url}/{self.bucket_name}/{s3_key}"
            logger.info(f"Файл успешно загружен в S3: {url}")
            return url
        except Exception as e:
            logger.error(f"Ошибка загрузки в S3: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка загрузки в S3: {str(e)}")

    def upload_fileobj(self, file_obj: BinaryIO, s3_key: str, content_type: str = "video/mp4") -> str:
        """Загружает файл из объекта в S3 и возвращает URL"""
        try:
            logger.info(f"Загрузка файла в S3 из объекта: {s3_key}")
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )
            url = f"{settings.s3_endpoint_url}/{self.bucket_name}/{s3_key}"
            logger.info(f"Файл успешно загружен в S3: {url}")
            return url
        except Exception as e:
            logger.error(f"Ошибка загрузки в S3: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка загрузки в S3: {str(e)}")

    def delete_file(self, s3_key: str):
        """Удаляет файл из S3"""
        try:
            logger.info(f"Удаление файла из S3: {s3_key}")
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Файл успешно удален из S3: {s3_key}")
        except Exception as e:
            logger.error(f"Ошибка удаления из S3: {str(e)}", exc_info=True)
            raise Exception(f"Ошибка удаления из S3: {str(e)}")


s3_service = S3Service()
