import requests
from django.conf import settings
from typing import Dict, List, Optional
import base64


class EbayClient:
    """
    Client for eBay Sell Fulfillment API and Order API.

    eBay uses OAuth 2.0 authentication.
    Documentation: https://developer.ebay.com/api-docs/sell/fulfillment/overview.html
    """

    def __init__(self):
        self.client_id = settings.EBAY_CLIENT_ID
        self.client_secret = settings.EBAY_CLIENT_SECRET
        self.refresh_token = settings.EBAY_REFRESH_TOKEN
        self.environment = settings.EBAY_ENVIRONMENT  # 'production' or 'sandbox'

        if self.environment == 'production':
            self.api_base_url = 'https://api.ebay.com'
            self.auth_url = 'https://api.ebay.com/identity/v1/oauth2/token'
        else:
            self.api_base_url = 'https://api.sandbox.ebay.com'
            self.auth_url = 'https://api.sandbox.ebay.com/identity/v1/oauth2/token'

        self.access_token = None

    def _get_access_token(self) -> str:
        """Get OAuth access token using refresh token."""
        if self.access_token:
            return self.access_token

        # Create basic auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64_credentials}'
        }

        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'scope': 'https://api.ebay.com/oauth/api_scope https://api.ebay.com/oauth/api_scope/sell.fulfillment'
        }

        try:
            response = requests.post(self.auth_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            return self.access_token

        except requests.RequestException as e:
            raise Exception(f"Failed to get eBay access token: {str(e)}")

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers for eBay API."""
        access_token = self._get_access_token()

        return {
            'Authorization': f'Bearer {access_token}',
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
        """Make authenticated request to eBay API."""
        url = f"{self.api_base_url}/{endpoint.lstrip('/')}"
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

            if response.content:
                return response.json()
            return {}

        except requests.RequestException as e:
            raise Exception(f"eBay API request failed: {str(e)}")

    def get_orders(
        self,
        order_creation_date_from: Optional[str] = None,
        order_creation_date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """
        Fetch orders from eBay using Sell Fulfillment API.

        Args:
            order_creation_date_from: ISO 8601 format (e.g., 2024-01-01T00:00:00.000Z)
            order_creation_date_to: ISO 8601 format
            limit: Number of results per page (max 200)
            offset: Offset for pagination

        Returns:
            Dict with 'orders' list and pagination info
        """
        params = {
            'limit': min(limit, 200),
            'offset': offset
        }

        # Build filter string
        filters = []
        if order_creation_date_from:
            filters.append(f"creationdate:[{order_creation_date_from}..")
        if order_creation_date_to:
            if order_creation_date_from:
                filters[-1] = f"creationdate:[{order_creation_date_from}..{order_creation_date_to}]"
            else:
                filters.append(f"creationdate:[..{order_creation_date_to}]")

        if filters:
            params['filter'] = ','.join(filters)

        try:
            endpoint = '/sell/fulfillment/v1/order'
            return self._make_request('GET', endpoint, params)

        except Exception as e:
            raise Exception(f"Failed to fetch orders from eBay: {str(e)}")

    def get_all_orders(
        self,
        order_creation_date_from: Optional[str] = None,
        order_creation_date_to: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all orders with automatic pagination.

        Args:
            order_creation_date_from: ISO 8601 format
            order_creation_date_to: ISO 8601 format

        Returns:
            List of all orders
        """
        all_orders = []
        offset = 0
        limit = 200

        while True:
            response = self.get_orders(
                order_creation_date_from=order_creation_date_from,
                order_creation_date_to=order_creation_date_to,
                limit=limit,
                offset=offset
            )

            orders = response.get('orders', [])
            if not orders:
                break

            all_orders.extend(orders)

            # Check if there are more results
            total = response.get('total', 0)
            if offset + len(orders) >= total:
                break

            offset += limit

        return all_orders

    def get_order(self, order_id: str) -> Dict:
        """
        Fetch a single order by ID.

        Args:
            order_id: eBay order ID

        Returns:
            Order details
        """
        try:
            endpoint = f'/sell/fulfillment/v1/order/{order_id}'
            return self._make_request('GET', endpoint)

        except Exception as e:
            raise Exception(f"Failed to fetch order {order_id} from eBay: {str(e)}")

    def get_transactions(
        self,
        transaction_date_from: Optional[str] = None,
        transaction_date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Fetch transactions from eBay Finances API (for financial data).

        Args:
            transaction_date_from: ISO 8601 format
            transaction_date_to: ISO 8601 format
            limit: Number of results per page (max 1000)
            offset: Offset for pagination

        Returns:
            Dict with 'transactions' list
        """
        params = {
            'limit': min(limit, 1000),
            'offset': offset
        }

        # Build filter
        filters = []
        if transaction_date_from:
            filters.append(f"transactionDate:[{transaction_date_from}..")
        if transaction_date_to:
            if transaction_date_from:
                filters[-1] = f"transactionDate:[{transaction_date_from}..{transaction_date_to}]"
            else:
                filters.append(f"transactionDate:[..{transaction_date_to}]")

        if filters:
            params['filter'] = ','.join(filters)

        try:
            endpoint = '/sell/finances/v1/transaction'
            return self._make_request('GET', endpoint, params)

        except Exception as e:
            raise Exception(f"Failed to fetch transactions from eBay: {str(e)}")

    def get_seller_transactions_legacy(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_number: int = 1,
        entries_per_page: int = 100
    ) -> Dict:
        """
        Fetch seller transactions using Trading API (legacy, but sometimes needed).

        This is a fallback method if the newer APIs don't provide all needed data.

        Args:
            start_time: ISO 8601 format
            end_time: ISO 8601 format
            page_number: Page number (1-indexed)
            entries_per_page: Entries per page (max 200)

        Returns:
            Dict with transaction data
        """
        # Note: Trading API uses XML, this is simplified
        # In production, you might need to use the official eBay SDK
        # or implement XML request/response handling

        params = {
            'ModTimeFrom': start_time,
            'ModTimeTo': end_time,
            'PageNumber': page_number,
            'EntriesPerPage': min(entries_per_page, 200)
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            # This would need proper Trading API implementation
            # Placeholder for now
            return {}

        except Exception as e:
            raise Exception(f"Failed to fetch legacy transactions from eBay: {str(e)}")
