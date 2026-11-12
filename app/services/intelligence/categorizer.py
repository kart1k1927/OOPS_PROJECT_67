"""Intelligent feature C: automatic incident categorization.

Suggests one of the nine seeded categories from the words in the report, with a
confidence and the terms that drove it. The reporter can override it, which is
the point: a suggestion that cannot be corrected is a bug generator.

Weights exist because evidence differs in strength. "vpn" means Network and
nothing else. "slow" means almost nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.intelligence.text import tokenize


@dataclass(frozen=True, slots=True)
class CategorySuggestion:
    category_name: str
    confidence: float
    matched: list[str]

    def explain(self) -> str:
        return f"{self.category_name} suggested from {', '.join(self.matched)}"


class IncidentCategorizer:
    KEYWORDS: dict[str, dict[str, int]] = {
        "Hardware": {
            "laptop": 3, "printer": 3, "monitor": 3, "keyboard": 3, "mouse": 2, "screen": 2,
            "battery": 3, "charger": 3, "projector": 3, "scanner": 3, "desktop": 2, "fan": 2,
            "overheating": 3, "physical": 2, "cable": 2, "port": 2, "device": 1, "hardware": 4,
        },
        "Software": {
            "install": 2, "software": 4, "licence": 3, "license": 3, "update": 2, "version": 2,
            "crash": 3, "crashing": 3, "freeze": 2, "excel": 3, "word": 2, "office": 3,
            "matlab": 3, "patch": 2, "uninstall": 3, "compiler": 3, "ide": 2,
        },
        "Network": {
            "wifi": 4, "network": 4, "internet": 4, "lan": 3, "ethernet": 3, "vpn": 4,
            "connection": 2, "connectivity": 3, "router": 3, "switch": 2, "dns": 3,
            "ping": 3, "latency": 3, "bandwidth": 3, "disconnect": 2, "offline": 2, "proxy": 3,
        },
        "Database": {
            "database": 4, "sql": 4, "query": 3, "table": 2, "postgres": 4, "mysql": 4,
            "oracle": 3, "deadlock": 4, "index": 2, "backup": 2, "replication": 3, "schema": 3,
        },
        "Cloud": {
            "cloud": 4, "aws": 4, "azure": 4, "gcp": 4, "bucket": 3, "instance": 2,
            "kubernetes": 4, "docker": 3, "container": 3, "deployment": 2, "serverless": 3, "supabase": 3,
        },
        "Security": {
            "phishing": 4, "malware": 4, "virus": 4, "ransomware": 4, "breach": 4, "attack": 3,
            "suspicious": 3, "unauthorized": 3, "unauthorised": 3, "hacked": 4, "spam": 2,
            "firewall": 3, "vulnerability": 3, "security": 4,
        },
        "Authentication": {
            "login": 4, "password": 4, "signin": 3, "credentials": 4, "otp": 4, "mfa": 4,
            "sso": 4, "locked": 3, "account": 2, "authenticate": 4, "authentication": 4,
            "reset": 2, "token": 2, "session": 2, "expired": 2,
        },
        "Application": {
            "application": 3, "portal": 3, "website": 3, "page": 2, "error": 1, "timeout": 2,
            "transaction": 3, "payment": 3, "checkout": 3, "form": 2, "submit": 2,
            "dashboard": 2, "api": 2, "500": 2, "unavailable": 2,
        },
        "Storage": {
            "storage": 4, "disk": 4, "space": 3, "quota": 4, "full": 2, "drive": 3,
            "folder": 2, "file": 2, "nas": 3, "share": 2, "onedrive": 3, "gdrive": 3, "capacity": 3,
        },
    }

    MIN_CONFIDENCE = 0.25

    def suggest(self, title: str, description: str | None = None) -> CategorySuggestion | None:
        tokens = tokenize(f"{title} {description or ''}")
        if not tokens:
            return None

        scores: dict[str, tuple[int, list[str]]] = {}
        for category, keywords in self.KEYWORDS.items():
            hits = [(word, weight) for word, weight in keywords.items() if word in tokens]
            if hits:
                scores[category] = (sum(w for _, w in hits), [word for word, _ in hits])

        if not scores:
            return None

        total = sum(score for score, _ in scores.values())
        category, (score, matched) = max(scores.items(), key=lambda kv: kv[1][0])
        confidence = round(score / total, 3) if total else 0.0
        if confidence < self.MIN_CONFIDENCE:
            return None
        return CategorySuggestion(category, confidence, sorted(matched)[:4])

    def rank(self, title: str, description: str | None = None, *, limit: int = 3) -> list[CategorySuggestion]:
        tokens = tokenize(f"{title} {description or ''}")
        out: list[CategorySuggestion] = []
        for category, keywords in self.KEYWORDS.items():
            hits = [(w, k) for w, k in keywords.items() if w in tokens]
            if hits:
                out.append(CategorySuggestion(category, float(sum(k for _, k in hits)), sorted(w for w, _ in hits)[:4]))
        out.sort(key=lambda s: s.confidence, reverse=True)
        return out[:limit]
