# stdlib imports
import base64

# vendor imports
import requests


def shortenUrl(
    url: str, username: str, password: str, scheme: bool = True
) -> str:
    """Using my personal `short.spgill.me` URL shortening service, return a shortened version of a URL."""
    # Combine the credentials for the authorization header
    authHeaderValue = base64.b64encode(f"{username}:{password}".encode("utf8"))

    return requests.put(
        "https://short.spgill.me/api",
        json={"url": url, "format": "normal" if scheme else "noscheme"},
        headers={"Proxy-Authorization": authHeaderValue},
    ).text
