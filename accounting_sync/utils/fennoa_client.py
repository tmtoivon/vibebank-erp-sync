import requests
from django.conf import settings
from typing import Dict, List, Optional


class FennoaClient:
    """
    Client for Fennoa API.

    Fennoa uses REST API with API key authentication.
    Documentation: https://tietopankki.fennoa.com/api-accounting
    """

    def __init__(self):
        self.api_key = settings.FENNOA_API_KEY
        self.base_url = settings.FENNOA_BASE_URL.rstrip('/')

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Fennoa API."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Fennoa API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            raise Exception(f"Fennoa API request failed: {str(e)}")

    def get_sales_invoices(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        per_page: int = 100
    ) -> List[Dict]:
        """
        Fetch sales invoices (receivables) from Fennoa.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page: Page number for pagination
            per_page: Number of items per page
        """
        params = {
            'page': page,
            'per_page': per_page
        }

        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            data = self._make_request('GET', '/api/v1/sales_invoices', params)
            return data.get('invoices', []) if isinstance(data, dict) else data

        except Exception as e:
            raise Exception(f"Failed to fetch sales invoices from Fennoa: {str(e)}")

    def get_sales_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed sales invoice by ID."""
        try:
            return self._make_request('GET', f'/api/v1/sales_invoices/{invoice_id}')

        except Exception as e:
            raise Exception(f"Failed to fetch sales invoice {invoice_id} from Fennoa: {str(e)}")

    def get_purchase_invoices(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        per_page: int = 100
    ) -> List[Dict]:
        """
        Fetch purchase invoices (payables) from Fennoa.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page: Page number for pagination
            per_page: Number of items per page
        """
        params = {
            'page': page,
            'per_page': per_page
        }

        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date

        try:
            data = self._make_request('GET', '/api/v1/purchase_invoices', params)
            return data.get('invoices', []) if isinstance(data, dict) else data

        except Exception as e:
            raise Exception(f"Failed to fetch purchase invoices from Fennoa: {str(e)}")

    def get_purchase_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed purchase invoice by ID."""
        try:
            return self._make_request('GET', f'/api/v1/purchase_invoices/{invoice_id}')

        except Exception as e:
            raise Exception(f"Failed to fetch purchase invoice {invoice_id} from Fennoa: {str(e)}")

    def get_customers(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch customers from Fennoa."""
        params = {'page': page, 'per_page': per_page}

        try:
            data = self._make_request('GET', '/api/v1/customers', params)
            return data.get('customers', []) if isinstance(data, dict) else data

        except Exception as e:
            raise Exception(f"Failed to fetch customers from Fennoa: {str(e)}")

    def get_vendors(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Fetch vendors/suppliers from Fennoa."""
        params = {'page': page, 'per_page': per_page}

        try:
            data = self._make_request('GET', '/api/v1/suppliers', params)
            return data.get('suppliers', []) if isinstance(data, dict) else data

        except Exception as e:
            raise Exception(f"Failed to fetch vendors from Fennoa: {str(e)}")
