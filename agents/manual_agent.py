import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from services.foundry import FoundryClient


class ManualAgent:
    def __init__(self):
        self.ai = FoundryClient()

    def analyze_manual(self):
        prompt = """
You are an AI assembly manual analyst.

For this project, we are building an instruction-manual-to-animated-video generator.

Reply with a concise JSON structure showing what information should be extracted from a furniture assembly manual before creating an animated video.

Return only JSON.
"""
        return self.ai.chat(prompt)


if __name__ == "__main__":
    agent = ManualAgent()
    result = agent.analyze_manual()
    print(result)