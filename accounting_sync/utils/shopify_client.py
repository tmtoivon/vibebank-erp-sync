import requests
from django.conf import settings
from typing import Dict, List, Optional
from datetime import datetime


class ShopifyClient:
    """
    Client for Shopify Admin API.

    Shopify uses REST API with API access token authentication.
    Documentation: https://shopify.dev/docs/api/admin-rest
    """

    def __init__(self):
        self.shop_name = settings.SHOPIFY_SHOP_NAME
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = settings.SHOPIFY_API_VERSION
        self.base_url = f"https://{self.shop_name}.myshopify.com/admin/api/{self.api_version}"

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Shopify API."""
        return {
            'X-Shopify-Access-Token': self.access_token,
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
        """Make authenticated request to Shopify API."""
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
            raise Exception(f"Shopify API request failed: {str(e)}")

    def get_orders(
        self,
        status: str = 'any',
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None,
        updated_at_min: Optional[str] = None,
        updated_at_max: Optional[str] = None,
        limit: int = 250,
        fields: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch orders from Shopify.

        Args:
            status: Filter orders by status (open, closed, cancelled, any)
            created_at_min: Show orders created after date (ISO 8601 format)
            created_at_max: Show orders created before date (ISO 8601 format)
            updated_at_min: Show orders updated after date (ISO 8601 format)
            updated_at_max: Show orders updated before date (ISO 8601 format)
            limit: Number of results (max 250)
            fields: Comma-separated list of fields to include
        """
        params = {
            'status': status,
            'limit': min(limit, 250)
        }

        if created_at_min:
            params['created_at_min'] = created_at_min
        if created_at_max:
            params['created_at_max'] = created_at_max
        if updated_at_min:
            params['updated_at_min'] = updated_at_min
        if updated_at_max:
            params['updated_at_max'] = updated_at_max
        if fields:
            params['fields'] = fields

        try:
            all_orders = []
            page_info = None

            while True:
                if page_info:
                    params['page_info'] = page_info

                data = self._make_request('GET', '/orders.json', params)
                orders = data.get('orders', [])

                if not orders:
                    break

                all_orders.extend(orders)

                link_header = data.get('link', '')
                if 'rel="next"' in link_header:
                    page_info = self._extract_page_info(link_header)
                    if page_info:
                        params = {'limit': limit, 'page_info': page_info}
                    else:
                        break
                else:
                    break

                if len(orders) < limit:
                    break

            return all_orders

        except Exception as e:
            raise Exception(f"Failed to fetch orders from Shopify: {str(e)}")

    def get_order(self, order_id: str) -> Dict:
        """Fetch a single order by ID."""
        try:
            data = self._make_request('GET', f'/orders/{order_id}.json')
            return data.get('order', {})

        except Exception as e:
            raise Exception(f"Failed to fetch order {order_id} from Shopify: {str(e)}")

    def get_customers(self, limit: int = 250) -> List[Dict]:
        """Fetch customers from Shopify."""
        params = {'limit': min(limit, 250)}

        try:
            data = self._make_request('GET', '/customers.json', params)
            return data.get('customers', [])

        except Exception as e:
            raise Exception(f"Failed to fetch customers from Shopify: {str(e)}")

    def get_customer(self, customer_id: str) -> Dict:
        """Fetch a single customer by ID."""
        try:
            data = self._make_request('GET', f'/customers/{customer_id}.json')
            return data.get('customer', {})

        except Exception as e:
            raise Exception(f"Failed to fetch customer {customer_id} from Shopify: {str(e)}")

    def _extract_page_info(self, link_header: str) -> Optional[str]:
        """Extract page_info parameter from Link header for pagination."""
        import re
        match = re.search(r'page_info=([^&>]+)', link_header)
        return match.group(1) if match else None

    def get_financial_status_orders(
        self,
        financial_status: str,
        created_at_min: Optional[str] = None,
        created_at_max: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch orders by financial status.

        Args:
            financial_status: pending, authorized, paid, partially_paid, refunded, voided, partially_refunded, any
            created_at_min: Start date (ISO 8601)
            created_at_max: End date (ISO 8601)
        """
        params = {
            'financial_status': financial_status,
            'status': 'any',
            'limit': 250
        }

        if created_at_min:
            params['created_at_min'] = created_at_min
        if created_at_max:
            params['created_at_max'] = created_at_max

        try:
            data = self._make_request('GET', '/orders.json', params)
            return data.get('orders', [])

        except Exception as e:
            raise Exception(f"Failed to fetch orders by financial status from Shopify: {str(e)}")
