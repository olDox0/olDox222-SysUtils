# energy_sys/core/cost_calculator.py
from __future__ import annotations
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_ROOT / "data" / "energy_config.json"

DEFAULT_TARIFF_KWH = 0.9543
DEFAULT_PROVIDER = "Elderbarry"

def load_energy_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tariff_kwh": DEFAULT_TARIFF_KWH, "provider": DEFAULT_PROVIDER}

def save_energy_config(tariff_kwh: float, provider: str = "Elderbarry") -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tariff_kwh": tariff_kwh, "provider": provider}
    CONFIG_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def calculate_energy_cost(watts: float, tariff_kwh: float | None = None) -> dict:
    cfg = load_energy_config()
    tariff = tariff_kwh if tariff_kwh is not None else cfg.get("tariff_kwh", DEFAULT_TARIFF_KWH)
    provider = cfg.get("provider", DEFAULT_PROVIDER)

    kw = watts / 1000.0
    cost_per_hour = kw * tariff
    cost_per_day_8h = cost_per_hour * 8.0
    cost_per_day_24h = cost_per_hour * 24.0

    return {
        "watts": round(watts, 2),
        "provider": provider,
        "tariff_kwh": tariff,
        "cost_hour": round(cost_per_hour, 4),
        "cost_day_8h": round(cost_per_day_8h, 2),
        "cost_day_24h": round(cost_per_day_24h, 2),
        "cost_month_8h": round(cost_per_day_8h * 30.0, 2),
        "cost_month_24h": round(cost_per_day_24h * 30.0, 2),
    }
