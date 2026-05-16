from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_list_change_logs
from app.api.schemas import ChangeLogPageResponse, ChangeLogResponse
from app.application.governance.use_cases import ListChangeLogsUseCase
from app.domain.enums import GovernanceEntityType
from app.domain.governance.change_log import ConfigChangeLog

router = APIRouter(prefix="/governance", tags=["Governance"])


def _to_response(log: ConfigChangeLog) -> ChangeLogResponse:
    return ChangeLogResponse(
        log_id=log.log_id,
        entity_type=log.entity_type,
        entity_key=log.entity_key,
        change_type=log.change_type,
        before=log.before,
        after=log.after,
        reason=log.reason,
        changed_by=log.changed_by,
        changed_at=log.changed_at,
    )


@router.get("/change-logs", response_model=ChangeLogPageResponse)
def list_change_logs(
    entity_type: Optional[GovernanceEntityType] = Query(default=None),
    entity_key: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    uc: ListChangeLogsUseCase = Depends(get_list_change_logs),
):
    page = uc.execute(
        entity_type=entity_type,
        entity_key=entity_key,
        limit=limit,
        offset=offset,
    )
    return ChangeLogPageResponse(
        items=[_to_response(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        has_next=page.has_next,
    )
