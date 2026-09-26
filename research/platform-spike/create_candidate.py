"""Open the synthetic query-understanding PR in Gitea."""
from common import *
from environments import git
from gitea import api

guard()
repo=STATE/'search-source'
git('switch','-c','candidate-normalisation',cwd=repo)
app=repo/'app.py'
app.write_text(app.read_text(encoding='utf-8').replace('NORMALISE=False','NORMALISE=True'),encoding='utf-8')
git('add','app.py',cwd=repo);git('commit','-m','Normalise trainers to running shoes',cwd=repo)
git('push','--set-upstream','origin','candidate-normalisation',cwd=repo)
pr=api('/repos/elastic-agent/search-spike/pulls','POST',{'base':'main','head':'candidate-normalisation',
    'title':'Compare API query understanding against the frozen baseline',
    'body':'Synthetic spike: rewrite trainers to running shoes in the API. The dataset and Elasticsearch index remain unchanged.'})
record('candidate-pr',{'number':pr['number'],'url':pr['html_url'],'head_sha':pr['head']['sha']})
print(pr['html_url'])
