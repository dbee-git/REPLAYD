"""API and media-pipeline integration tests using generated, not copyrighted, footage."""
from pathlib import Path
import subprocess

import pytest
from fastapi.testclient import TestClient

import replayd.web as web
from replayd.web import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture(autouse=True)
def clean_test_storage(tmp_path, monkeypatch):
    """Never touch the real local creator library during tests."""
    monkeypatch.setattr(web, "DATA", tmp_path)
    monkeypatch.setattr(web, "DB", tmp_path / "test_replayd.sqlite3")


def test_home_and_health():
    home = client.get('/')
    assert home.status_code == 200
    assert 'REPLAYD' in home.text
    health = client.get('/api/health').json()
    assert health['ffmpeg_available'] is True
    assert health['mode'] == 'local'


def test_invalid_file_rejected():
    out = client.post('/api/projects', files={'file':('payload.txt', b'not video', 'text/plain')})
    assert out.status_code == 400


def test_tiny_invalid_video_rejected():
    out = client.post('/api/projects', files={'file':('fake.mp4', b'fake', 'video/mp4')})
    assert out.status_code == 422


def test_video_workflow():
    source = ROOT / 'data' / 'DEMO_synthetic.mp4'
    with source.open('rb') as handle:
        uploaded = client.post('/api/projects', files={'file':('demo.mp4', handle, 'video/mp4')})
    assert uploaded.status_code == 201, uploaded.text
    project = uploaded.json()
    assert project['has_audio'] is True
    pid = project['id']
    assert client.get(f'/api/projects/{pid}/video').status_code == 200
    assert any(item['id']==pid for item in client.get('/api/projects').json())
    analysis = client.post(f'/api/projects/{pid}/analyze?threshold=0.1&max_candidates=8')
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    assert result['waveform']
    assert 'heuristic' in result['method'].lower()
    assert client.get(f'/api/projects/{pid}').json()['analyzed'] is True
    clip = client.post(f'/api/projects/{pid}/clips', json={'start':2.0,'end':5.0,'layout':'Portrait · contain'})
    assert clip.status_code == 201, clip.text
    video_url = clip.json()['url']
    downloaded = client.get(video_url)
    assert downloaded.status_code == 200
    assert downloaded.content[:4] != b''
    outpath = web.DATA/'clips'/ (clip.json()['id'] + '.mp4')
    dims = subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','csv=p=0',str(outpath)],text=True).strip()
    assert dims == '720,1280'
    assert any(c['id']==clip.json()['id'] for c in client.get('/api/clips').json())
    invalid = client.post(f'/api/projects/{pid}/clips', json={'start':0,'end':99,'layout':'Original'})
    assert invalid.status_code == 400


def test_analytics():
    csv = (ROOT/'data'/'SIMULATED_engagement_example.csv').read_bytes()
    result = client.post('/api/analytics', files={'file':('sample.csv',csv,'text/csv')})
    assert result.status_code == 200,result.text
    doc=result.json()
    assert doc['summary']['posts'] > 0
    assert doc['summary']['views'] > 0
    assert isinstance(doc['posts'],list)
    assert client.get('/api/sample-analytics').status_code == 200


def test_csv_missing_optional_columns_accepted():
    data=b'clip_id,views,likes\n1,100,9\n'
    r=client.post('/api/analytics',files={'file':('partial.csv',data,'text/csv')})
    assert r.status_code == 200
    assert r.json()["posts"][0]["shares_per_1000_views"] is None
