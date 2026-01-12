import anthropic
from django.conf import settings
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import datetime, timedelta
import json
from typing import Dict, List, Optional

from accounting_sync.models import Receivable, Payable, Customer, ERPSystem


class FinancialDataQueryService:
    """Service for querying financial data based on natural language queries."""

    def __init__(self, whatsapp_customer):
        self.whatsapp_customer = whatsapp_customer
        self.linked_customers = list(whatsapp_customer.linked_customers.all())
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def query(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Process a natural language query about receivables and payables.

        Returns:
            Dict with 'response' (text) and 'data' (structured data)
        """
        if conversation_history is None:
            conversation_history = []

        # Get financial data for context
        financial_context = self._get_financial_context()

        # Build the system prompt with tools
        system_prompt = self._build_system_prompt(financial_context)

        # Add user message to conversation
        messages = conversation_history + [
            {"role": "user", "content": user_message}
        ]

        try:
            # Call Claude with tool use
            response = self.client.messages.create(
                model=settings.WHATSAPP_LLM_MODEL,
                max_tokens=2000,
                system=system_prompt,
                messages=messages,
                tools=self._get_tools()
            )

            # Process the response
            result = self._process_response(response, financial_context)

            return {
                'response': result['text'],
                'data': result.get('data', {}),
                'tokens_used': response.usage.input_tokens + response.usage.output_tokens,
                'model': settings.WHATSAPP_LLM_MODEL
            }

        except Exception as e:
            return {
                'response': f"I apologize, but I encountered an error processing your request: {str(e)}",
                'data': {},
                'tokens_used': 0,
                'model': settings.WHATSAPP_LLM_MODEL
            }

    def _get_financial_context(self) -> Dict:
        """Get current financial data for the customer."""
        if not self.linked_customers:
            return {
                'has_data': False,
                'message': 'No linked customers found'
            }

        customer_ids = [c.id for c in self.linked_customers]

        # Get receivables
        receivables = Receivable.objects.filter(
            customer_id__in=customer_ids
        ).order_by('-invoice_date')

        # Get summary statistics
        total_receivables = receivables.aggregate(
            total=Sum('amount_gross'),
            outstanding=Sum('amount_outstanding')
        )

        outstanding_receivables = receivables.filter(
            amount_outstanding__gt=0
        ).order_by('due_date')

        overdue_receivables = outstanding_receivables.filter(
            due_date__lt=datetime.now().date()
        )

        # Get payables (if customer is also a vendor)
        payables = Payable.objects.filter(
            vendor__name__in=[c.name for c in self.linked_customers]
        ).order_by('-invoice_date')

        total_payables = payables.aggregate(
            total=Sum('amount_gross'),
            outstanding=Sum('amount_outstanding')
        )

        outstanding_payables = payables.filter(
            amount_outstanding__gt=0
        ).order_by('due_date')

        return {
            'has_data': True,
            'customer_names': [c.name for c in self.linked_customers],
            'receivables': {
                'total_count': receivables.count(),
                'total_amount': float(total_receivables['total'] or 0),
                'outstanding_amount': float(total_receivables['outstanding'] or 0),
                'overdue_count': overdue_receivables.count(),
                'overdue_amount': float(overdue_receivables.aggregate(Sum('amount_outstanding'))['amount_outstanding__sum'] or 0),
                'recent': self._serialize_invoices(receivables[:5]),
                'outstanding': self._serialize_invoices(outstanding_receivables[:10]),
                'overdue': self._serialize_invoices(overdue_receivables[:10]),
            },
            'payables': {
                'total_count': payables.count(),
                'total_amount': float(total_payables['total'] or 0),
                'outstanding_amount': float(total_payables['outstanding'] or 0),
                'recent': self._serialize_invoices(payables[:5]),
                'outstanding': self._serialize_invoices(outstanding_payables[:10]),
            }
        }

    def _serialize_invoices(self, invoices) -> List[Dict]:
        """Serialize invoice queryset to dict."""
        return [
            {
                'invoice_number': inv.invoice_number,
                'date': inv.invoice_date.isoformat(),
                'due_date': inv.due_date.isoformat(),
                'amount': float(inv.amount_gross),
                'outstanding': float(inv.amount_outstanding),
                'status': inv.status,
                'currency': inv.currency,
                'source': inv.source_system,
            }
            for inv in invoices
        ]

    def _build_system_prompt(self, financial_context: Dict) -> str:
        """Build the system prompt with financial context."""
        if not financial_context.get('has_data'):
            return """You are a helpful financial assistant for a banking application accessed via WhatsApp.
The user has not yet linked any customer accounts, so you cannot provide specific financial information.
Please inform them politely and guide them on how to link their account."""

        customer_names = ", ".join(financial_context['customer_names'])
        receivables = financial_context['receivables']
        payables = financial_context['payables']

        return f"""You are a helpful financial assistant for a banking application accessed via WhatsApp.

You are helping: {customer_names}

CURRENT FINANCIAL SUMMARY:
- Total Receivables (Sales/Income): {receivables['total_count']} invoices, ${receivables['total_amount']:.2f} total
- Outstanding Receivables: ${receivables['outstanding_amount']:.2f}
- Overdue Receivables: {receivables['overdue_count']} invoices, ${receivables['overdue_amount']:.2f}

- Total Payables (Purchases/Expenses): {payables['total_count']} invoices, ${payables['total_amount']:.2f} total
- Outstanding Payables: ${payables['outstanding_amount']:.2f}

When the user asks about their finances, use the available tools to query specific data and provide helpful, concise answers suitable for WhatsApp (keep responses relatively short and scannable).

Key guidelines:
- Receivables = money owed TO the customer (sales, income)
- Payables = money the customer owes (purchases, expenses)
- Format currency amounts clearly
- Highlight overdue items when relevant
- Keep responses concise and formatted for mobile reading
- Use emojis sparingly for emphasis (💰 📊 ⚠️ ✅)
"""

    def _get_tools(self) -> List[Dict]:
        """Define tools for the LLM to query financial data."""
        return [
            {
                "name": "get_receivables_summary",
                "description": "Get a summary of all receivables (money owed to the customer from sales/invoices)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_overdue_only": {
                            "type": "boolean",
                            "description": "Only include overdue receivables"
                        },
                        "include_outstanding_only": {
                            "type": "boolean",
                            "description": "Only include receivables with outstanding balance"
                        }
                    }
                }
            },
            {
                "name": "get_payables_summary",
                "description": "Get a summary of all payables (money the customer owes from purchases/bills)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_outstanding_only": {
                            "type": "boolean",
                            "description": "Only include payables with outstanding balance"
                        }
                    }
                }
            },
            {
                "name": "get_invoice_details",
                "description": "Get detailed information about a specific invoice by invoice number",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "invoice_number": {
                            "type": "string",
                            "description": "The invoice number to look up"
                        },
                        "invoice_type": {
                            "type": "string",
                            "enum": ["receivable", "payable"],
                            "description": "Whether this is a receivable or payable"
                        }
                    },
                    "required": ["invoice_number"]
                }
            }
        ]

    def _process_response(self, response, financial_context: Dict) -> Dict:
        """Process the LLM response and execute any tool calls."""
        result_text = ""
        result_data = {}

        for block in response.content:
            if block.type == "text":
                result_text += block.text

            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input

                # Execute the tool
                tool_result = self._execute_tool(tool_name, tool_input, financial_context)
                result_data[tool_name] = tool_result

                # For simple queries, include the data directly in the text
                if not result_text:
                    result_text = self._format_tool_result(tool_name, tool_result)

        return {
            'text': result_text.strip(),
            'data': result_data
        }

    def _execute_tool(self, tool_name: str, tool_input: Dict, financial_context: Dict) -> Dict:
        """Execute a tool call and return results."""
        if tool_name == "get_receivables_summary":
            include_overdue = tool_input.get('include_overdue_only', False)
            include_outstanding = tool_input.get('include_outstanding_only', False)

            if include_overdue:
                return financial_context['receivables']['overdue']
            elif include_outstanding:
                return financial_context['receivables']['outstanding']
            else:
                return financial_context['receivables']

        elif tool_name == "get_payables_summary":
            include_outstanding = tool_input.get('include_outstanding_only', False)

            if include_outstanding:
                return financial_context['payables']['outstanding']
            else:
                return financial_context['payables']

        elif tool_name == "get_invoice_details":
            invoice_number = tool_input.get('invoice_number')
            invoice_type = tool_input.get('invoice_type', 'receivable')

            if invoice_type == 'receivable':
                invoice = Receivable.objects.filter(
                    customer_id__in=[c.id for c in self.linked_customers],
                    invoice_number=invoice_number
                ).first()
            else:
                invoice = Payable.objects.filter(
                    vendor__name__in=[c.name for c in self.linked_customers],
                    invoice_number=invoice_number
                ).first()

            if not invoice:
                return {'error': 'Invoice not found'}

            return {
                'invoice_number': invoice.invoice_number,
                'date': invoice.invoice_date.isoformat(),
                'due_date': invoice.due_date.isoformat(),
                'amount_gross': float(invoice.amount_gross),
                'amount_paid': float(invoice.amount_paid),
                'amount_outstanding': float(invoice.amount_outstanding),
                'status': invoice.status,
                'currency': invoice.currency,
                'source': invoice.source_system,
            }

        return {}

    def _format_tool_result(self, tool_name: str, tool_result: Dict) -> str:
        """Format tool results as readable text."""
        # This is a fallback; normally Claude will format the response
        return f"Tool {tool_name} executed successfully."
