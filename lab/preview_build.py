"""Build one pinned source commit with protected tooling, then create its preview."""
import json
import os
import re
import time
from urllib.parse import quote

from common import STATE
from delivery_provider import SOURCE, api, endpoint
from delivery_source_comparison import ComparisonInputError
from gitea import GiteaHTTPError

WORKFLOW = 'build-preview.yaml'
BUILD_URL = 'https://gitea.localhost:34443/elastic-agent/delivery-source/actions'


class PreviewBuildError(ComparisonInputError):
    def __init__(self, message, result=None):
        super().__init__(message)
        self.preview_result = result


def valid_ref(value):
    """Accept a branch name or full SHA, never Git revision expressions or URLs."""
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,199}', value):
        return False
    return not (value.endswith(('/', '.')) or '..' in value or '//' in value or
                any(part.startswith('.') or part.endswith('.lock') for part in value.split('/')))


def prepare(source_ref):
    """Resolve once at submission, separately pinning the protected workflow."""
    if not valid_ref(source_ref):
        raise ValueError('Enter a branch name or a full 40-character commit SHA.')
    try:
        if re.fullmatch('[a-fA-F0-9]{40}', source_ref):
            source = api(endpoint(SOURCE, '/git/commits/' + source_ref.lower()))['sha']
        else:
            source = api(endpoint(SOURCE, '/branches/' + quote(source_ref, safe='')))['commit']['id']
        workflow = api(endpoint(SOURCE, '/branches/main'))['commit']['id']
        installed = api(endpoint(SOURCE, '/contents/.github/workflows/' + WORKFLOW + '?ref=' + workflow))
    except GiteaHTTPError as error:
        if error.status_code == 404:
            raise ValueError('The branch/commit or protected preview workflow was not found in delivery-source. '
                             'Check the revision and install the preview workflow on main.') from None
        raise
    if not all(re.fullmatch('[a-f0-9]{40}', x or '') for x in (source, workflow)) or installed.get('type') != 'file':
        raise ValueError('The source commit or protected preview workflow could not be verified.')
    return {'_preview_source_sha': source, '_preview_workflow_sha': workflow}


def _save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    temporary.replace(path)


def advance(request, identifier, progress):
    """Advance without holding the coordinator while CI runs; dispatch at most once."""
    from delivery_release import from_run
    from delivery_runtime import resolve, preview
    from delivery_variant_selection import source_selection
    from preview_routes import url

    if not re.fullmatch('[a-f0-9]{32}', identifier):
        raise ValueError('Invalid preview operation identity.')
    source, workflow = request['_preview_source_sha'], request['_preview_workflow_sha']
    title = 'Preview ' + source + ' ' + identifier
    result = {'source_ref': request['source_ref'], 'source_sha': source, 'workflow_sha': workflow,
              'build_url': BUILD_URL, 'state': 'waiting-for-build'}
    folder = STATE / 'preview-builds'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (identifier + '.json')
    journal = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    if journal and (journal['source_sha'], journal['workflow_sha']) != (source, workflow):
        raise PreviewBuildError('The saved build request has a different pinned identity.', result)
    matching = []
    for page in range(1, 6):
        runs = api(endpoint(SOURCE, f'/actions/runs?limit=100&page={page}'))['workflow_runs']
        matching.extend(r for r in runs if r.get('display_title') == title and
                        r.get('path') == WORKFLOW + '@refs/heads/main' and
                        r.get('event') == 'workflow_dispatch' and r.get('head_sha') == workflow)
        if matching or len(runs) < 100:
            break
    if not matching:
        if journal is None:
            if api(endpoint(SOURCE, '/branches/main'))['commit']['id'] != workflow:
                raise PreviewBuildError('Protected main changed while queued. Submit a new preview request.', result)
            journal = {'source_sha': source, 'workflow_sha': workflow, 'created_at': time.time()}
            # Persist intent before the remote mutation. An unknown dispatch
            # outcome is inspected by request identity, never blindly repeated.
            try:
                with path.open('x', encoding='utf-8') as stream:
                    json.dump(journal, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
            except FileExistsError:
                return {**result, 'waiting': True, 'progress': 'Confirming the existing preview build request'}
            progress('Requesting a build of commit ' + source[:12])
            try:
                api(endpoint(SOURCE, '/actions/workflows/' + WORKFLOW + '/dispatches'), 'POST',
                    {'ref': 'main', 'inputs': {'source_sha': source, 'request_id': identifier}})
            except GiteaHTTPError as error:
                raise PreviewBuildError('Gitea rejected the preview build request (HTTP ' + str(error.status_code) +
                                        '). Check the protected workflow and Actions permissions before retrying.', result) from None
            except Exception:
                raise PreviewBuildError('The build request outcome could not be confirmed. Check delivery-source Actions '
                                        'before starting another attempt; this request will not be sent twice.', result) from None
        if time.time() - journal['created_at'] > 300:
            raise PreviewBuildError('No matching preview build appeared within five minutes. Check Actions and runner '
                                    'availability before starting another attempt.', result)
        return {**result, 'waiting': True, 'progress': 'Waiting for the requested build to appear in Actions'}
    if len(matching) != 1:
        raise PreviewBuildError('More than one build has this request identity. Review Actions before continuing.', result)
    run = matching[0]
    result.update(build_run=run['id'], build_url=BUILD_URL + '/runs/' + str(run['id']),
                  build_status=run['status'], build_conclusion=run.get('conclusion'))
    journal = journal or {'source_sha': source, 'workflow_sha': workflow, 'created_at': time.time()}
    journal['build_run'] = run['id']
    _save(path, journal)
    if run['status'] != 'completed':
        return {**result, 'waiting': True, 'progress': 'Build ' + str(run['id']) + ' is ' + run['status']}
    if run['conclusion'] != 'success':
        raise PreviewBuildError('Preview build ' + str(run['id']) + ' finished with ' + str(run['conclusion']) +
                                '. Open the build logs; no environment was deployed.', result)
    try:
        receipt, release, _files = from_run(run['id'])
    except (ValueError, KeyError):
        raise PreviewBuildError('Build evidence could not be verified. Open the build logs; no preview was deployed.', result) from None
    if (receipt.get('preview_request_id') != identifier or release['source_sha'] != source or
            receipt.get('workflow_source_sha') != workflow):
        raise PreviewBuildError('Successful build evidence differs from the requested commit. No preview was deployed.', result)
    progress('Build succeeded; preparing the frozen preview for ' + source[:12])
    try:
        selection = source_selection(source)
        deployment = resolve(run['id'], request.get('dataset', 'esci-gb-v1'), request.get('recipe'),
                             merged=False, variant_config=selection['configuration'])
    except (ValueError, KeyError):
        raise PreviewBuildError('The source configuration or selected data is incompatible with this build. '
                                'Review the build and catalogue selection; no preview was deployed.', result) from None
    environment = preview(deployment)
    return {**result, **environment, 'state': 'ready', 'waiting': False,
            'version': release.get('version'), 'browser_url': url(environment['name'])}
