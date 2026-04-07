import os
import base64
import requests
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MpesaGateway:
    SANDBOX_TEST_NUMBERS = [ "254759903964"]  # String amounts that work in sandbox
    PRODUCTION_SHORTCODE_LENGTH = 6

    def __init__(self):
        self.environment = os.getenv('MPESA_ENVIRONMENT', 'sandbox').lower()
        self._validate_environment()
        self._initialize_endpoints()
        self._load_credentials()
        self.timeout = 30
        self.access_token = None
        self.token_expiry = None

    def _validate_environment(self):
        if self.environment not in ['sandbox', 'production']:
            raise ValueError("MPESA_ENVIRONMENT must be 'sandbox' or 'production'")

    def _initialize_endpoints(self):
        self.base_url = (
            "https://sandbox.safaricom.co.ke"
            if self.environment == 'sandbox'
            else "https://api.safaricom.co.ke"
        )
        self.token_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        self.stk_push_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        self.query_url = f"{self.base_url}/mpesa/stkpushquery/v1/query"

    def _load_credentials(self):
        self.consumer_key = os.getenv('MPESA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('MPESA_CONSUMER_SECRET')

        if not all([self.consumer_key, self.consumer_secret]):
            raise ValueError("Missing M-Pesa API credentials")

        if self.environment == 'sandbox':
            self.business_shortcode = '174379'
            self.passkey = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
        else:
            self.business_shortcode = os.getenv('MPESA_BUSINESS_SHORTCODE')
            self.passkey = os.getenv('MPESA_PASSKEY')
            if not all([self.business_shortcode, self.passkey]):
                raise ValueError("Missing production credentials")

        self.callback_url = os.getenv('MPESA_CALLBACK_URL')
        if not self.callback_url:
            raise ValueError("Callback URL is required")

    def get_access_token(self):
        """Get OAuth access token with enhanced error handling"""
        if self._is_token_valid():
            return self.access_token

        try:
            auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
            response = requests.get(self.token_url, auth=auth, timeout=self.timeout)

            if response.status_code == 401:
                error_data = response.json()
                error_msg = error_data.get('error_description', 'Invalid credentials')
                logger.error(f"Authentication failed: {error_msg}")
                raise Exception(f"Authentication failed: {error_msg}")

            response.raise_for_status()
            token_data = response.json()

            if 'access_token' not in token_data:
                logger.error("Invalid token response format")
                raise Exception("Invalid response from M-Pesa API")

            self.access_token = token_data['access_token']
            self.token_expiry = datetime.now() + timedelta(seconds=3300)
            return self.access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Token request failed: {str(e)}")
            raise Exception("Could not connect to M-Pesa API. Please check your internet connection.")
        except Exception as e:
            logger.error(f"Unexpected error during token generation: {str(e)}")
            raise Exception("Failed to generate access token")

    def _is_token_valid(self):
        return (
                self.access_token is not None and
                self.token_expiry is not None and
                datetime.now() < self.token_expiry
        )

    def check_api_status(self):
        """Return True when token generation succeeds, else False."""
        try:
            return bool(self.get_access_token())
        except Exception as exc:
            logger.error(f"M-Pesa API status check failed: {exc}")
            return False

    def stk_push(self, phone_number, amount, account_reference, transaction_desc="Payment"):
        """Initiate STK Push safely for sandbox and production."""
        try:
            # ===== Handle sandbox environment =====
            if self.environment == 'sandbox':
                phone = self._format_phone_number(phone_number)
                logger.info(f"Using sandbox mode with entered number: {phone}")

                # Map custom allowed amounts -> sandbox allowed values
                sandbox_amount_map = {
                    1: 1,
                    5: 10,  # sandbox doesn’t allow 5, so test with 10
                    15: 100  # sandbox doesn’t allow 15, so test with 100
                }

                if amount not in sandbox_amount_map:
                    logger.warning(
                        f"Sandbox only supports amounts 1, 5, 15 in your app. Defaulting to 1 instead of {amount}")
                    amount = 1

                formatted_amount = sandbox_amount_map[amount]
            else:
                # Production allows real amounts
                phone = self._format_phone_number(phone_number)
                if float(amount) <= 0:
                    raise ValueError("Amount must be positive")
                formatted_amount = float(amount)

            # ===== Generate security password =====
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
            ).decode()

            # ===== Build payload =====
            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": formatted_amount,
                "PartyA": phone,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference[:12],
                "TransactionDesc": transaction_desc[:13]
            }

            headers = {
                "Authorization": f"Bearer {self.get_access_token()}",
                "Content-Type": "application/json"
            }

            logger.info(f"Initiating payment request for {phone}, amount: KES {formatted_amount}")

            # ===== Send request =====
            response = requests.post(
                self.stk_push_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            # ===== Handle response =====
            data = response.json()

            if response.status_code >= 400:
                logger.error(f"API Error Response: {data}")
                if self.environment == 'sandbox' and data.get('errorCode') == '400.002.02':
                    raise Exception("Sandbox amount error. Reset your test environment.")
                raise Exception(data.get('errorMessage', 'Payment request failed'))

            if data.get('ResponseCode') != "0":
                raise Exception(data.get('errorMessage', data.get('ResponseDescription', 'Payment failed')))

            return {
                'success': True,
                'checkout_request_id': data['CheckoutRequestID'],
                'merchant_request_id': data['MerchantRequestID'],
                'customer_message': data.get('CustomerMessage', 'Check your phone to complete payment'),
                'response_description': data.get('ResponseDescription', 'Request processed successfully')
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during STK push: {str(e)}")
            raise Exception("Payment request failed. Check your internet connection.")
        except Exception as e:
            logger.error(f"STK Push failed: {str(e)}")
            raise Exception(f"Payment initiation failed: {str(e)}")

    def query_stk_status(self, checkout_request_id):
        """Query the status of a previously initiated STK push."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
            ).decode()

            payload = {
                "BusinessShortCode": self.business_shortcode,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id,
            }

            headers = {
                "Authorization": f"Bearer {self.get_access_token()}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                self.query_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            data = response.json()

            if response.status_code >= 400:
                logger.error(f"STK query API error: {data}")
                raise Exception(data.get('errorMessage', 'Payment status query failed'))

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during STK query: {str(e)}")
            raise Exception("Payment status query failed. Check your internet connection.")
        except Exception as e:
            logger.error(f"STK query failed: {str(e)}")
            raise Exception(f"Payment status query failed: {str(e)}")

    def _format_phone_number(self, phone_number):
        """Format phone number to M-Pesa standard (254...)"""
        phone = phone_number.strip().replace("+", "").replace(" ", "")

        if phone.startswith('0') and len(phone) == 10:
            return f"254{phone[1:]}"
        elif phone.startswith('254') and len(phone) == 12:
            return phone

        raise ValueError("Invalid Kenyan phone number format. Use 07... or 254...")


if __name__ == "__main__":
    try:
        print("=== M-Pesa STK Push Tester ===")

        mpesa = MpesaGateway()

        # Test with sandbox parameters
        result = mpesa.stk_push(
            phone_number="254759903964",  # Will be overridden with first test number
            amount=1,  # Must be 1, 10, or 100 for sandbox
            account_reference="TEST123",
            transaction_desc="Test Payment"
        )

        print("\n✅ STK Push initiated successfully!")
        print(f"Checkout Request ID: {result['checkout_request_id']}")
        print(f"Merchant Request ID: {result['merchant_request_id']}")
        print(f"Message: {result['customer_message']}")
        print(f"Description: {result['response_description']}")
        print("\nCheck your phone to complete the payment")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting Tips:")
        print("1. For sandbox, use exactly 1, 10, or 100 as the amount")
        print("2. Verify your .env file has correct sandbox credentials")
        print("3. Ensure your callback URL is accessible")
        print("4. Try resetting your sandbox test environment")
        print("5. Contact Safaricom API support if issue persists")