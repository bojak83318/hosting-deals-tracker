from __future__ import annotations

import math
import sys
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.db_manager import DBManager


def create_app(db_path: Path | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    manager = DBManager(db_path=db_path)

    @app.route("/")
    def index():
        page = max(int(request.args.get("page", 1) or 1), 1)
        per_page = min(max(int(request.args.get("per_page", 25) or 25), 1), 100)

        search = (request.args.get("q") or "").strip() or None
        provider = (request.args.get("provider") or "").strip() or None
        category = (request.args.get("category") or "").strip() or None
        sort = (request.args.get("sort") or "date_desc").strip()

        price_min_raw = (request.args.get("price_min") or "").strip()
        price_max_raw = (request.args.get("price_max") or "").strip()

        price_min = float(price_min_raw) if price_min_raw else None
        price_max = float(price_max_raw) if price_max_raw else None

        deals, total = manager.query_deals(
            search=search,
            provider=provider,
            category=category,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
            page=page,
            per_page=per_page,
        )

        providers = sorted({(d.get("provider") or "Unknown") for d in manager.get_latest(limit=500)})
        categories = sorted({(d.get("category") or "Unknown") for d in manager.get_latest(limit=500)})

        total_pages = max(math.ceil(total / per_page), 1)

        return render_template(
            "index.html",
            deals=deals,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            providers=providers,
            categories=categories,
            filters={
                "q": search or "",
                "provider": provider or "",
                "category": category or "",
                "price_min": price_min_raw,
                "price_max": price_max_raw,
                "sort": sort,
            },
        )

    @app.route("/deal/<int:deal_id>")
    def deal_detail(deal_id: int):
        deal = manager.get_deal_by_id(deal_id)
        if not deal:
            abort(404)

        history = manager.get_price_history(deal_id=deal_id)
        max_price = max([h.get("price_monthly") or 0 for h in history] or [0])

        return render_template("detail.html", deal=deal, history=history, max_price=max_price)

    @app.route("/provider/<name>")
    def provider_view(name: str):
        deals = manager.get_by_provider(name, limit=200)
        return render_template("index.html", deals=deals, total=len(deals), page=1, per_page=200, total_pages=1,
                               providers=[], categories=[],
                               filters={"q": "", "provider": name, "category": "", "price_min": "", "price_max": "", "sort": "date_desc"})

    @app.route("/api/deals")
    def api_deals():
        page = max(int(request.args.get("page", 1) or 1), 1)
        per_page = min(max(int(request.args.get("per_page", 25) or 25), 1), 100)
        search = (request.args.get("q") or "").strip() or None
        provider = (request.args.get("provider") or "").strip() or None
        category = (request.args.get("category") or "").strip() or None
        sort = (request.args.get("sort") or "date_desc").strip()

        price_min_raw = (request.args.get("price_min") or "").strip()
        price_max_raw = (request.args.get("price_max") or "").strip()
        price_min = float(price_min_raw) if price_min_raw else None
        price_max = float(price_max_raw) if price_max_raw else None

        deals, total = manager.query_deals(
            search=search,
            provider=provider,
            category=category,
            price_min=price_min,
            price_max=price_max,
            sort=sort,
            page=page,
            per_page=per_page,
        )
        return jsonify({"total": total, "page": page, "per_page": per_page, "items": deals})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
