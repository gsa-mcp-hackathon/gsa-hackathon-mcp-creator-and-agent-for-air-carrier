"""Who is calling, as Databricks authenticated them.

Databricks Apps puts the signed-in user in front of the app and forwards two
things this module reads:

  x-forwarded-email         the user's email. Display only. Never the basis
                            of an authority decision.
  x-forwarded-access-token  the user's on-behalf-of token. Present only when
                            the app declares user_api_scopes (here: sql).

Authority is decided inside Unity Catalog, by a statement that runs under the
user's token and calls current_user() (api.harness_sql.AUTHORITY_CHECK). This
module never decides anything. It only builds the client that statement runs
as. There is no role in a request, no role in a cookie, and the demonstration
view switcher is not read here at all.

Without a token there is no way to act as the user, so every authority-bearing
route refuses with the reason from obo_missing_reason(). Reads still work as
the app service principal.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class Identity:
    """The caller. email is for display; token is what authority runs on."""
    email: str | None
    token: str | None

    @property
    def can_act(self) -> bool:
        """True when a statement can run as this user. Not an authority check."""
        return bool(self.token)


def from_request(request: Request) -> Identity:
    """Read the identity headers the Apps proxy sets. Missing headers stay None."""
    h = request.headers
    email = h.get("x-forwarded-email") or h.get("x-forwarded-preferred-username")
    token = h.get("x-forwarded-access-token")
    return Identity(email=email or None, token=token or None)


def obo_missing_reason() -> str:
    """The refusal shown when the request carries no user token."""
    return ("This request did not carry your sign-in token, so the app cannot act as you. "
            "The app needs the sql user authorization scope and your consent to it. "
            "No action has been taken.")


def user_client(identity: Identity):
    """A WorkspaceClient that authenticates as the end user, or None.

    auth_type='pat' forces the forwarded token. Without it the SDK would pick
    up the app service principal's client id and secret from the environment
    and the statement would run as the app, which is the one outcome this
    path exists to prevent.
    """
    if not identity.token:
        return None
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.config import Config
    host = os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = "https://" + host
    return WorkspaceClient(config=Config(host=host, token=identity.token, auth_type="pat"))
