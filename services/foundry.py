import os
import base64
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
import openai
from openai import AzureOpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


class FoundryConfigError(RuntimeError):
    """Azure OpenAI is misconfigured or unreachable, so every call will fail.

    Callers should stop the pipeline instead of recording the failure and
    carrying on with empty data.
    """


class FoundryResponseError(RuntimeError):
    """A single call returned no usable content (truncated or filtered)."""


def describe_fatal_error(exc: Exception) -> Optional[str]:
    """Return an actionable message if ``exc`` means no call can succeed."""
    if isinstance(exc, ClientAuthenticationError):
        return (
            "Azure credential could not get a token. Run `az login` (or set up "
            f"another DefaultAzureCredential source) and retry. Details: {exc}"
        )

    if isinstance(exc, openai.APIConnectionError):
        return (
            "Could not reach the Azure OpenAI endpoint. Check AZURE_OPENAI_ENDPOINT "
            f"in .env and your network connection. Details: {exc}"
        )

    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return (
            "Azure OpenAI rejected the credentials. Make sure the signed-in identity "
            "has the 'Cognitive Services OpenAI User' role on the resource. "
            f"Details: {exc}"
        )

    if isinstance(exc, openai.NotFoundError):
        return (
            "Azure OpenAI deployment or endpoint not found. Check "
            "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT and "
            f"AZURE_OPENAI_API_VERSION in .env. Details: {exc}"
        )

    if isinstance(exc, openai.BadRequestError) and "SubscriptionNotRegistered" in str(exc):
        return (
            "The Azure subscription is not registered for Microsoft.CognitiveServices. "
            "Run `az provider register --namespace Microsoft.CognitiveServices`, wait "
            f"until it shows 'Registered', then retry. Details: {exc}"
        )

    return None


class FoundryClient:
    def __init__(self):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()

        if not endpoint:
            raise FoundryConfigError(
                "AZURE_OPENAI_ENDPOINT is not set. Create a .env file in "
                f"{PROJECT_ROOT} with AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/ "
                "(optionally AZURE_OPENAI_DEPLOYMENT and AZURE_OPENAI_API_VERSION), "
                "and sign in with `az login`."
            )

        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default"
        )

        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version
        )

        self.deployment = deployment

    def _complete(self, **kwargs) -> str:
        try:
            response = self.client.chat.completions.create(model=self.deployment, **kwargs)
        except Exception as e:
            message = describe_fatal_error(e)
            if message:
                raise FoundryConfigError(message) from e
            raise

        choice = response.choices[0]
        content = choice.message.content

        if choice.finish_reason == "length":
            raise FoundryResponseError(
                "Model response was cut off at max_tokens; the JSON is incomplete."
            )

        if not content:
            raise FoundryResponseError(
                f"Model returned no content (finish_reason={choice.finish_reason})."
            )

        return content

    def chat(self, prompt: str) -> str:
        return self._complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

    def vision(self, image_path: str, prompt: str) -> str:
        image_bytes = Path(image_path).read_bytes()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        return self._complete(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{encoded_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
            # Page-state JSON for a busy parts page easily exceeds 1200 tokens,
            # which used to truncate the response and break JSON parsing.
            max_tokens=4096,
        )


if __name__ == "__main__":
    ai = FoundryClient()
    reply = ai.chat("Reply with exactly: Azure AI Foundry connection successful.")
    print(reply)
