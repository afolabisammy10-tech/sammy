"""Python storefront server for sammy.com.

Run with: python store_server.py
Open: http://127.0.0.1:8080/sammy-business.html
"""
from __future__ import annotations

import json
import mimetypes
import secrets
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HOST = "127.0.0.1"
PORT = 8080
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
ORDERS_FILE = DATA_DIR / "python-orders.json"

PRODUCTS = [
    {"id": "1", "name": "The Air Shirt", "category": "tops", "price": 48000, "colour": "Chalk"},
    {"id": "2", "name": "The Studio Overshirt", "category": "tops", "price": 58000, "colour": "Rust"},
    {"id": "3", "name": "The Daily Tee", "category": "tops", "price": 28000, "colour": "White"},
    {"id": "4", "name": "The Pleat Short", "category": "bottoms", "price": 41000, "colour": "Sand"},
    {"id": "5", "name": "The Carry Tote", "category": "accessories", "price": 35000, "colour": "Tan"},
    {"id": "6", "name": "The Frame One", "category": "accessories", "price": 22000, "colour": "Smoke"},
    {"id": "7", "name": "Studio Laptop 14", "category": "devices laptops", "price": 1650000, "colour": "Silver"},
    {"id": "8", "name": "PowerBook Air 13", "category": "devices laptops", "price": 1825000, "colour": "Midnight"},
    {"id": "9", "name": "Pulse Earbuds Pro", "category": "devices audio", "price": 95000, "colour": "Black"},
    {"id": "10", "name": "Studio Mini Speaker", "category": "devices audio", "price": 175000, "colour": "Blue"},
    {"id": "11", "name": "Echo Beam Headset", "category": "devices audio", "price": 210000, "colour": "Sand"},
    {"id": "12", "name": "Arc Smart Watch", "category": "devices wearables", "price": 280000, "colour": "Space Gray"},
    {"id": "13", "name": "Pulse Fit Band", "category": "devices wearables", "price": 120000, "colour": "Rose"},
    {"id": "14", "name": "Dock Charge Hub", "category": "devices accessory", "price": 65000, "colour": "White"},
    {"id": "15", "name": "Game Control Pro", "category": "devices accessory", "price": 140000, "colour": "Black"},
]


def read_orders() -> list[dict]:
    if not ORDERS_FILE.exists():
        return []
    try:
        return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def write_orders(orders: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    ORDERS_FILE.write_text(json.dumps(orders, indent=2), encoding="utf-8")


class StoreHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/health":
            return self.send_json({"status": "ok", "service": "sammy-python-store"})
        if route == "/api/products":
            return self.send_json(PRODUCTS)
        if route == "/api/orders":
            return self.send_json(read_orders())
        if route.startswith("/api/orders/"):
            order_id = unquote(route.rsplit("/", 1)[-1]).lower()
            order = next((item for item in read_orders() if item["id"].lower() == order_id), None)
            if not order:
                return self.send_json({"error": "Order not found."}, 404)
            return self.send_json({"order": order})
        self.serve_file(route)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/orders":
            return self.send_json({"error": "Route not found."}, 404)
        try:
            payload = self.read_json()
            customer = str(payload.get("customer", "")).strip()
            phone = str(payload.get("phone", "")).strip()
            address = str(payload.get("address", "")).strip()
            items = payload.get("items", [])
            total = float(payload.get("total", 0))
            if not customer or not phone or not address or not items or total <= 0:
                return self.send_json({"error": "Complete your customer details and order first."}, 400)
            order = {
                "id": f"SM-{secrets.token_hex(3).upper()}",
                "customer": customer[:100],
                "phone": phone[:40],
                "address": address[:300],
                "items": items[:20],
                "total": total,
                "status": "awaiting-payment",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            orders = read_orders()
            orders.append(order)
            write_orders(orders)
            return self.send_json({"order": order}, 201)
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send_json({"error": "The order data was not valid JSON."}, 400)

    def do_PATCH(self) -> None:
        route = urlparse(self.path).path
        if not route.startswith("/api/orders/"):
            return self.send_json({"error": "Route not found."}, 404)
        try:
            order_id = unquote(route.rsplit("/", 1)[-1]).lower()
            status = str(self.read_json().get("status", "")).strip()
            allowed = {"awaiting-payment", "processing", "shipped", "out-for-delivery", "delivered"}
            if status not in allowed:
                return self.send_json({"error": "Unsupported order status."}, 400)
            orders = read_orders()
            order = next((item for item in orders if item["id"].lower() == order_id), None)
            if not order:
                return self.send_json({"error": "Order not found."}, 404)
            order["status"] = status
            order["updatedAt"] = datetime.now(timezone.utc).isoformat()
            write_orders(orders)
            return self.send_json({"order": order})
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send_json({"error": "The status data was not valid JSON."}, 400)

    def serve_file(self, route: str) -> None:
        relative = unquote(route.lstrip("/")) or "sammy-business.html"
        requested = (ROOT / relative).resolve()
        if ROOT not in requested.parents and requested != ROOT:
            return self.send_error(403)
        if not requested.is_file():
            return self.send_error(404)
        content = requested.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(requested.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[sammy-python] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), StoreHandler)
    print(f"sammy.com Python store running at http://{HOST}:{PORT}/sammy-business.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStore server stopped.")
    finally:
        server.server_close()
