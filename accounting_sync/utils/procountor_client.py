import requests
from django.conf import settings
from typing import Dict, List, Optional


class ProcountorClient:
    """
    Client for Procountor API.

    Procountor uses REST API with OAuth 2.0 or API key authentication.
    Documentation: https://dev.procountor.com/
    """

    def __init__(self):
        self.api_key = settings.PROCOUNTOR_API_KEY
        self.company_id = settings.PROCOUNTOR_COMPANY_ID
        self.base_url = settings.PROCOUNTOR_BASE_URL.rstrip('/')

    def _get_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Procountor API."""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated request to Procountor API."""
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
            return response.json() if response.content else {}

        except requests.RequestException as e:
            raise Exception(f"Procountor API request failed: {str(e)}")

    def get_sales_invoices(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 0,
        size: int = 100
    ) -> List[Dict]:
        """
        Fetch sales invoices (receivables) from Procountor.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page: Page number for pagination (0-indexed)
            size: Number of items per page
        """
        params = {
            'page': page,
            'size': size,
            'orderById': 'DESC'
        }

        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date

        try:
            endpoint = f'/api/invoices'
            data = self._make_request('GET', endpoint, params)

            if isinstance(data, dict):
                return data.get('results', [])
            return data if isinstance(data, list) else []

        except Exception as e:
            raise Exception(f"Failed to fetch sales invoices from Procountor: {str(e)}")

    def get_sales_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed sales invoice by ID."""
        try:
            return self._make_request('GET', f'/api/invoices/{invoice_id}')

        except Exception as e:
            raise Exception(f"Failed to fetch sales invoice {invoice_id} from Procountor: {str(e)}")

    def get_purchase_invoices(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 0,
        size: int = 100
    ) -> List[Dict]:
        """
        Fetch purchase invoices (payables) from Procountor.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            page: Page number for pagination (0-indexed)
            size: Number of items per page
        """
        params = {
            'page': page,
            'size': size,
            'orderById': 'DESC'
        }

        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date

        try:
            endpoint = f'/api/purchaseinvoices'
            data = self._make_request('GET', endpoint, params)

            if isinstance(data, dict):
                return data.get('results', [])
            return data if isinstance(data, list) else []

        except Exception as e:
            raise Exception(f"Failed to fetch purchase invoices from Procountor: {str(e)}")

    def get_purchase_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed purchase invoice by ID."""
        try:
            return self._make_request('GET', f'/api/purchaseinvoices/{invoice_id}')

        except Exception as e:
            raise Exception(f"Failed to fetch purchase invoice {invoice_id} from Procountor: {str(e)}")

    def get_customers(self, page: int = 0, size: int = 100) -> List[Dict]:
        """Fetch customers from Procountor."""
        params = {'page': page, 'size': size}

        try:
            data = self._make_request('GET', '/api/customers', params)

            if isinstance(data, dict):
                return data.get('results', [])
            return data if isinstance(data, list) else []

        except Exception as e:
            raise Exception(f"Failed to fetch customers from Procountor: {str(e)}")

    def get_ledger_receipts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """Fetch ledger receipts which may include both receivables and payables."""
        params = {}

        if start_date:
            params['startDate'] = start_date
        if end_date:
            params['endDate'] = end_date

        try:
            data = self._make_request('GET', '/api/ledgerreceipts', params)

            if isinstance(data, dict):
                return data.get('results', [])
            return data if isinstance(data, list) else []

        except Exception as e:
            raise Exception(f"Failed to fetch ledger receipts from Procountor: {str(e)}")
