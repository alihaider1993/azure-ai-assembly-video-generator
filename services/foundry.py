import os
import base64
from pathlib import Path

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

load_dotenv()


class FoundryClient:
    def __init__(self):
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
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

    def chat(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content

    def vision(self, image_path: str, prompt: str) -> str:
        image_bytes = Path(image_path).read_bytes()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        response = self.client.chat.completions.create(
            model=self.deployment,
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
            max_tokens=1200,
        )

        return response.choices[0].message.content


if __name__ == "__main__":
    ai = FoundryClient()
    reply = ai.chat("Reply with exactly: Azure AI Foundry connection successful.")
    print(reply)