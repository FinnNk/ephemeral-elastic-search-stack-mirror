import concurrent.futures,hashlib,urllib.request,zipfile,io,json
from pathlib import Path
Path('.lab/tools').mkdir(parents=True,exist_ok=True)
Path('.lab/evidence').mkdir(parents=True,exist_ok=True)
jobs=[('k3d.exe','https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-windows-amd64.exe','https://github.com/k3d-io/k3d/releases/download/v5.9.0/checksums.txt','k3d-windows-amd64.exe'),('kind.exe','https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-windows-amd64','https://github.com/kubernetes-sigs/kind/releases/download/v0.33.0/kind-windows-amd64.sha256sum','kind-windows-amd64'),('helm.exe','https://get.helm.sh/helm-v4.3.0-windows-amd64.zip','https://get.helm.sh/helm-v4.3.0-windows-amd64.zip.sha256sum','helm-v4.3.0-windows-amd64.zip')]
def get(url):
    with urllib.request.urlopen(url,timeout=90) as r:return r.read()
def download(job):
    name,url,check,asset=job
    data=get(url);checks=get(check).decode()
    line=next((line for line in checks.splitlines() if asset in line),checks.strip())
    expected=line.split()[0]
    assert hashlib.sha256(data).hexdigest()==expected,name
    binary=zipfile.ZipFile(io.BytesIO(data)).read('windows-amd64/helm.exe') if name=='helm.exe' else data
    Path('.lab/tools',name).write_bytes(binary)
    return {'tool':name,'url':url,'download_sha256':expected}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    records=list(pool.map(download,jobs))
Path('.lab/evidence/tool-downloads.json').write_text(json.dumps(records,indent=2))
print(json.dumps(records))
