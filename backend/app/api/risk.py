from fastapi import APIRouter, HTTPException

from app.schemas.requests import RiskRulePayload
from app.services.risk_service import list_risk_rules, risk_overview, update_risk_rule

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/overview")
def get_risk_overview() -> dict:
    return risk_overview()


@router.get("/rules")
def get_risk_rules() -> list[dict]:
    return list_risk_rules()


@router.put("/rules/{rule_id}")
def put_risk_rule(rule_id: int, payload: RiskRulePayload) -> dict:
    updated = update_risk_rule(rule_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="risk rule not found")
    return updated

