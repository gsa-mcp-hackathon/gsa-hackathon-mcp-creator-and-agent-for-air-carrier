class DatabricksSecrets:
    def get(self, scope: str, key: str) -> str:
        from databricks.sdk import WorkspaceClient
        return WorkspaceClient().secrets.get_secret(scope, key).value


def make_secrets() -> DatabricksSecrets:
    return DatabricksSecrets()
