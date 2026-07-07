from azure.identity import DefaultAzureCredential


def get_credential():
    """
    Uses Azure CLI login locally and Managed Identity when deployed to Azure.
    No API keys required.
    """
    return DefaultAzureCredential()


def test_auth():
    credential = get_credential()
    token = credential.get_token("https://management.azure.com/.default")
    print("Azure authentication successful")
    print("Token acquired:", token.token[:20] + "...")


if __name__ == "__main__":
    test_auth()