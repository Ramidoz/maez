"""Out-of-process MiniCheck verifier service.

The daemon talks to this local service over HTTP. This is the only module in
the shadow slice that imports torch/transformers, and it lazy-loads them on the
first prediction.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_REPO = "lytang/MiniCheck-DeBERTa-v3-Large"
_MODEL = None
_TOKENIZER = None


def _load():
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _TOKENIZER = AutoTokenizer.from_pretrained(_REPO)
        _MODEL = AutoModelForSequenceClassification.from_pretrained(_REPO)
    return _MODEL, _TOKENIZER


def _predict(evidence: str, claim: str):
    import torch

    model, tokenizer = _load()
    inputs = tokenizer(
        evidence,
        claim,
        truncation=True,
        max_length=2048,
        return_tensors="pt",
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    label = int(torch.argmax(logits, dim=-1).item())
    score = float(torch.softmax(logits, dim=-1)[0, 1].item())
    return ("SUPPORTED" if label == 1 else "UNSUPPORTED"), score


def handle_support(payload: dict) -> dict:
    evidence = payload.get("evidence")
    claim = payload.get("claim")
    if not evidence or not claim:
        return {"error": "evidence and claim are required"}
    verdict, score = _predict(evidence, claim)
    return {"verdict": verdict, "score": score}


def health_payload() -> dict:
    return {"status": "ok", "contract": "minicheck_support.v1"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") != "/health":
            self.send_error(404)
            return
        data = json.dumps(health_payload()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path.rstrip("/") != "/support":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            body = handle_support(payload)
            code = 400 if "error" in body else 200
        except Exception as exc:
            body = {"error": str(exc)}
            code = 500
        data = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    HTTPServer(("127.0.0.1", 8083), Handler).serve_forever()


if __name__ == "__main__":
    main()
