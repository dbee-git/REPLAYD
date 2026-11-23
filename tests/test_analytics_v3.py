"""Analytics v0.3 tests: partial data, aliases, duplicate handling and persistence."""
import io
import pytest
from fastapi.testclient import TestClient
import replayd.web as web
from replayd.analytics import parse_csv, dashboard, enrich

client=TestClient(web.app)

@pytest.fixture(autouse=True)
def safe_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(web,'DATA',tmp_path)
    monkeypatch.setattr(web,'DB',tmp_path/'test.sqlite3')


def test_partial_csv_and_aliases():
    rows,info=parse_csv(io.BytesIO(b'Post ID,View Count,Posted Site,Category\nabc,1,Instagram,comeback\n'))
    assert rows[0]['clip_id']=='abc'
    assert rows[0]['views']==1
    assert rows[0]['platform']=='instagram'
    assert rows[0]['shares'] is None
    assert info['matched_columns']==['clip_id','platform','content_type','views'] or set(info['matched_columns'])=={'clip_id','platform','content_type','views'}


def test_empty_metric_or_negative_rejected():
    with pytest.raises(ValueError,match='No engagement columns'):parse_csv(io.BytesIO(b'platform\ninstagram\n'))
    with pytest.raises(ValueError,match='Row 2'):parse_csv(io.BytesIO(b'views,shares\n90,-2\n'))
    with pytest.raises(ValueError,match='Row 2'):parse_csv(io.BytesIO(b'views\n3.5\n'))


def test_missing_not_zero_and_complete_interactions():
    post=enrich({'views':100,'likes':5,'shares':3,'saves':None,'comments':None})
    assert post['shares_per_1000_views']==30
    assert post['interactions_per_100_views'] is None
    result=dashboard([post])
    assert result['summary']['saves'] is None
    assert result['coverage']['shares']==1
    assert result['coverage']['saves']==0


def test_minimum_group_sample_size():
    records=[{'clip_id':str(i),'platform':'instagram','content_type': 'goal' if i<2 else 'comeback','views':100,'shares':10} for i in range(6)]
    data=dashboard(records)
    groups={g['name']:g for g in data['content_types']}
    assert groups['goal']['median_shares_1000'] is None
    assert groups['comeback']['median_shares_1000']==100.0
    assert groups['goal']['posts']==2


def test_manual_import_persistence_and_dedupe():
    empty=client.get('/api/analytics/overview');assert empty.json()['summary']['posts']==0
    data={'clip_id':'reel01','platform':'instagram','views':1200,'shares':20,'content_type':'goal'}
    a=client.post('/api/analytics/manual',json=data)
    assert a.status_code==201,a.text
    assert client.get('/api/analytics/overview').json()['summary']['posts']==1
    data['views']=1500
    data['shares']=None
    b=client.post('/api/analytics/manual',json=data);assert b.status_code==201
    doc=client.get('/api/analytics/overview').json();assert doc['summary']['posts']==1
    assert doc['posts'][0]['views']==1500
    assert doc['posts'][0]['shares']==20  # missing input didn't erase known values
    deleted=client.delete('/api/analytics/posts/'+a.json()['id']);assert deleted.status_code==204
    assert client.get('/api/analytics/overview').json()['summary']['posts']==0


def test_flexible_csv_bulk_and_reimport_no_duplicates():
    csv=b'Post ID,View Count,Posted Site,Category,Shares\n1,8000,Instagram,goal,51\n2,18000,Instagram,comeback,330\n'
    a=client.post('/api/analytics/import',files={'file':('my_posts.csv',csv,'text/csv')})
    assert a.status_code==200,a.text
    assert a.json()['import_info']['new']==2
    b=client.post('/api/analytics/import',files={'file':('my_posts.csv',csv,'text/csv')})
    assert b.status_code==200
    assert b.json()['import_info']['updated']==2
    assert b.json()['summary']['posts']==2


def test_sample_dataset_is_marked_synthetic():
    r=client.get('/api/sample-analytics');assert r.status_code==200
    imp=client.post('/api/analytics/import',files={'file':('REPLAYD_SYNTHETIC_144_posts.csv',r.content,'text/csv')})
    assert imp.status_code==200,imp.text
    assert imp.json()['demo_posts']==144


def test_bad_date_and_undocumented_data_rejected():
    assert client.post('/api/analytics/manual',json={'views':90,'published_at':'tomorrow'}).status_code==422
    assert client.post('/api/analytics/manual',json={}).status_code==422


def test_partially_missing_synthetic_demo_import():
    source=web.ROOT/'data'/'REPLAYD_SYNTHETIC_PARTIAL_24_posts.csv'
    result=client.post('/api/analytics/import',files={'file':(source.name,source.read_bytes(),'text/csv')})
    assert result.status_code==200,result.text
    data=result.json()
    assert data['summary']['posts']==24
    assert data['demo_posts']==24
    assert data['coverage']['views'] < 24
    assert data['coverage']['shares'] < 24

