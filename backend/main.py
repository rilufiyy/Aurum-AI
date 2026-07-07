from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from predictor import forecast_budget, get_history, predict_current
from schemas import (
    BudgetRequest,
    BudgetResponse,
    HistoryResponse,
    PredictionResponse,
)

app = FastAPI(title="Aurum AI", description="Real-Time UBS Gold Price Predictor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "Aurum AI"}


@app.get("/api/predict", response_model=PredictionResponse)
def predict():
    try:
        return predict_current()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history", response_model=HistoryResponse)
def history(days: int = Query(default=30, ge=7, le=365)):
    try:
        return {"data": get_history(days=days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/budget", response_model=BudgetResponse)
def budget(req: BudgetRequest):
    try:
        return forecast_budget(
            budget_idr=req.budget_idr,
            weight_gram=req.weight_gram,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
