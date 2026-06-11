from fastapi import APIRouter,Depends,HTTPException
from app.deps import get_current_user,get_db
from app.db import models
router=APIRouter(tags=["inspections"])
@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id:int,db=Depends(get_db),u=Depends(get_current_user)):
 q=db.query(models.Inspection).filter(models.Inspection.id==inspection_id)
 if getattr(u,"role","") not in {"admin","super_admin","security_admin"}:
  q=q.filter(models.Inspection.tenant_id==getattr(u,"tenant_id",