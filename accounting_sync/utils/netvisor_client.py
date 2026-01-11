import hashlib
import requests
from datetime import datetime
from django.conf import settings
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET


class NetvisorClient:
    """
    Client for Netvisor API.

    Netvisor uses XML-based API with custom authentication headers.
    Documentation: https://support.netvisor.fi/en/support/solutions/77000205228
    """

    def __init__(self):
        self.host = settings.NETVISOR_HOST
        self.sender = settings.NETVISOR_SENDER
        self.customer_id = settings.NETVISOR_CUSTOMER_ID
        self.customer_key = settings.NETVISOR_CUSTOMER_KEY
        self.partner_id = settings.NETVISOR_PARTNER_ID
        self.partner_key = settings.NETVISOR_PARTNER_KEY
        self.organization_id = settings.NETVISOR_ORGANIZATION_ID
        self.language = settings.NETVISOR_LANGUAGE

    def _generate_mac(self, url: str, timestamp: str, transaction_id: str) -> str:
        """Generate MAC hash for authentication."""
        mac_string = (
            f"{url}&{self.sender}&{self.customer_id}&{timestamp}&"
            f"{self.language}&{self.organization_id}&{transaction_id}&"
            f"{self.customer_key}&{self.partner_key}"
        )
        return hashlib.md5(mac_string.encode()).hexdigest()

    def _get_headers(self, endpoint: str) -> Dict[str, str]:
        """Generate authentication headers for Netvisor API."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        transaction_id = datetime.now().strftime('%Y%m%d%H%M%S%f')

        url_for_mac = endpoint.replace(f'{self.host}/', '')
        mac = self._generate_mac(url_for_mac, timestamp, transaction_id)

        return {
            'X-Netvisor-Authentication-Sender': self.sender,
            'X-Netvisor-Authentication-CustomerId': self.customer_id,
            'X-Netvisor-Authentication-PartnerId': self.partner_id,
            'X-Netvisor-Authentication-Timestamp': timestamp,
            'X-Netvisor-Authentication-TransactionId': transaction_id,
            'X-Netvisor-Authentication-MAC': mac,
            'X-Netvisor-Organisation-ID': self.organization_id,
            'X-Netvisor-Interface-Language': self.language,
            'Content-Type': 'text/xml'
        }

    def _parse_xml_response(self, response_text: str) -> ET.Element:
        """Parse XML response and check for errors."""
        root = ET.fromstring(response_text)

        status = root.find('.//ResponseStatus/Status')
        if status is not None and status.text != 'OK':
            error_msg = root.find('.//ResponseStatus/StatusMessage')
            raise Exception(f"Netvisor API error: {error_msg.text if error_msg is not None else 'Unknown error'}")

        return root

    def get_sales_invoices(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        Fetch sales invoices (receivables) from Netvisor.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        endpoint = f"{self.host}/salesinvoicelist.nv"

        params = {}
        if start_date:
            params['startdate'] = start_date
        if end_date:
            params['enddate'] = end_date

        headers = self._get_headers(endpoint)

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            root = self._parse_xml_response(response.text)
            invoices = []

            for invoice in root.findall('.//SalesInvoice'):
                invoices.append({
                    'id': invoice.find('NetvisorKey').text if invoice.find('NetvisorKey') is not None else None,
                    'invoice_number': invoice.find('InvoiceNumber').text if invoice.find('InvoiceNumber') is not None else None,
                    'invoice_date': invoice.find('InvoiceDate').text if invoice.find('InvoiceDate') is not None else None,
                    'due_date': invoice.find('InvoiceDueDate').text if invoice.find('InvoiceDueDate') is not None else None,
                    'customer_name': invoice.find('CustomerName').text if invoice.find('CustomerName') is not None else None,
                    'amount': invoice.find('InvoiceAmount').text if invoice.find('InvoiceAmount') is not None else None,
                    'status': invoice.find('InvoiceStatus').text if invoice.find('InvoiceStatus') is not None else None,
                    'raw': ET.tostring(invoice, encoding='unicode')
                })

            return invoices

        except requests.RequestException as e:
            raise Exception(f"Failed to fetch sales invoices from Netvisor: {str(e)}")

    def get_sales_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed sales invoice by ID."""
        endpoint = f"{self.host}/getsalesinvoice.nv"
        params = {'netvisorkey': invoice_id}
        headers = self._get_headers(endpoint)

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            root = self._parse_xml_response(response.text)
            return {'raw': response.text, 'parsed': root}

        except requests.RequestException as e:
            raise Exception(f"Failed to fetch sales invoice {invoice_id} from Netvisor: {str(e)}")

    def get_purchase_invoices(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """
        Fetch purchase invoices (payables) from Netvisor.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        endpoint = f"{self.host}/purchaseinvoicelist.nv"

        params = {}
        if start_date:
            params['startdate'] = start_date
        if end_date:
            params['enddate'] = end_date

        headers = self._get_headers(endpoint)

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            root = self._parse_xml_response(response.text)
            invoices = []

            for invoice in root.findall('.//PurchaseInvoice'):
                invoices.append({
                    'id': invoice.find('NetvisorKey').text if invoice.find('NetvisorKey') is not None else None,
                    'invoice_number': invoice.find('InvoiceNumber').text if invoice.find('InvoiceNumber') is not None else None,
                    'invoice_date': invoice.find('InvoiceDate').text if invoice.find('InvoiceDate') is not None else None,
                    'due_date': invoice.find('DueDate').text if invoice.find('DueDate') is not None else None,
                    'vendor_name': invoice.find('VendorName').text if invoice.find('VendorName') is not None else None,
                    'amount': invoice.find('Amount').text if invoice.find('Amount') is not None else None,
                    'status': invoice.find('Status').text if invoice.find('Status') is not None else None,
                    'raw': ET.tostring(invoice, encoding='unicode')
                })

            return invoices

        except requests.RequestException as e:
            raise Exception(f"Failed to fetch purchase invoices from Netvisor: {str(e)}")

    def get_purchase_invoice(self, invoice_id: str) -> Dict:
        """Fetch detailed purchase invoice by ID."""
        endpoint = f"{self.host}/getpurchaseinvoice.nv"
        params = {'netvisorkey': invoice_id}
        headers = self._get_headers(endpoint)

        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            root = self._parse_xml_response(response.text)
            return {'raw': response.text, 'parsed': root}

        except requests.RequestException as e:
            raise Exception(f"Failed to fetch purchase invoice {invoice_id} from Netvisor: {str(e)}")
