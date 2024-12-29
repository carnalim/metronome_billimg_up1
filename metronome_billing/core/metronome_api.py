from typing import Dict, List, Optional
import requests
import csv
from datetime import datetime
from pathlib import Path
from ..utils.config import Config

class MetronomeAPI:
    BASE_URL = "https://api.metronome.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.config = Config()
        self.api_key = api_key or self.config.metronome_api_key
        print(f"Using API key: {self.api_key[:8]}...")  # Print first 8 chars for verification
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, **kwargs)
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text[:500]}")  # Print first 500 chars of response
        response.raise_for_status()
        return response.json()

    def list_customers(self, limit: int = 100, cursor: Optional[str] = None) -> Dict:
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._make_request("GET", "/customers", params=params)

    def get_all_customers(self) -> List[Dict]:
        all_customers = []
        cursor = None

        while True:
            response = self.list_customers(cursor=cursor)
            customers = response.get("data", [])
            all_customers.extend(customers)

            # Metronome API doesn't seem to support pagination for customers yet
            break

        return all_customers