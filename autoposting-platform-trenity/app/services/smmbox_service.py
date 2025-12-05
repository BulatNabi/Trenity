import httpx
from typing import List, Dict, Any
from app.config import settings
from app.models import SocialNetwork
from app.logger import service_logger as logger


class SmmBoxService:
    def __init__(self):
        self.api_url = settings.smmbox_api_url
        self.token = settings.smmbox_api_token

    def _get_auth_headers(self) -> Dict[str, str]:
        """Формирует заголовки авторизации с проверкой токена"""
        if not self.token or not self.token.strip():
            raise ValueError(
                "SmmBox API токен не установлен. Установите переменную окружения SMMBOX_API_TOKEN"
            )
        # Удаляем пробелы и кавычки (если они были добавлены в .env файле)
        token = self.token.strip().strip('"').strip("'")
        return {"Authorization": f"Bearer {token}"}

    async def get_groups(self) -> List[Dict[str, Any]]:
        """Получает список групп из SmmBox"""
        headers = self._get_auth_headers()
        url = f"{self.api_url}v1/groups"
        logger.info(f"Запрос списка групп из SmmBox: {url}")

        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers=headers
                )
                logger.info(f"Получен ответ: статус {response.status_code}")
                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    groups = data.get("response", [])
                    logger.info(f"Получено {len(groups)} групп из SmmBox")
                    return groups
                else:
                    error_msg = data.get('error', {}).get('message') or str(
                        data.get('error', 'Неизвестная ошибка'))
                    logger.error(
                        f"Ошибка получения групп из SmmBox: {error_msg}")
                    logger.error(f"Полный ответ API: {data}")
                    raise Exception(f"Ошибка получения групп: {error_msg}")
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при запросе к SmmBox API: {url}")
            raise Exception(f"Таймаут при запросе к SmmBox API: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Ошибка соединения с SmmBox API: {str(e)}")
            logger.error(f"URL: {url}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            raise Exception(f"Ошибка соединения с SmmBox API: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка от SmmBox API: {e.response.status_code}")
            logger.error(f"URL: {url}")
            try:
                error_body = e.response.json()
                logger.error(f"Тело ошибки: {error_body}")
                error_msg = error_body.get('error', {}).get(
                    'message') or str(error_body)
            except:
                error_body = e.response.text
                logger.error(f"Текст ошибки: {error_body[:500]}")
                error_msg = error_body[:200]
            raise Exception(f"HTTP {e.response.status_code}: {error_msg}")
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при запросе к SmmBox API: {str(e)}", exc_info=True)
            raise

    async def create_posts_batch(
        self,
        posts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Создает несколько постов в SmmBox одним запросом

        Args:
            posts: Список постов, каждый содержит:
                - group: {"id": str, "social": str, "type": str}
                - attachments: [{"type": "video", "url": str}]
                - date: int (unix timestamp, опционально)
        """
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        payload = {
            "posts": posts
        }

        logger.info(f"Создание {len(posts)} постов в SmmBox одним запросом")
        url = f"{self.api_url}v1/posts/postpone"
        logger.info(f"URL запроса: {url}")
        logger.info(f"Количество постов: {len(posts)}")

        try:
            # Увеличиваем таймаут для больших запросов
            timeout = httpx.Timeout(120.0, connect=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"Отправка запроса к SmmBox API...")
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload
                )
                logger.info(f"Получен ответ: статус {response.status_code}")

                response.raise_for_status()
                data = response.json()
                logger.debug(f"Ответ API: {data}")

                if data.get("success"):
                    result = data.get("response", {})
                    logger.info(
                        f"Посты успешно созданы в SmmBox: {len(result.get('posts', []))} постов")
                    return result
                else:
                    error_msg = data.get('error', {}).get('message') or str(
                        data.get('error', 'Неизвестная ошибка'))
                    logger.error(
                        f"Ошибка создания постов в SmmBox: {error_msg}")
                    logger.error(f"Полный ответ API: {data}")
                    raise Exception(f"Ошибка создания постов: {error_msg}")
        except httpx.TimeoutException as e:
            logger.error(f"Таймаут при запросе к SmmBox API: {url}")
            raise Exception(f"Таймаут при запросе к SmmBox API: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Ошибка соединения с SmmBox API: {str(e)}")
            logger.error(f"URL: {url}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            raise Exception(f"Ошибка соединения с SmmBox API: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка от SmmBox API: {e.response.status_code}")
            logger.error(f"URL: {url}")
            try:
                error_body = e.response.json()
                logger.error(f"Тело ошибки: {error_body}")
                error_msg = error_body.get('error', {}).get(
                    'message') or str(error_body)
            except:
                error_body = e.response.text
                logger.error(f"Текст ошибки: {error_body[:500]}")
                error_msg = error_body[:200]
            raise Exception(f"HTTP {e.response.status_code}: {error_msg}")
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при запросе к SmmBox API: {str(e)}", exc_info=True)
            raise

    async def create_post(
        self,
        group_id: str,
        social: SocialNetwork,
        group_type: str,
        video_url: str,
        date: int = None
    ) -> Dict[str, Any]:
        """
        Создает пост в SmmBox

        Args:
            group_id: ID группы в соцсети
            social: Соцсеть (vk, io, gg, pi)
            group_type: Тип группы (user, group, page)
            video_url: URL видео
            date: Unix timestamp для планирования (опционально)
        """
        headers = self._get_auth_headers()
        headers["Content-Type"] = "application/json"

        # Формируем группу
        group = {
            "id": group_id,
            "social": social.value,
            "type": group_type
        }

        # Формируем вложение видео
        attachment = {
            "type": "video",
            "url": video_url
        }

        post = {
            "group": group,
            "attachments": [attachment]
        }

        if date:
            post["date"] = date

        payload = {
            "posts": [post]
        }

        logger.info(
            f"Создание поста в SmmBox: social={social.value}, group_id={group_id}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}v1/postpone",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                result = data.get("response", {})
                post_id = result.get("posts", [{}])[0].get(
                    "id") if result.get("posts") else None
                logger.info(f"Пост успешно создан в SmmBox: post_id={post_id}")
                return result
            else:
                error_msg = data.get('error', {}).get('message')
                logger.error(f"Ошибка создания поста в SmmBox: {error_msg}")
                raise Exception(f"Ошибка создания поста: {error_msg}")


smmbox_service = SmmBoxService()
