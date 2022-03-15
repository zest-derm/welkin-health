"""Client

This module provides a Client object to interface with the Welkin Health API.
"""
import logging

from requests import HTTPError, Session
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests.compat import urljoin
from requests.packages.urllib3.util.retry import Retry  # type: ignore

from welkin.api import *

logger = logging.getLogger(__name__)


class WelkinAuth(HTTPBasicAuth):
    """Attaches API Key Authentication to the given Request object."""

    def __init__(self, api_key):
        self.api_key = api_key

    def __eq__(self, other):
        return self.api_key == getattr(other, "api_key", None)

    def __call__(self, r):
        logger.info(f"{r.method} {r.url}")
        r.headers["Authorization"] = self.api_key
        return r


class Client(Session):
    """Welkin Health Client.

    Constructs a :obj:`requests.Session` for Welkin Health API requests with
    authorization, base URL, request timeouts, and request retries.

    Args:
        tenant (str): Name of the organization.
        instance (str): Name of the database inside a customer space.
        api_client (str): API client name.
        secret_key (str): API client secret key.
        timeout (int, optional): :obj:`TimeoutHTTPAdapter` timeout value. Defaults to 5.
        total (int, optional): :obj:`Retry` total value. Defaults to 5.
        backoff_factor (int, optional): :obj:`Retry` backoff_factor value.
            Defaults to 30.

    Usage::

        from welkin import Client

        welkin = Client(
            tenant="gh", api_client="VBOPNRYRWJIP", secret_key="+}B{KGTG6#zG%P;tQm0C"
        )

        # Create a calendar event
        patient = welkin.Patient(id="6801d498-26f4-4aee-961b-5daffcf193c8")
        user = welkin.User(username="johndoe")
        event = welkin.Calendar(
            start="2020-01-01T00:00:00.000Z",
            end="2020-01-31T23:59:59.000Z",
            patient=patient,
            host=user,
        ).post()

        # Get a calendar event by ID
        event = welkin.Calendar(id="313c2029-493b-4114-8b86-788d631a1851").get()

        # Get a single calendar event
        event = welkin.Calendar().get(id="313c2029-493b-4114-8b86-788d631a1851")

        # Search for calendar events with pagination
        events = welkin.Calendar().get(
            from_date="2020-01-15T14:00:00.000Z",
            to_date="2020-02-11T00:00:00.000Z",
            paginate=True,
        )
        for event in events:
            print(event)
    """

    def __init__(
        self,
        tenant,
        instance,
        api_client,
        secret_key,
        timeout=5,
        total=5,
        backoff_factor=30,
    ):
        """Welkin Health client constructor.

        Constructs a :obj:`requests.Session` for Welkin Health API requests with
        authorization, base URL, request timeouts, and request retries.

        Args:
            tenant (str): Name of the customer space.
            instance (str): Name of the database inside a customer space.
            api_client (str): API client name.
            secret_key (str): API client secret key.
            timeout (int, optional): :obj:`TimeoutHTTPAdapter` timeout value. Defaults to 5.
            total (int, optional): :obj:`Retry` total value. Defaults to 5.
            backoff_factor (int, optional): :obj:`Retry` backoff_factor value.
                Defaults to 30.
        """
        super().__init__()

        self.auth = WelkinAuth(
            tenant=tenant, api_client=api_client, secret_key=secret_key
        )
        self.host = f"https://api.live.welkincloud.io/{tenant}/{instance}/"

        adapter = TimeoutHTTPAdapter(
            timeout=timeout,
            max_retries=Retry(
                total=total,
                status_forcelist=[429, 500, 502, 503, 504],
                backoff_factor=backoff_factor,
            ),
        )
        self.mount("https://", adapter)
        self.mount("http://", adapter)

        self.__build_resources()

    def __build_resources(self):
        """Add each resource with a reference to this instance."""
        for k, v in globals().items():
            try:
                for base in v.__bases__:
                    if base.__name__ not in ["Collection", "Resource"]:
                        continue

                    v._client = self
                    setattr(self, k, v)

            except AttributeError:
                continue

    def request(self, method, path, *args, **kwargs):
        """Override :obj:`Session` request method to add retries and output JSON.

        Args:
            method (str): Method for the new Request object.
            path (str): Path from host for the new Request object.

        Returns:
            dict: Response JSON
        """
        if not isinstance(path, str):
            path = "/".join((str(s) for s in path if s))
        path = path.rstrip("/")

        response = super().request(
            method=method, url=urljoin(self.host, path), *args, **kwargs
        )
        response.raise_for_status()

        json = response.json()
        meta = json.pop("meta", None)
        resource, *_ = json.values()

        if meta:
            return resource, meta
        return resource


class TimeoutHTTPAdapter(HTTPAdapter):
    def __init__(self, timeout, *args, **kwargs):
        """TimeoutHTTPAdapter constructor.

        Args:
            timeout (int): How many seconds to wait for the server to send data before
                giving up.
        """
        self.timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):
        """Override :obj:`HTTPAdapter` send method to add a default timeout."""
        timeout = kwargs.get("timeout")
        if timeout is None:
            kwargs["timeout"] = self.timeout

        return super().send(request, **kwargs)