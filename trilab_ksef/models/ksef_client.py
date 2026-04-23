import base64
import hashlib
import io
import json
import logging
import secrets
import time
import zipfile
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, IntEnum, StrEnum, auto
from pathlib import Path
from typing import Any, Literal, TypedDict, cast
from urllib.parse import urljoin, urlparse

import dateutil.parser
import pytz
import requests
from cryptography import exceptions as crypto_exceptions, x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding as sym_padding, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_logger = logging.getLogger(__name__)

TIMEOUT_SECS = 5
AUTH_STATUS_CHECK_ATTEMPTS = 5
AUTH_STATUS_CHECK_DELAY_SECS = 1
MAX_TRIES = 3
FALLBACK_RETRY_AFTER_SECS = 5


class KsefClientError(Exception):
    """Base exception for all KSeF API client errors."""


class KsefInvalidKeyError(KsefClientError):
    """Raised when a public key is not a valid RSA key."""

    key_type: str

    def __init__(self, key_type: str) -> None:
        self.key_type = key_type
        super().__init__(f'{key_type.capitalize()} public key is not an RSA key')


class KsefNetworkError(KsefClientError):
    """Base exception for network and HTTP communication errors."""


class KsefRequestError(KsefNetworkError):
    """Raised when an HTTP request fails due to network issues."""

    endpoint: str
    cause: Exception | None

    def __init__(self, endpoint: str, cause: Exception | None = None) -> None:
        self.endpoint = endpoint
        self.cause = cause
        super().__init__(f'Request to {endpoint!r} failed: {cause}')


class KsefTimeoutError(KsefNetworkError):
    """Raised when an HTTP request times out."""


class KsefHttpStatusError(KsefNetworkError):
    """Raised when API returns an unexpected HTTP status code."""

    endpoint: str
    status_code: int
    response_text: str
    expected_status: int

    def __init__(self, endpoint: str, status_code: int, response_text: str, expected_status: int) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_text = response_text
        self.expected_status = expected_status
        super().__init__(
            f'Unexpected status {status_code} (expected {expected_status}) from {endpoint!r}: {response_text}'
        )


class KsefRateLimitError(KsefNetworkError):
    endpoint: str
    attempts: int

    def __init__(self, endpoint: str, attempts: int) -> None:
        self.endpoint = endpoint
        self.attempts = attempts
        super().__init__(f'Rate limit exceeded for endpoint {endpoint!r} after {attempts} attempts')


class KsefAuthenticationError(KsefClientError):
    """Base exception for authentication-related errors."""


class KsefAuthenticationStatusError(KsefAuthenticationError):
    """Raised when authentication fails with an error status code."""

    status_code: int
    status_description: str

    def __init__(self, status_code: int, status_description: str) -> None:
        self.status_code = status_code
        self.status_description = status_description
        super().__init__(f'Authentication failed with status {status_code}: {status_description}')


class KsefSessionError(KsefClientError):
    """Base exception for session lifecycle errors."""


class KsefNotAuthenticatedError(KsefSessionError):
    """Raised when attempting an operation that requires authentication."""


class KsefNoActiveSessionError(KsefSessionError):
    """Raised when attempting an operation that requires an active interactive session."""


class KsefNoActiveBatchSessionError(KsefSessionError):
    """Raised when attempting an operation that requires an active batch import."""


class KsefBatchPartUploadError(KsefClientError):
    """Raised when batch part upload fails."""

    part_number: int
    status_code: int
    response_text: str

    def __init__(self, part_number: int, status_code: int, response_text: str) -> None:
        self.part_number = part_number
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(f'Part {part_number} upload failed ({status_code}): {response_text}')


class KsefEncryptionError(KsefClientError):
    """Base exception for encryption and decryption errors."""


class KsefInvoiceEncryptionError(KsefEncryptionError):
    """Raised when invoice encryption fails."""


class KsefCertificateVerificationUrlError(KsefClientError):
    """Raised when certificate verification URL generation fails."""


class KsefInvoiceBatchExportError(KsefClientError):
    """Raised when invoice batch export fails."""


class KsefInvoiceBatchExportMissingStateDataError(KsefInvoiceBatchExportError):
    """Raised when invoice batch export fails due to missing state data."""


class KsefInvoiceBatchExportStatusError(KsefInvoiceBatchExportError):
    """Raised when the invoice batch export status check fails."""

    status_code: int
    status_description: str

    def __init__(self, status_code: int, status_description: str) -> None:
        self.status_code = status_code
        self.status_description = status_description
        super().__init__(f'Invoice Batch Export failed with status {status_code}: {status_description}')


class InvoiceBatchExportPendingError(KsefInvoiceBatchExportError):
    """Raised when batch export is still pending and not ready for download."""

    reference_number: str
    status_code: int

    def __init__(self, reference_number: str, status_code: int) -> None:
        self.reference_number = reference_number
        self.status_code = status_code
        super().__init__(f'Batch export {reference_number} is still pending (status: {status_code})')


class FormCode(Enum):
    FA_2 = ('FA (2)', '1-0E', 'FA')
    FA_3 = ('FA (3)', '1-0E', 'FA')
    PEF_3 = ('PEF (3)', '2-1', 'PEF')
    PEF_KOR_3 = ('PEF KOR (3)', '2-1', 'PEF')


class ContextIdentifierType(StrEnum):
    NIP = 'Nip'
    INTERNAL_ID = 'InternalId'
    NIP_VAT_UE = 'NipVatUe'
    PEPPOL_ID = 'PeppolId'


class InvoiceBatchExportStatus(Enum):
    PENDING = auto()
    COMPLETED = auto()


class KsefStatusCode(IntEnum):
    PENDING = 100
    OK = 200


@dataclass(kw_only=True, frozen=True)
class AuthenticateKsefTokenResponse:
    access_token: str
    access_token_valid_until: datetime
    refresh_token: str
    refresh_token_valid_until: datetime

    def to_json(self) -> str:
        return json.dumps(
            {
                'access_token': self.access_token,
                'access_token_valid_until': int(self.access_token_valid_until.timestamp()),
                'refresh_token': self.refresh_token,
                'refresh_token_valid_until': int(self.refresh_token_valid_until.timestamp()),
            }
        )


@dataclass(kw_only=True, frozen=True)
class InvoiceStatusInfo:
    code: int
    description: str
    details: list[str] | None = None
    extensions: dict[str, str | None] | None = None


@dataclass(kw_only=True, frozen=True)
class SessionInvoiceStatusResponse:
    ordinal_number: int
    reference_number: str
    invoice_hash: str
    invoicing_date: datetime
    status: InvoiceStatusInfo
    invoice_number: str | None = None
    ksef_number: str | None = None
    invoice_file_name: str | None = None
    acquisition_date: datetime | None = None
    permanent_storage_date: datetime | None = None
    upo_download_url: str | None = None
    upo_download_url_expiration_date: datetime | None = None
    invoicing_mode: str | None = None


class InvoiceBatchExportState(TypedDict):
    reference_number: str
    iv_b64: str
    key_b64: str


@dataclass(kw_only=True, frozen=True)
class InvoiceBatchExportResult:
    permanent_storage_hwm_date: datetime
    is_truncated: bool
    invoices: Generator[tuple[str, str], None, None]  # (filename, xml_content)


class InvoiceBatchExportStatusResult(TypedDict):
    status: InvoiceBatchExportStatus
    status_code: int
    status_description: str
    data: dict[str, Any] | None


class BatchFileMetadata(TypedDict):
    file_size: int
    file_hash_sha256_b64: str


class BatchPartMetadata(TypedDict):
    ordinal_number: int
    file_name: str
    file_size: int
    file_hash_sha256_b64: str
    encrypted_data: bytes


class SessionInvoicesListResponse(TypedDict):
    continuation_token: str | None
    invoices: list[SessionInvoiceStatusResponse]


class KsefClient:
    """KSeF V2 API Client"""

    def __init__(
        self,
        base_url: str,
        ksef_token: str,
        nip_identifier: str,
        public_asymmetric_key_path: str | Path,
        public_symmetric_key_path: str | Path,
    ) -> None:
        self.base_url: str = self._validate_base_url(base_url)
        self.public_asymmetric_key_path: Path = self._validate_public_key_path(public_asymmetric_key_path)
        self.public_symmetric_key_path: Path = self._validate_public_key_path(public_symmetric_key_path)

        self.ksef_token: str = ksef_token
        self.nip_identifier: str = nip_identifier
        self._session: requests.Session = requests.Session()

        self.access_token: str | None = None

        self.session_key: bytes | None = None
        self.session_iv: bytes | None = None
        self.session_reference: str | None = None

        self.invoice_batch_export_reference: str | None = None
        self.invoice_batch_export_iv: bytes | None = None
        self.invoice_batch_export_key: bytes | None = None

        self.invoice_batch_import_reference: str | None = None
        self.invoice_batch_import_key: bytes | None = None
        self.invoice_batch_import_iv: bytes | None = None

    @staticmethod
    def _validate_base_url(base_url: str) -> str:
        if base_url.endswith('/'):
            return base_url
        _logger.warning('Provided `base_url` without trailing URL slash! Fixing...')
        return f'{base_url}/'

    @staticmethod
    def _validate_public_key_path(public_key_path: str | Path) -> Path:
        if isinstance(public_key_path, str):
            public_key_path = Path(public_key_path)

        if not public_key_path.is_file():
            raise KsefClientError(f'Invalid `public_key_path` {public_key_path}')

        return public_key_path

    @staticmethod
    def parse_datetime(dt_str: str) -> datetime:
        return dateutil.parser.isoparse(dt_str)

    @classmethod
    def _parse_invoice_status_response(cls, data: dict[str, Any]) -> SessionInvoiceStatusResponse:
        status_data = data['status']
        return SessionInvoiceStatusResponse(
            ordinal_number=data['ordinalNumber'],
            reference_number=data['referenceNumber'],
            invoice_hash=data['invoiceHash'],
            invoicing_date=cls.parse_datetime(data['invoicingDate']),
            status=InvoiceStatusInfo(
                code=status_data['code'],
                description=status_data['description'],
                details=status_data.get('details'),
                extensions=status_data.get('extensions'),
            ),
            invoice_number=data.get('invoiceNumber'),
            ksef_number=data.get('ksefNumber'),
            invoice_file_name=data.get('invoiceFileName'),
            acquisition_date=cls.parse_datetime(data['acquisitionDate']) if data.get('acquisitionDate') else None,
            permanent_storage_date=(
                cls.parse_datetime(data['permanentStorageDate']) if data.get('permanentStorageDate') else None
            ),
            upo_download_url=data.get('upoDownloadUrl'),
            upo_download_url_expiration_date=(
                cls.parse_datetime(data['upoDownloadUrlExpirationDate'])
                if data.get('upoDownloadUrlExpirationDate')
                else None
            ),
            invoicing_mode=data.get('invoicingMode'),
        )

    def _ensure_access_token(self) -> None:
        if self.access_token is None:
            _logger.error('Not authenticated. Call authenticate_ksef_token() first.')
            raise KsefNotAuthenticatedError

    def _ensure_session_data(self) -> None:
        if self.session_key is None or self.session_iv is None or self.session_reference is None:
            _logger.error('No active session. Call open_interactive_session() first.')
            raise KsefNoActiveSessionError

    def _ensure_invoice_batch_export_data(self) -> None:
        if (
            self.invoice_batch_export_reference is None
            or self.invoice_batch_export_iv is None
            or self.invoice_batch_export_key is None
        ):
            _logger.error('No active invoice batch export. Call start_batch_invoice_export() first.')
            raise KsefInvoiceBatchExportMissingStateDataError

    def _encrypt_invoice_aes(self, invoice_xml: bytes) -> tuple[bytes, str, int]:
        """Encrypt invoice XML using AES-256-CBC with session keys.

        Args:
            invoice_xml: Raw invoice XML content as bytes.

        Returns:
            Tuple of (encrypted_bytes, encrypted_hash_base64, encrypted_size).

        Raises:
            KsefInvoiceEncryptionError: If encryption fails or session keys are invalid.
        """
        if self.session_key is None or self.session_iv is None:
            raise KsefNoActiveSessionError('No active session.')

        try:
            # PKCS7 padding for AES block cipher (128-bit blocks)
            padder = sym_padding.PKCS7(128).padder()
            padded_data = padder.update(invoice_xml) + padder.finalize()

            # Create AES-256-CBC cipher
            cipher = Cipher(algorithms.AES(self.session_key), modes.CBC(self.session_iv), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

            # Calculate hash and size of encrypted data
            encrypted_hash = base64.b64encode(hashlib.sha256(encrypted_data).digest()).decode()
            encrypted_size = len(encrypted_data)

            return encrypted_data, encrypted_hash, encrypted_size
        except (TypeError, ValueError) as error:
            raise KsefInvoiceEncryptionError from error

    @staticmethod
    def _calculate_file_metadata(data: bytes) -> BatchFileMetadata:
        file_hash = base64.b64encode(hashlib.sha256(data).digest()).decode()

        return {
            'file_size': len(data),
            'file_hash_sha256_b64': file_hash,
        }

    @staticmethod
    def _split_into_parts(data: bytes, max_part_size: int) -> list[bytes]:
        if len(data) <= max_part_size:
            return [data]

        parts: list[bytes] = []
        offset = 0
        while offset < len(data):
            chunk_size = min(max_part_size, len(data) - offset)
            parts.append(data[offset : offset + chunk_size])
            offset += chunk_size

        return parts

    @staticmethod
    def _encrypt_part_aes(data: bytes, key: bytes, iv: bytes) -> bytes:
        try:
            padder = sym_padding.PKCS7(128).padder()
            padded_data = padder.update(data) + padder.finalize()

            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            encryptor = cipher.encryptor()
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

            return encrypted_data
        except (TypeError, ValueError) as error:
            raise KsefEncryptionError('AES encryption failed') from error

    @staticmethod
    def _create_invoice_zip(invoices: Iterator[tuple[str, bytes]]) -> tuple[bytes, int]:
        zip_buffer = io.BytesIO()
        invoice_count = 0

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_name, content in invoices:
                if not content:
                    raise KsefClientError(f'Invoice {file_name} has empty content')
                zf.writestr(file_name, content)
                invoice_count += 1

        if invoice_count == 0:
            raise KsefClientError('Invoice zip cannot be empty')

        return zip_buffer.getvalue(), invoice_count

    def _prepare_batch_parts(
        self, zip_bytes: bytes, key: bytes, iv: bytes, max_part_size: int
    ) -> list[BatchPartMetadata]:
        raw_parts = self._split_into_parts(zip_bytes, max_part_size)

        _logger.debug('Split ZIP (%d bytes) into %d parts', len(zip_bytes), len(raw_parts))

        encrypted_parts: list[BatchPartMetadata] = []
        for idx, part_data in enumerate(raw_parts, start=1):
            encrypted_data = self._encrypt_part_aes(part_data, key, iv)

            encrypted_hash = base64.b64encode(hashlib.sha256(encrypted_data).digest()).decode()

            _logger.debug('Part %d: %d bytes -> %d encrypted bytes', idx, len(part_data), len(encrypted_data))

            encrypted_parts.append(
                {
                    'ordinal_number': idx,
                    'file_name': f'part_{idx}.zip.aes',
                    'file_size': len(encrypted_data),
                    'file_hash_sha256_b64': encrypted_hash,
                    'encrypted_data': encrypted_data,
                }
            )

        return encrypted_parts

    def _call_api(
        self, endpoint: str, *, method: str, expected_status: int = requests.codes.ok, **kwargs: Any
    ) -> requests.Response:
        _logger.debug(f'Calling API: {method.upper()} {endpoint}')

        counter = 0
        while counter < MAX_TRIES:
            try:
                if self.access_token is not None:
                    kwargs['headers'] = kwargs.get('headers', {}) | {'Authorization': f'Bearer {self.access_token}'}

                response: requests.Response = getattr(self._session, method.lower())(
                    url=urljoin(self.base_url, endpoint), timeout=TIMEOUT_SECS, **kwargs
                )

            except requests.RequestException as err:
                raise KsefRequestError(endpoint, err) from err

            _logger.debug(f'Response status: {response.status_code} for {endpoint}')

            if response.status_code == requests.codes.too_many_requests:
                retry_after = int(response.headers.get('Retry-After', FALLBACK_RETRY_AFTER_SECS))

                _logger.info(
                    f'Rate limit hit on {endpoint} (attempt {counter + 1}/{MAX_TRIES}), retrying after {retry_after}s'
                )

                time.sleep(retry_after)
                counter += 1
                continue

            if response.status_code != expected_status:
                raise KsefHttpStatusError(endpoint, response.status_code, response.text, expected_status)

            return response

        _logger.error(f'Rate limit exceeded for {endpoint} after {MAX_TRIES} attempts')
        raise KsefRateLimitError(endpoint, MAX_TRIES)

    @staticmethod
    def _decode_certificate(certificate: str) -> str:
        cert_der = base64.b64decode(certificate)
        cert = x509.load_der_x509_certificate(cert_der)
        public_key = cert.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()

    def _load_symmetric_public_key(self) -> RSAPublicKey:
        key = serialization.load_pem_public_key(self.public_symmetric_key_path.read_bytes(), backend=default_backend())
        if not isinstance(key, RSAPublicKey):
            raise KsefInvalidKeyError('symmetric')
        return key

    def _load_asymmetric_public_key(self) -> RSAPublicKey:
        key = serialization.load_pem_public_key(self.public_asymmetric_key_path.read_bytes(), backend=default_backend())
        if not isinstance(key, RSAPublicKey):
            raise KsefInvalidKeyError('asymmetric')
        return key

    def get_public_keys(self) -> tuple[str, str]:
        """Retrieve current valid public keys from KSeF API.

        Returns:
            A tuple of (symmetric_public_key_pem, asymmetric_public_key_pem) as PEM-encoded strings.

        Raises:
            KsefApiClientError: If an API call fails or required certificates are not found.
        """
        response = self._call_api(
            'security/public-key-certificates',
            method='get',
        )
        certs_data = response.json()

        symmetric_certificate = None
        symmetric_certificate_valid_to = None
        token_certificate = None
        token_certificate_valid_to = None

        for cert_info in certs_data:
            usage = cert_info['usage']
            valid_from = datetime.fromisoformat(cert_info['validFrom'])
            valid_to = datetime.fromisoformat(cert_info['validTo'])

            if not (valid_from <= datetime.now(tz=pytz.UTC) <= valid_to):
                continue

            if 'SymmetricKeyEncryption' in usage:
                if symmetric_certificate_valid_to is not None and valid_to < symmetric_certificate_valid_to:
                    continue

                symmetric_certificate = cert_info['certificate']
                symmetric_certificate_valid_to = valid_to

            if 'KsefTokenEncryption' in usage:
                if token_certificate_valid_to is not None and valid_to < token_certificate_valid_to:
                    continue

                token_certificate = cert_info['certificate']
                token_certificate_valid_to = valid_to

        if not (symmetric_certificate and token_certificate):
            raise KsefClientError(
                "Could not find all required KSeF public keys ('SymmetricKeyEncryption' and 'KsefTokenEncryption')."
            )

        return self._decode_certificate(symmetric_certificate), self._decode_certificate(token_certificate)

    def get_challenge(self) -> tuple[str, datetime]:
        """Request authentication challenge from KSeF API.

        Returns:
            A tuple of (challenge_string, challenge_timestamp).

        Raises:
            KsefApiClientError: If API call fails.
        """
        try:
            challenge_data = self._call_api('auth/challenge', method='post').json()

        except KsefHttpStatusError as error:
            raise KsefAuthenticationStatusError(error.status_code, error.response_text) from error

        return challenge_data['challenge'], self.parse_datetime(challenge_data['timestamp'])

    def _encrypt_ksef_token(self, challenge_timestamp: datetime) -> str:
        timestamp_ms = int(challenge_timestamp.timestamp() * 1000)

        public_key = self._load_asymmetric_public_key()
        encrypted = public_key.encrypt(
            f'{self.ksef_token}|{timestamp_ms}'.encode(),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )

        return base64.b64encode(encrypted).decode()

    def _authenticate_ksef_token(self) -> dict[str, Any]:
        challenge, challenge_timestamp = self.get_challenge()

        try:
            response = self._call_api(
                'auth/ksef-token',
                method='post',
                expected_status=requests.codes.accepted,
                json={
                    'Challenge': challenge,
                    'ContextIdentifier': {'Type': 'Nip', 'Value': self.nip_identifier},
                    'EncryptedToken': self._encrypt_ksef_token(challenge_timestamp),
                },
            )

        except KsefHttpStatusError as error:
            raise KsefAuthenticationStatusError(error.status_code, error.response_text) from error

        return response.json()

    def get_authentication_status(self, reference_number: str, temp_token: str) -> dict[str, Any]:
        try:
            response = self._call_api(
                f'auth/{reference_number}',
                method='get',
                headers={'Authorization': f'Bearer {temp_token}'},
            )

        except KsefHttpStatusError as error:
            raise KsefAuthenticationStatusError(error.status_code, error.response_text) from error

        return response.json()

    def redeem_token(self, temp_token: str) -> dict[str, Any]:
        try:
            response = self._call_api(
                'auth/token/redeem',
                method='post',
                headers={'Authorization': f'Bearer {temp_token}'},
            )

        except KsefHttpStatusError as error:
            raise KsefAuthenticationStatusError(error.status_code, error.response_text) from error

        return response.json()

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        try:
            response = self._call_api(
                'auth/token/refresh',
                method='post',
                headers={'Authorization': f'Bearer {refresh_token}'},
            )

        except KsefHttpStatusError as error:
            raise KsefAuthenticationStatusError(error.status_code, error.response_text) from error

        return response.json()

    def authenticate_ksef_token(self) -> AuthenticateKsefTokenResponse:
        """Authenticate with KSeF using an encrypted token and get access/refresh tokens.

        This method performs multistep authentication:
        1. Initiates authentication with an encrypted KSeF token
        2. Polls authentication status until confirmed or failed
        3. Redeems temporary token for access and refresh tokens

        Returns:
            AuthenticateKsefTokenResponse containing access token, refresh token, and their expiry times.

        Raises:
            KsefAuthenticationError: If authentication fails or times out.
            KsefApiClientError: If API calls fail.
        """
        _logger.info('Starting KSeF token authentication')
        init_response = self._authenticate_ksef_token()
        reference_number = init_response['referenceNumber']
        temp_token = init_response['authenticationToken']['token']

        _logger.debug('Authentication initiated with reference: %s', reference_number)

        for attempt in range(AUTH_STATUS_CHECK_ATTEMPTS):
            status_response = self.get_authentication_status(reference_number, temp_token)

            status_code = status_response['status']['code']
            status_description = status_response['status']['description']

            _logger.debug(
                'KSeF authentication status (attempt %d/%d): %s - %s',
                attempt + 1,
                AUTH_STATUS_CHECK_ATTEMPTS,
                status_code,
                status_description,
            )

            if status_code == KsefStatusCode.OK:
                break

            elif status_code == KsefStatusCode.PENDING:
                if attempt < AUTH_STATUS_CHECK_ATTEMPTS - 1:
                    _logger.debug('Waiting for KSeF authentication...')
                    time.sleep(AUTH_STATUS_CHECK_DELAY_SECS)

            else:
                raise KsefAuthenticationStatusError(status_code, status_description)
        else:
            raise KsefAuthenticationStatusError(-1, 'Too many status check attempts!')

        _logger.debug('Authentication confirmed, redeeming token')
        redeem_response = self.redeem_token(temp_token)

        _logger.info('Authentication successful')
        auth_response = AuthenticateKsefTokenResponse(
            access_token=redeem_response['accessToken']['token'],
            access_token_valid_until=self.parse_datetime(redeem_response['accessToken']['validUntil']),
            refresh_token=redeem_response['refreshToken']['token'],
            refresh_token_valid_until=self.parse_datetime(redeem_response['refreshToken']['validUntil']),
        )

        self.access_token = auth_response.access_token

        return auth_response

    def open_interactive_session(self, form_code: FormCode = FormCode.FA_3) -> tuple[str, datetime]:
        """Open an encrypted interactive session for invoice submission.

        Creates a new interactive session with KSeF API using AES encryption.
        Generates random encryption keys and securely transmits them to the server.
        Stores session context (keys, IV, reference) for subsequent invoice operations.

        Args:
            form_code: Invoice form type to use for this session. Defaults to FA_3.

        Returns:
            A tuple of (session_reference_number, session_valid_until_datetime).

        Raises:
            KsefApiClientError: If not authenticated or API call fails.
        """
        self._ensure_access_token()

        raw_key = secrets.token_bytes(32)
        raw_iv = secrets.token_bytes(16)

        public_key = self._load_symmetric_public_key()

        encrypted_key = public_key.encrypt(
            raw_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

        response_json = self._call_api(
            'sessions/online',
            method='post',
            expected_status=requests.codes.created,
            json={
                'formCode': {
                    'systemCode': form_code.value[0],
                    'schemaVersion': form_code.value[1],
                    'value': form_code.value[2],
                },
                'encryption': {
                    'encryptedSymmetricKey': base64.b64encode(encrypted_key).decode(),
                    'initializationVector': base64.b64encode(raw_iv).decode(),
                },
            },
        ).json()

        reference_number = response_json['referenceNumber']
        valid_until = self.parse_datetime(response_json['validUntil'])

        # Store session context for invoice encryption
        self.session_key = raw_key
        self.session_iv = raw_iv
        self.session_reference = reference_number

        _logger.info('Interactive session opened: %s (valid until %s)', reference_number, valid_until)
        return reference_number, valid_until

    def close_interactive_session(self) -> None:
        self._ensure_access_token()
        self._ensure_session_data()

        # Store reference before clearing for logging
        session_ref = self.session_reference

        _ = self._call_api(
            f'sessions/online/{session_ref}/close',
            method='post',
            expected_status=requests.codes.no_content,
        )

        self.session_key = None
        self.session_iv = None
        self.session_reference = None

        _logger.info('Interactive session closed: %s', session_ref)

    def send_invoice(self, ksef_invoice_xml: bytes) -> str:
        self._ensure_access_token()
        self._ensure_session_data()

        if not ksef_invoice_xml:
            raise KsefClientError('Invoice XML content cannot be empty')

        # Calculate the hash and size of the original invoice
        invoice_hash = base64.b64encode(hashlib.sha256(ksef_invoice_xml).digest()).decode()
        invoice_size = len(ksef_invoice_xml)

        # Encrypt invoice using AES-256-CBC with session keys
        encrypted_data, encrypted_hash, encrypted_size = self._encrypt_invoice_aes(ksef_invoice_xml)
        encrypted_content = base64.b64encode(encrypted_data).decode()

        _logger.debug(
            'Sending invoice to session %s (original: %d bytes, encrypted: %d bytes)',
            self.session_reference,
            invoice_size,
            encrypted_size,
        )

        response_json = self._call_api(
            f'sessions/online/{self.session_reference}/invoices',
            method='post',
            expected_status=requests.codes.accepted,
            json={
                'invoiceHash': invoice_hash,
                'invoiceSize': invoice_size,
                'encryptedInvoiceHash': encrypted_hash,
                'encryptedInvoiceSize': encrypted_size,
                'encryptedInvoiceContent': encrypted_content,
            },
        ).json()

        invoice_ref = response_json['referenceNumber']
        _logger.info('Invoice submitted successfully: %s', invoice_ref)
        return invoice_ref

    def get_session_status(self, session_reference: str | None = None) -> dict[str, Any]:
        self._ensure_access_token()

        session_reference = session_reference or self.session_reference

        if session_reference is None:
            raise KsefClientError('No session reference provided or active.')

        return self._call_api(
            f'sessions/{session_reference}',
            method='get',
        ).json()

    def get_session_invoices(
        self, session_reference: str | None = None, page_size: int = 1000, continuation_token: str | None = None
    ) -> SessionInvoicesListResponse:
        self._ensure_access_token()

        session_reference = session_reference or self.session_reference

        if session_reference is None:
            raise KsefClientError('No session reference provided or active.')

        headers = {}

        if continuation_token:
            headers['x-continuation-token'] = continuation_token

        response_json = self._call_api(
            f'sessions/{session_reference}/invoices',
            method='get',
            headers=headers,
            params={'pageSize': page_size},
        ).json()

        return {
            'continuation_token': response_json.get('continuationToken'),
            'invoices': [self._parse_invoice_status_response(inv) for inv in response_json.get('invoices', [])],
        }

    def get_all_session_invoices(self, session_reference: str | None = None) -> list[SessionInvoiceStatusResponse]:
        invoices = []
        continuation_token: str | None = None

        while True:
            response = self.get_session_invoices(
                session_reference=session_reference,
                continuation_token=continuation_token,
            )

            invoices.extend(response['invoices'])

            continuation_token = response['continuation_token']

            if not continuation_token:
                break

        return invoices

    def get_session_invoice_status(
        self, invoice_reference: str, session_reference: str | None = None
    ) -> SessionInvoiceStatusResponse:
        self._ensure_access_token()

        session_reference = session_reference or self.session_reference

        if session_reference is None:
            raise KsefClientError('No session reference provided or active.')

        response_json = self._call_api(
            f'sessions/{session_reference}/invoices/{invoice_reference}',
            method='get',
        ).json()

        return self._parse_invoice_status_response(response_json)

    def get_session_invoice_upo(self, invoice_reference: str, session_reference: str | None = None) -> str:
        """Download invoice UPO XML file."""
        self._ensure_access_token()

        session_reference = session_reference or self.session_reference

        if session_reference is None:
            raise KsefClientError('No session reference provided or active.')

        return self._call_api(
            f'sessions/{session_reference}/invoices/{invoice_reference}/upo',
            method='get',
        ).text

    def get_invoice(self, invoice_reference: str) -> str:
        """Download the invoice XML file by KSEF reference."""
        self._ensure_access_token()

        return self._call_api(
            f'invoices/ksef/{invoice_reference}',
            method='get',
        ).text

    def dump_invoice_batch_export_state(self) -> InvoiceBatchExportState:
        """Dump the current invoice batch export state."""
        self._ensure_invoice_batch_export_data()

        assert self.invoice_batch_export_reference is not None
        assert self.invoice_batch_export_iv is not None
        assert self.invoice_batch_export_key is not None

        return {
            'reference_number': self.invoice_batch_export_reference,
            'iv_b64': base64.b64encode(self.invoice_batch_export_iv).decode(),
            'key_b64': base64.b64encode(self.invoice_batch_export_key).decode(),
        }

    def load_invoice_batch_export_state(self, state: InvoiceBatchExportState) -> None:
        """Load invoice batch export state from a previously dumped state."""

        self.invoice_batch_export_reference = state['reference_number']
        self.invoice_batch_export_iv = base64.b64decode(state['iv_b64'])
        self.invoice_batch_export_key = base64.b64decode(state['key_b64'])

    def start_invoice_batch_export(
        self,
        date_from: datetime,
        date_to: datetime | None = None,
        subject_type: Literal['Subject1', 'Subject2', 'Subject3', 'SubjectAuthorized'] = 'Subject2',
        **filters: Any,
    ) -> str:
        self._ensure_access_token()

        raw_key = secrets.token_bytes(32)
        raw_iv = secrets.token_bytes(16)

        public_key = self._load_symmetric_public_key()

        encrypted_key = public_key.encrypt(
            raw_key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )

        if date_from.tzinfo is None:
            date_from = date_from.astimezone(pytz.UTC)

        if date_to is not None and date_to.tzinfo is None:
            date_to = date_to.astimezone(pytz.UTC)

        response_json = self._call_api(
            'invoices/exports',
            method='post',
            expected_status=requests.codes.created,
            json={
                'encryption': {
                    'encryptedSymmetricKey': base64.b64encode(encrypted_key).decode(),
                    'initializationVector': base64.b64encode(raw_iv).decode(),
                },
                'filters': {
                    'subjectType': subject_type,
                    'dateRange': {
                        'dateType': 'PermanentStorage',
                        'from': date_from.isoformat(),
                        'to': date_to.isoformat() if date_to else None,
                        'restrictToPermanentStorageHwmDate': True,
                    },
                }
                | filters,
            },
        ).json()

        reference_number = response_json['referenceNumber']

        self.invoice_batch_export_reference = reference_number
        self.invoice_batch_export_key = raw_key
        self.invoice_batch_export_iv = raw_iv

        _logger.info(
            'Batch invoice export started: %s (PermanentStorage: %s -> %s)',
            reference_number,
            date_from.isoformat(),
            date_to.isoformat() if date_to else 'now',
        )
        return reference_number

    def _get_invoice_batch_export_status(self, reference_number: str) -> InvoiceBatchExportStatusResult:
        self._ensure_access_token()

        response_json = self._call_api(
            f'invoices/exports/{reference_number}',
            method='get',
        ).json()

        status_code = response_json['status']['code']
        status_description = response_json['status']['description']

        if status_code < KsefStatusCode.OK:
            _logger.debug('Batch invoice export status in progress: %s', reference_number)
            return {
                'status': InvoiceBatchExportStatus.PENDING,
                'status_code': status_code,
                'status_description': status_description,
                'data': None,
            }
        elif status_code > KsefStatusCode.OK:
            raise KsefInvoiceBatchExportStatusError(status_code, status_description)

        _logger.info('Batch invoice export completed: %s', reference_number)
        return {
            'status': InvoiceBatchExportStatus.COMPLETED,
            'status_code': status_code,
            'status_description': status_description,
            'data': response_json,
        }

    def _download_all_invoice_parts(self, parts: list[dict[str, Any]]) -> Generator[tuple[str, str], None, None]:
        for part in parts:
            yield from self._download_and_decrypt_part(part)

    def download_invoice_batch_export(self) -> InvoiceBatchExportResult | None:
        self._ensure_invoice_batch_export_data()
        result = self._get_invoice_batch_export_status(cast('str', self.invoice_batch_export_reference))

        if result['status'] == InvoiceBatchExportStatus.PENDING:
            _logger.debug('Export not ready yet: %s', self.invoice_batch_export_reference)
            raise InvoiceBatchExportPendingError(
                cast('str', self.invoice_batch_export_reference), result['status_code']
            )

        response_data = result['data']
        if response_data is None:
            _logger.warning('No response data available: %s', self.invoice_batch_export_reference)
            return None

        parts = response_data.get('package', {}).get('parts', [])

        if not parts:
            _logger.warning('No invoice parts found in export response: %s', self.invoice_batch_export_reference)
            return None

        return InvoiceBatchExportResult(
            permanent_storage_hwm_date=self.parse_datetime(response_data['package']['permanentStorageHwmDate']),
            is_truncated=response_data['package']['isTruncated'],
            invoices=self._download_all_invoice_parts(parts),
        )

    def _ensure_invoice_batch_import_data(self) -> None:
        if (
            self.invoice_batch_import_key is None
            or self.invoice_batch_import_iv is None
            or self.invoice_batch_import_reference is None
        ):
            _logger.error('No active batch import data')
            raise KsefNoActiveBatchSessionError

    def _open_invoice_batch_import(
        self,
        form_code: FormCode,
        zip_metadata: BatchFileMetadata,
        parts: list[BatchPartMetadata],
        encrypted_key: bytes,
        iv: bytes,
    ) -> dict[str, Any]:
        payload = {
            'formCode': {
                'systemCode': form_code.value[0],
                'schemaVersion': form_code.value[1],
                'value': form_code.value[2],
            },
            'batchFile': {
                'fileSize': zip_metadata['file_size'],
                'fileHash': zip_metadata['file_hash_sha256_b64'],
                'fileParts': [
                    {
                        'ordinalNumber': part['ordinal_number'],
                        'fileName': part['file_name'],
                        'fileSize': part['file_size'],
                        'fileHash': part['file_hash_sha256_b64'],
                    }
                    for part in parts
                ],
            },
            'encryption': {
                'encryptedSymmetricKey': base64.b64encode(encrypted_key).decode(),
                'initializationVector': base64.b64encode(iv).decode(),
            },
        }

        _logger.info('Opening batch import: %d parts, %d bytes total', len(parts), zip_metadata['file_size'])

        return self._call_api(
            'sessions/batch', method='post', expected_status=requests.codes.created, json=payload
        ).json()

    def _upload_batch_part(
        self, url: str, method: str, headers: dict[str, str], encrypted_data: bytes, part_number: int
    ) -> None:
        try:
            _logger.debug('Uploading part %d (%d bytes) to %s', part_number, len(encrypted_data), url[:50] + '...')

            response = self._session.request(
                method=method, url=url, data=encrypted_data, headers=headers, timeout=TIMEOUT_SECS
            )

            if response.status_code != requests.codes.created:
                raise KsefBatchPartUploadError(part_number, response.status_code, response.text)

            _logger.info('Part %d uploaded successfully', part_number)

        except requests.RequestException as err:
            raise KsefBatchPartUploadError(part_number, 0, str(err)) from err

    def _upload_batch_parts(self, upload_requests: list[dict[str, Any]], parts: list[BatchPartMetadata]) -> None:
        upload_map = {req['ordinalNumber']: req for req in upload_requests}

        for part in parts:
            ordinal = part['ordinal_number']

            if ordinal not in upload_map:
                raise KsefClientError(f'No upload request for part {ordinal}')

            upload_req = upload_map[ordinal]

            self._upload_batch_part(
                url=upload_req['url'],
                method=upload_req['method'],
                headers=upload_req['headers'],
                encrypted_data=part['encrypted_data'],
                part_number=ordinal,
            )

        _logger.info('All %d parts uploaded successfully', len(parts))

    def start_invoice_batch_import(
        self,
        invoices: Iterator[tuple[str, bytes]],
        form_code: FormCode = FormCode.FA_3,
        max_part_size: int = 100 * 1024 * 1024,
    ) -> str:
        self._ensure_access_token()

        zip_bytes, invoice_count = self._create_invoice_zip(invoices)

        _logger.info('Starting batch invoice submission: %d invoices', invoice_count)

        zip_metadata = self._calculate_file_metadata(zip_bytes)

        _logger.debug('Created ZIP archive: %d bytes', len(zip_bytes))

        raw_key = secrets.token_bytes(32)
        raw_iv = secrets.token_bytes(16)

        parts = self._prepare_batch_parts(zip_bytes, raw_key, raw_iv, max_part_size)

        public_key = self._load_symmetric_public_key()
        encrypted_key = public_key.encrypt(
            raw_key,
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )

        session_response = self._open_invoice_batch_import(form_code, zip_metadata, parts, encrypted_key, raw_iv)

        reference_number = session_response['referenceNumber']
        upload_requests = session_response['partUploadRequests']

        self.invoice_batch_import_key = raw_key
        self.invoice_batch_import_iv = raw_iv
        self.invoice_batch_import_reference = reference_number

        _logger.info('Batch import opened: %s', reference_number)

        try:
            self._upload_batch_parts(upload_requests, parts)
        except KsefBatchPartUploadError:
            _logger.error('Part upload failed, batch import may be invalid')
            raise

        _logger.info('Batch submission complete: %s', reference_number)
        return reference_number

    def close_invoice_batch_import(self, session_reference: str | None = None) -> None:
        self._ensure_access_token()

        session_reference = session_reference or self.invoice_batch_import_reference

        if session_reference is None:
            raise KsefClientError('No session reference provided or active.')

        _logger.debug('Closing batch import: %s', session_reference)

        self._call_api(
            f'sessions/batch/{session_reference}/close',
            method='post',
            expected_status=requests.codes.no_content,
        )

        _logger.info('Batch import closed: %s', session_reference)

    def _download_and_decrypt_part(self, part: dict[str, Any]) -> Generator[tuple[str, str], None, None]:
        url = part['url']
        part_name = part['partName']

        _logger.debug('Downloading invoice part: %s', part_name)

        try:
            response = self._session.get(url, timeout=TIMEOUT_SECS)
            response.raise_for_status()
        except requests.HTTPError as error:
            raise KsefInvoiceBatchExportError(f'Could not download invoice part: {part_name}: {error}') from error

        encrypted_data = response.content

        cipher = Cipher(
            algorithms.AES(cast('bytes', self.invoice_batch_export_key)),
            modes.CBC(cast('bytes', self.invoice_batch_export_iv)),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted_data) + decryptor.finalize()

        unpadder = sym_padding.PKCS7(128).unpadder()
        decrypted_data = unpadder.update(decrypted_padded) + unpadder.finalize()

        _logger.debug('Decrypted part: %s (%d bytes)', part_name, len(decrypted_data))

        with zipfile.ZipFile(io.BytesIO(decrypted_data)) as zip_file:
            for file_name in zip_file.namelist():
                if not file_name.endswith('.xml'):
                    continue

                with zip_file.open(file_name) as xml_file:
                    xml_content = xml_file.read().decode()
                    _logger.debug('Extracted invoice: %s', file_name)
                    yield file_name, xml_content

    @staticmethod
    def build_invoice_verification_url(base_qr_url: str, nip: str, issue_date: date, invoice_xml: bytes) -> str:
        invoice_hash = hashlib.sha256(invoice_xml).digest()

        invoice_hash_b64url = base64.urlsafe_b64encode(invoice_hash).decode().rstrip('=')

        return urljoin(base_qr_url, f'invoice/{nip}/{issue_date:%d-%m-%Y}/{invoice_hash_b64url}')

    @staticmethod
    def _extract_certificate_serial(certificate: x509.Certificate) -> str:
        hex_str = format(certificate.serial_number, 'X')
        if len(hex_str) % 2 != 0:
            hex_str = '0' + hex_str
        return hex_str

    @staticmethod
    def _sign_url_path_ecdsa(url_path: str, private_key: ec.EllipticCurvePrivateKey) -> bytes:
        if not isinstance(private_key.curve, ec.SECP256R1):
            raise KsefCertificateVerificationUrlError(
                f'ECDSA key must use P-256 curve, got {type(private_key.curve).__name__}'
            )

        der_signature = private_key.sign(url_path.encode(), ec.ECDSA(hashes.SHA256()))

        signature_r, signature_s = decode_dss_signature(der_signature)

        signature_r_bytes = signature_r.to_bytes(32, byteorder='big')
        signature_s_bytes = signature_s.to_bytes(32, byteorder='big')

        return signature_r_bytes + signature_s_bytes

    @staticmethod
    def build_certificate_verification_url(
        base_qr_url: str,
        context_value: str,
        seller_nip: str,
        certificate_pem: bytes,
        private_key_pem: bytes,
        invoice_xml: bytes,
        private_key_password: bytes,
        context_type: ContextIdentifierType = ContextIdentifierType.NIP,
    ) -> str:
        try:
            certificate = x509.load_pem_x509_certificate(certificate_pem, backend=default_backend())
        except ValueError as err:
            raise KsefCertificateVerificationUrlError(f'Failed to load certificate: {err}') from err

        certificate_serial = KsefClient._extract_certificate_serial(certificate)

        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem, password=private_key_password, backend=default_backend()
            )
        except (ValueError, TypeError, crypto_exceptions.UnsupportedAlgorithm) as err:
            raise KsefCertificateVerificationUrlError(f'Failed to load private key: {err}') from err

        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise KsefCertificateVerificationUrlError(
                f'Unsupported private key type: {type(private_key).__name__}. Only ECDSA keys are supported.'
            )

        invoice_hash = hashlib.sha256(invoice_xml).digest()
        invoice_hash_b64url = base64.urlsafe_b64encode(invoice_hash).decode().rstrip('=')

        parsed_url = urlparse(base_qr_url)
        base_domain = parsed_url.netloc or parsed_url.path.split('/')[0]

        path_to_sign = (
            f'{base_domain}/certificate/{context_type}/{context_value}/'
            f'{seller_nip}/{certificate_serial}/{invoice_hash_b64url}'
        )

        signature_bytes = KsefClient._sign_url_path_ecdsa(path_to_sign, private_key)

        signature_b64url = base64.urlsafe_b64encode(signature_bytes).decode().rstrip('=')

        path = (
            f'certificate/{context_type}/{context_value}/{seller_nip}/'
            f'{certificate_serial}/{invoice_hash_b64url}/{signature_b64url}'
        )
        return urljoin(base_qr_url, path)
