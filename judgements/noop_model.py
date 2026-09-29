"""Registered model contract: return an abstention for every synthetic pair."""


def predict_rows(rows):
    if not isinstance(rows, list):
        raise ValueError('Model input must be a batch of query/product pairs.')
    return [{'outcome': 'abstain'} for _ in rows]


def register(tracking_uri, registered_name='synthetic-esci-judge'):
    import hashlib
    import mlflow
    import pandas as pd
    from fetch_model import tree_digest
    from pathlib import Path

    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    class AbstainingModel(mlflow.pyfunc.PythonModel):
        def predict(self, context, model_input, params=None):
            return pd.DataFrame(predict_rows(model_input.to_dict(orient='records')))

    mlflow.set_tracking_uri(tracking_uri)
    client = mlflow.MlflowClient()
    for existing in client.search_model_versions(f"name='{registered_name}'"):
        if existing.tags.get('model_source_sha256') == source_sha:
            artefact = mlflow.artifacts.download_artifacts(
                artifact_uri=f'models:/{registered_name}/{existing.version}')
            return {'run_id': existing.run_id, 'registered_name': registered_name,
                    'version': existing.version, 'artifact_sha256': tree_digest(artefact),
                    'source_sha256': source_sha, 'reused': True}
    with mlflow.start_run(run_name='synthetic-abstaining-judge') as run:
        info = mlflow.pyfunc.log_model(
            name='judge', python_model=AbstainingModel(),
            input_example=pd.DataFrame([{'payload': '{"query_id":"example-q1","product_id":"example-p1","request":{"query":"desk lamp","country":"GB","currency":"GBP"},"product":{"product_id":"example-p1","title":"Desk lamp","country":"GB","currency":"GBP"}}'}]),
            registered_model_name=registered_name)
    versions = [item for item in client.search_model_versions(
        f"name='{registered_name}'") if item.run_id == run.info.run_id]
    if len(versions) != 1:
        raise ValueError('Could not identify the registered model version.')
    version = versions[0].version
    client.set_model_version_tag(registered_name, version, 'model_source_sha256', source_sha)
    artefact = mlflow.artifacts.download_artifacts(
        artifact_uri=f'models:/{registered_name}/{version}')
    return {'run_id': run.info.run_id, 'model_uri': info.model_uri,
            'registered_name': registered_name, 'version': version,
            'artifact_sha256': tree_digest(artefact), 'source_sha256': source_sha,
            'reused': False}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking-uri', required=True)
    parser.add_argument('--registered-name', default='synthetic-esci-judge')
    args = parser.parse_args()
    print(json.dumps(register(args.tracking_uri, args.registered_name), sort_keys=True))
