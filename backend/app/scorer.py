import os
import time
from typing import Dict, Iterable, List, Optional


class PrivacyDebtScorer:
    """Privacy Debt Score engine with category breakdown and demo-friendly severity."""

    WEIGHTS = {
        "Aadhaar": 20,
        "SSN": 20,
        "CreditCard": 18,
        "PAN": 15,
        "Email": 8,
        "Phone": 10,
        "BankAccount": 12,
        "RoutingCode": 10,
        "Secret": 16,
        "APIKey": 16,
        "Medical": 5,
        "Name": 5,
        "Organization": 5,
        "Location": 5,
    }

    CATEGORY_BY_TYPE = {
        "Aadhaar": "identity",
        "SSN": "identity",
        "PAN": "identity",
        "Name": "identity",
        "CreditCard": "financial",
        "BankAccount": "financial",
        "RoutingCode": "financial",
        "Email": "contact",
        "Phone": "contact",
        "Organization": "contact",
        "Location": "location",
        "Secret": "credentials",
        "APIKey": "credentials",
        "Medical": "medical",
    }

    ONE_YEAR_SECONDS = 365 * 24 * 60 * 60

    def calculate_score(self, pii_results, file_metadata: Optional[Dict] = None) -> Dict:
        detections = self._normalize_detections(pii_results)
        file_metadata = file_metadata or {}

        breakdown = {
            "identity": 0,
            "financial": 0,
            "contact": 0,
            "credentials": 0,
            "medical": 0,
            "location": 0,
            "other": 0,
            "bonuses": 0,
        }

        weighted_detections = []
        for detection in detections:
            pii_type = detection["pii_type"]
            weight = self.WEIGHTS.get(pii_type, 5)
            category = detection.get("category") or self.CATEGORY_BY_TYPE.get(pii_type, "other")
            breakdown[category] = breakdown.get(category, 0) + weight
            weighted_detections.append(
                {
                    "pii_type": pii_type,
                    "category": category,
                    "weight": weight,
                    "method": detection.get("method", "unknown"),
                    "confidence": detection.get("confidence"),
                }
            )

        bonuses = self._calculate_bonuses(file_metadata)
        breakdown["bonuses"] = sum(item["weight"] for item in bonuses)

        raw_score = sum(item["weight"] for item in weighted_detections) + breakdown["bonuses"]
        score = min(raw_score, 100)
        return {
            "score": score,
            "raw_score": raw_score,
            "severity": self._severity(score),
            "breakdown": breakdown,
            "detections": weighted_detections,
            "bonuses": bonuses,
        }

    def _normalize_detections(self, pii_results) -> List[Dict]:
        if isinstance(pii_results, dict):
            if "detections" in pii_results:
                return list(pii_results["detections"])
            return [{"pii_type": item} for item in pii_results.get("pii_types", [])]

        if isinstance(pii_results, Iterable):
            return [item if isinstance(item, dict) else {"pii_type": str(item)} for item in pii_results]

        return []

    def _calculate_bonuses(self, file_metadata: Dict) -> List[Dict]:
        bonuses = []
        path = str(file_metadata.get("path", "")).lower()
        if "downloads" in path or "appdata" in path:
            bonuses.append({"reason": "sensitive_location", "weight": 2})

        modified = file_metadata.get("modified") or file_metadata.get("mtime")
        if modified and not file_metadata.get("encrypted", False):
            if time.time() - float(modified) > self.ONE_YEAR_SECONDS:
                bonuses.append({"reason": "old_unencrypted_file", "weight": 2})

        return bonuses

    def _severity(self, score: int) -> str:
        if score >= 70:
            return "orange"
        if score >= 30:
            return "yellow"
        return "green"


def calculate_score(pii_results, file_metadata: Optional[Dict] = None) -> Dict:
    return PrivacyDebtScorer().calculate_score(pii_results, file_metadata)


if __name__ == "__main__":
    old_timestamp = time.time() - (366 * 24 * 60 * 60)
    before = [
        {"pii_type": "Aadhaar"},
        {"pii_type": "PAN"},
        {"pii_type": "CreditCard"},
        {"pii_type": "Email"},
        {"pii_type": "Phone"},
        {"pii_type": "Medical"},
    ]
    after = [{"pii_type": "Email"}]

    print("Before remediation:", calculate_score(before, {"path": os.path.expanduser("~/Downloads/demo.txt")}))
    print("After remediation:", calculate_score(after, {"path": os.path.expanduser("~/Downloads/demo.txt"), "modified": old_timestamp}))
