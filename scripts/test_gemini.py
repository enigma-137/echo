import argparse
import asyncio
import socket
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from google import genai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.runtime import configure_runtime


DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


def mask_key(value: str | None) -> str:
    if not value:
        return "missing"
    return f"present (...{value[-4:]})"


def print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def test_dns(host: str) -> bool:
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        unique_addresses = sorted({item[4][0] for item in addresses})
        print_result("DNS", True, f"{host} -> {', '.join(unique_addresses[:4])}")
        return True
    except OSError as exc:
        print_result("DNS", False, str(exc))
        return False


def test_tls(host: str, timeout: int) -> bool:
    try:
        context = ssl.create_default_context()
        started = time.perf_counter()
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                elapsed = time.perf_counter() - started
                cert = tls.getpeercert()
                subject = dict(item[0] for item in cert.get("subject", []))
                print_result("TLS", True, f"{tls.version()} in {elapsed:.2f}s, certificate CN={subject.get('commonName')}")
                return True
    except OSError as exc:
        print_result("TLS", False, str(exc))
        return False


async def test_rest(base_url: str, model: str, api_key: str, timeout: int) -> bool:
    endpoint = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": "Reply with exactly: ok"}]}]}
    headers = {"x-goog-api-key": api_key}
    try:
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10)) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
        elapsed = time.perf_counter() - started
        if response.is_success:
            body = response.json()
            text = (
                body.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
            )
            print_result("REST generateContent", True, f"HTTP {response.status_code} in {elapsed:.2f}s, text={text!r}")
            return True
        print_result("REST generateContent", False, f"HTTP {response.status_code}: {response.text[:500]}")
        return False
    except httpx.HTTPError as exc:
        print_result("REST generateContent", False, f"{exc.__class__.__name__}: {exc}")
        return False


async def test_sdk(model: str, api_key: str, timeout: int) -> bool:
    try:
        client = genai.Client(api_key=api_key)
        started = time.perf_counter()
        response = await asyncio.wait_for(
            client.aio.models.generate_content(model=model, contents="Reply with exactly: ok"),
            timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        print_result("google-genai SDK", True, f"{elapsed:.2f}s, text={(response.text or '').strip()!r}")
        return True
    except TimeoutError:
        print_result("google-genai SDK", False, f"timed out after {timeout}s")
        return False
    except Exception as exc:
        print_result("google-genai SDK", False, f"{exc.__class__.__name__}: {exc}")
        return False


async def test_sync_sdk(model: str, api_key: str, timeout: int) -> bool:
    def call() -> str:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents="Reply with exactly: ok")
        return (response.text or "").strip()

    try:
        started = time.perf_counter()
        text = await asyncio.wait_for(asyncio.to_thread(call), timeout=timeout)
        elapsed = time.perf_counter() - started
        print_result("google-genai sync SDK", True, f"{elapsed:.2f}s, text={text!r}")
        return True
    except TimeoutError:
        print_result("google-genai sync SDK", False, f"timed out after {timeout}s")
        return False
    except Exception as exc:
        print_result("google-genai sync SDK", False, f"{exc.__class__.__name__}: {exc}")
        return False


async def main() -> None:
    configure_runtime()
    parser = argparse.ArgumentParser(description="Diagnose local Gemini connectivity for Echo.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.gemini_api_key
    model = args.model or settings.gemini_model
    host = urlparse(args.base_url).hostname or "generativelanguage.googleapis.com"

    print("Echo Gemini diagnostic")
    print(f"Base URL: {args.base_url}")
    print(f"Host: {host}")
    print(f"Model: {model}")
    print(f"API key: {mask_key(api_key)}")
    print()

    if not api_key:
        print_result("Config", False, "GEMINI_API_KEY is missing from .env")
        return

    test_dns(host)
    test_tls(host, args.timeout)
    await test_rest(args.base_url, model, api_key, args.timeout)
    await test_sdk(model, api_key, args.timeout)
    await test_sync_sdk(model, api_key, args.timeout)


if __name__ == "__main__":
    asyncio.run(main())
