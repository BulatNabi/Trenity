from fastapi import APIRouter, HTTPException
from typing import List, Dict
from collections import defaultdict
from app.services.smmbox_service import smmbox_service
from app import schemas
from app.logger import api_logger as logger

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("/", response_model=List[schemas.GroupsBySocialResponse])
async def get_groups_by_social():
    """
    Получает все группы из SmmBox и группирует их по соцсетям
    """
    try:
        logger.info("Запрос списка групп из SmmBox")
        
        groups = await smmbox_service.get_groups()
        
        # Группируем по соцсетям
        groups_by_social: Dict[str, List[schemas.GroupInfo]] = defaultdict(list)
        
        for group in groups:
            social = group.get("social", "").lower()
            group_info = schemas.GroupInfo(
                id=str(group.get("id", "")),
                social=social,
                type=group.get("type", ""),
                name=group.get("name"),
                photo=group.get("photo"),
                index=group.get("index")
            )
            groups_by_social[social].append(group_info)
        
        # Формируем ответ
        result = []
        for social, group_list in groups_by_social.items():
            result.append(schemas.GroupsBySocialResponse(
                social=social,
                count=len(group_list),
                groups=group_list
            ))
        
        logger.info(f"Получено {len(groups)} групп, сгруппировано по {len(result)} соцсетям")
        return result
        
    except ValueError as e:
        # Ошибка конфигурации (например, отсутствует токен)
        logger.error(f"Ошибка конфигурации: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка получения групп: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка получения групп: {str(e)}")

