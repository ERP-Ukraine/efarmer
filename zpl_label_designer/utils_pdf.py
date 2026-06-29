import time
import typing as _t
from dataclasses import dataclass  # pylint: disable=missing-manifest-dependency

import requests


LabelaryHeaders = _t.Dict[str, str]


@dataclass
class LabelaryResponse:
    content: bytes
    content_type: str
    status_code: int
    headers: LabelaryHeaders

    @property
    def total_count(self) -> _t.Optional[int]:
        value = self.headers.get('X-Total-Count')
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class LabelaryError(Exception):
    pass


class LabelaryRateLimitError(LabelaryError):
    def __init__(self, message: str, retry_after_seconds: _t.Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LabelaryClient:
    '''
    Simple connector for the Labelary API.

    Supports PDF generation (and other formats), optional multi-label PDF by omitting index,
    page customization headers, and resilient retry/backoff for 429/5xx responses.
    '''

    def __init__(
        self,
        base_url: str = 'https://api.labelary.com/v1',
        session: _t.Optional[requests.Session] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip('/')
        self.session = session or requests.Session()
        self.timeout = timeout

    def _build_url(
        self,
        dpmm: str,
        width_in: _t.Union[int, float, str],
        height_in: _t.Union[int, float, str],
        index: _t.Optional[int],
    ) -> str:
        width = str(width_in)
        height = str(height_in)
        if index is None:
            # For PDF requests, omitting index returns all labels in a single PDF.
            return f'{self.base_url}/printers/{dpmm}/labels/{width}x{height}/'
        return f'{self.base_url}/printers/{dpmm}/labels/{width}x{height}/{index}/'

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: LabelaryHeaders,
        data: _t.Optional[bytes] = None,
        files: _t.Optional[_t.Dict[str, _t.Any]] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> LabelaryResponse:
        last_exc: _t.Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=self.timeout,
                )

                # 2xx
                if 200 <= resp.status_code < 300:
                    return LabelaryResponse(
                        content=resp.content,
                        content_type=resp.headers.get('Content-Type', ''),
                        status_code=resp.status_code,
                        headers=dict(resp.headers),
                    )

                # 429 handling with Retry-After
                if resp.status_code == 429:
                    retry_after = resp.headers.get('Retry-After')
                    wait_s: _t.Optional[float] = None
                    if retry_after:
                        try:
                            wait_s = float(retry_after)
                        except ValueError:
                            wait_s = None
                    if attempt < max_retries:
                        time.sleep(wait_s if wait_s is not None else backoff_factor * (attempt + 1))
                        continue
                    raise LabelaryRateLimitError(
                        'Labelary rate limit exceeded (HTTP 429). Attempts exhausted.',
                        retry_after_seconds=wait_s,
                    )

                # Retry on transient 5xx
                if 500 <= resp.status_code < 600 and attempt < max_retries:
                    time.sleep(backoff_factor * (attempt + 1))
                    continue

                # Specific known errors with helpful messages
                if resp.status_code == 413:
                    raise LabelaryError(
                        'Payload too large (HTTP 413). Check labels per request and body size limits.'
                    )
                if resp.status_code == 400:
                    raise LabelaryError(
                        'Bad request (HTTP 400). Check dpmm, dimensions, and any embedded assets.'
                    )

                # Generic error
                raise LabelaryError(
                    f'Labelary request failed with HTTP {resp.status_code}: {resp.text[:300]}'
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                if attempt < max_retries:
                    time.sleep(backoff_factor * (attempt + 1))
                    continue
                raise LabelaryError(f'Network error contacting Labelary: {exc}') from exc
        # Should be unreachable
        if last_exc:
            raise LabelaryError(f'Labelary request failed: {last_exc}') from last_exc
        raise LabelaryError('Labelary request failed for unknown reasons')

    def render(
        self,
        *,
        zpl: _t.Union[str, bytes],
        dpmm: str,
        width_in: _t.Union[int, float, str],
        height_in: _t.Union[int, float, str],
        index: _t.Optional[int] = 0,
        accept: str = 'application/pdf',
        use_post: bool = True,
        content_type: str = 'application/x-www-form-urlencoded',
        page_size: _t.Optional[str] = None,  # Letter, Legal, A4, A5, A6
        page_orientation: _t.Optional[str] = None,  # Portrait, Landscape
        page_layout: _t.Optional[str] = None,  # like '2x3'
        page_align: _t.Optional[str] = None,  # Left, Right, Center, Justify
        page_valign: _t.Optional[str] = None,  # Top, Bottom, Center, Justify
        label_border: _t.Optional[str] = None,  # Dashed, Solid, None
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> LabelaryResponse:
        '''
        Render a label using Labelary.

        For PDF with multiple labels, pass index=None to include all labels in the PDF.
        '''
        url = self._build_url(dpmm=dpmm, width_in=width_in, height_in=height_in, index=index)

        headers: LabelaryHeaders = {'Accept': accept}

        # PDF-only customization headers
        if accept == 'application/pdf':
            if page_size:
                headers['X-Page-Size'] = page_size
            if page_orientation:
                headers['X-Page-Orientation'] = page_orientation
            if page_layout:
                headers['X-Page-Layout'] = page_layout
            if page_align:
                headers['X-Page-Align'] = page_align
            if page_valign:
                headers['X-Page-Vertical-Align'] = page_valign
            if label_border:
                headers['X-Label-Border'] = label_border

        if use_post:
            # Prefer POST to avoid URL length and encoding issues
            if content_type not in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
                raise ValueError('Unsupported content_type for POST; use form-urlencoded or multipart/form-data')

            if content_type == 'application/x-www-form-urlencoded':
                headers['Content-Type'] = content_type
                # Body is raw ZPL; accept str or bytes
                if isinstance(zpl, bytes):
                    data = zpl
                else:
                    data = zpl.encode('utf-8')
                return self._request(
                    'POST',
                    url,
                    headers=headers,
                    data=data,
                    files=None,
                    max_retries=max_retries,
                    backoff_factor=backoff_factor,
                )

            # multipart/form-data with field name 'file'
            file_bytes = zpl if isinstance(zpl, bytes) else zpl.encode('utf-8')
            files = {'file': ('label.zpl', file_bytes, 'application/octet-stream')}
            return self._request(
                'POST',
                url,
                headers=headers,
                data=None,
                files=files,
                max_retries=max_retries,
                backoff_factor=backoff_factor,
            )

        # GET fallback (less recommended due to URL length/encoding constraints)
        return self._request(
            'GET',
            f'{url}{zpl}',
            headers=headers,
            data=None,
            files=None,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )

    def render_pdf(
        self,
        *,
        zpl: _t.Union[str, bytes],
        dpmm: str,
        width_in: _t.Union[int, float, str],
        height_in: _t.Union[int, float, str],
        all_labels: bool = False,
        page_size: _t.Optional[str] = None,
        page_orientation: _t.Optional[str] = None,
        page_layout: _t.Optional[str] = None,
        page_align: _t.Optional[str] = None,
        page_valign: _t.Optional[str] = None,
        label_border: _t.Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> LabelaryResponse:
        '''
        Convenience for PDFs
        '''
        index = None if all_labels else 0
        return self.render(
            zpl=zpl,
            dpmm=dpmm,
            width_in=width_in,
            height_in=height_in,
            index=index,
            accept='application/pdf',
            use_post=True,
            content_type='application/x-www-form-urlencoded',
            page_size=page_size,
            page_orientation=page_orientation,
            page_layout=page_layout,
            page_align=page_align,
            page_valign=page_valign,
            label_border=label_border,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )


def generate_pdf_from_zpl(
    *,
    zpl: _t.Union[str, bytes],
    dpmm: str,
    width_in: _t.Union[int, float, str],
    height_in: _t.Union[int, float, str],
    all_labels: bool = False,
    page_size: _t.Optional[str] = None,
    page_orientation: _t.Optional[str] = None,
    page_layout: _t.Optional[str] = None,
    page_align: _t.Optional[str] = None,
    page_valign: _t.Optional[str] = None,
    label_border: _t.Optional[str] = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> _t.Tuple[bytes, _t.Optional[int], LabelaryHeaders]:
    '''
    High-level helper to obtain PDF bytes and metadata.

    Returns (pdf_bytes, total_count, response_headers).

    - Set all_labels=True to include all labels in a single PDF (index omitted).
    - Use page_* and label_border for page customization.
    '''
    client = LabelaryClient(timeout=timeout)
    response = client.render_pdf(
        zpl=zpl,
        dpmm=dpmm,
        width_in=width_in,
        height_in=height_in,
        all_labels=all_labels,
        page_size=page_size,
        page_orientation=page_orientation,
        page_layout=page_layout,
        page_align=page_align,
        page_valign=page_valign,
        label_border=label_border,
        max_retries=max_retries,
        backoff_factor=backoff_factor,
    )

    return response.content, response.total_count, response.headers
