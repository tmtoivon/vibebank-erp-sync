import requests
from django.conf import settings
from typing import Dict, List, Optional


class EtsyClient:
    """
    Client for Etsy Open API v3.

    Etsy uses REST API with OAuth 2.0 authentication.
    Documentation: https://developers.etsy.com/documentation/
    """

    def __init__(self):
        self.api_key = settings.ETSY_API_KEY
        self.access_token = settings.ETSY_ACCESS_TOKEN
        self.shop_id = settings.ETSY_SHOP_ID
        self.base_url = 'https://openapi.etsy.com/v3'

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Etsy API."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict:
        """Make authenticated request to Etsy API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            raise Exception(f"Etsy API request failed: {str(e)}")

    def get_shop_receipts(
        self,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None,
        min_last_modified: Optional[int] = None,
        max_last_modified: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        was_paid: Optional[bool] = None,
        was_shipped: Optional[bool] = None
    ) -> Dict:
        """
        Fetch shop receipts (orders) from Etsy.

        Args:
            min_created: Earliest creation timestamp (Unix epoch seconds)
            max_created: Latest creation timestamp (Unix epoch seconds)
            min_last_modified: Earliest modification timestamp (Unix epoch seconds)
            max_last_modified: Latest modification timestamp (Unix epoch seconds)
            limit: Number of results per page (max 100)
            offset: Offset for pagination
            was_paid: Filter by payment status
            was_shipped: Filter by shipping status

        Returns:
            Dict with 'results' list and 'count' total
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset
        }

        if min_created:
            params['min_created'] = min_created
        if max_created:
            params['max_created'] = max_created
        if min_last_modified:
            params['min_last_modified'] = min_last_modified
        if max_last_modified:
            params['max_last_modified'] = max_last_modified
        if was_paid is not None:
            params['was_paid'] = str(was_paid).lower()
        if was_shipped is not None:
            params['was_shipped'] = str(was_shipped).lower()

        try:
            endpoint = f'/application/shops/{self.shop_id}/receipts'
            return self._make_request('GET', endpoint, params)

        except Exception as e:
            raise Exception(f"Failed to fetch receipts from Etsy: {str(e)}")

    def get_all_receipts(
        self,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None,
        **kwargs
    ) -> List[Dict]:
        """
        Fetch all receipts with automatic pagination.

        Args:
            min_created: Earliest creation timestamp (Unix epoch seconds)
            max_created: Latest creation timestamp (Unix epoch seconds)
            **kwargs: Additional parameters for get_shop_receipts
        """
        all_receipts = []
        offset = 0
        limit = 100

        while True:
            response = self.get_shop_receipts(
                min_created=min_created,
                max_created=max_created,
                limit=limit,
                offset=offset,
                **kwargs
            )

            receipts = response.get('results', [])
            if not receipts:
                break

            all_receipts.extend(receipts)

            if len(receipts) < limit:
                break

            offset += limit

        return all_receipts

    def get_shop_receipt(self, receipt_id: int) -> Dict:
        """Fetch a single receipt by ID."""
        try:
            endpoint = f'/application/shops/{self.shop_id}/receipts/{receipt_id}'
            data = self._make_request('GET', endpoint)
            return data

        except Exception as e:
            raise Exception(f"Failed to fetch receipt {receipt_id} from Etsy: {str(e)}")

    def get_shop_receipt_transactions(self, receipt_id: int) -> List[Dict]:
        """
        Fetch transactions (line items) for a receipt.

        Returns list of transaction objects with product details.
        """
        try:
            endpoint = f'/application/shops/{self.shop_id}/receipts/{receipt_id}/transactions'
            data = self._make_request('GET', endpoint)
            return data.get('results', [])

        except Exception as e:
            raise Exception(f"Failed to fetch transactions for receipt {receipt_id} from Etsy: {str(e)}")

    def get_shop_payment_account_ledger_entries(
        self,
        min_created: Optional[int] = None,
        max_created: Optional[int] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Fetch payment account ledger entries.

        This provides financial transaction data including payments, fees, and refunds.
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset
        }

        if min_created:
            params['min_created'] = min_created
        if max_created:
            params['max_created'] = max_created

        try:
            endpoint = f'/application/shops/{self.shop_id}/payment-account/ledger-entries'
            return self._make_request('GET', endpoint, params)

        except Exception as e:
            raise Exception(f"Failed to fetch ledger entries from Etsy: {str(e)}")

    def get_shop(self) -> Dict:
        """Fetch shop information."""
        try:
            endpoint = f'/application/shops/{self.shop_id}'
            return self._make_request('GET', endpoint)

        except Exception as e:
            raise Exception(f"Failed to fetch shop info from Etsy: {str(e)}")
