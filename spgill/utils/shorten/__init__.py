import requests


def shortenURL(url, key=None):
    """Take a URL and return the shortened one."""
    return requests.post(
        "https://short.spgill.me/api", data={"url": url, "key": key}
    ).text
