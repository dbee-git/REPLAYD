from pathlib import Path
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
import replayd.web as web
from replayd import campaigns

client=TestClient(web.app)

@pytest.fixture(autouse=True)
def clean_local_db(tmp_path,monkeypatch):
    monkeypatch.setattr(web,'DATA',tmp_path)
    monkeypatch.setattr(web,'DB',tmp_path/'campaign_test.sqlite3')


def new_campaign(**changes):
    payload={'title':'Autumn Matchdays','brand':'Example Partner','requirement_type':'both','rpm_usd':'300.00',
             'min_duration_sec':15,'max_duration_sec':45,'payout_cap_usd':None,'notes':'Logo top right; supplied music'}
    payload.update(changes)
    result=client.post('/api/campaigns',json=payload)
    assert result.status_code==201,result.text
    return result.json()


def new_submission(cid, **changes):
    payload={'title':'Clásico comeback','platform':'Instagram','public_views':150000,'eligible_views':120000,
             'duration_sec':30,'status':'submitted','edit_minutes':40}
    payload.update(changes)
    result=client.post('/api/campaigns/'+cid+'/submissions',json=payload)
    assert result.status_code==201,result.text
    return result.json()


def test_campaign_create_and_list():
    created=new_campaign()
    assert created['rpm_usd']=='300.00'
    assert created['requirement_type']=='both'
    assert created['min_duration_sec']==15
    assert created['submissions']==[]
    assert client.get('/api/campaigns').json()[0]['id']==created['id']
    assert client.get('/api/campaigns/'+created['id']).status_code==200
    assert client.get('/api/campaigns/does-not-exist').status_code==404


def test_views_not_money_until_approval_then_partial_payments():
    cid=new_campaign()['id']
    res=new_submission(cid)
    assert res['potential_total_usd']=='36.00'
    assert res['confirmed_earnings_usd']=='0.00'
    assert res['outstanding_usd']=='0.00'
    sid=res['new_submission_id']
    result=client.patch(f'/api/campaigns/{cid}/submissions/{sid}',json={'status':'approved'})
    assert result.status_code==200,result.text
    assert result.json()['confirmed_earnings_usd']=='36.00'
    pay=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'20.00','paid_on':'2026-11-23','reference':'REF001'})
    assert pay.status_code==201,pay.text
    assert pay.json()['outstanding_usd']=='16.00'
    assert pay.json()['settled_usd']=='20.00'
    assert pay.json()['payments'][0]['reference']=='REF001'
    pay=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'16','paid_on':'2026-11-23'})
    assert pay.json()['outstanding_usd']=='0.00'
    assert pay.json()['settled_usd']=='36.00'


def test_updated_cumulative_views_replaces_not_adds_and_snapshots():
    cid=new_campaign()['id']; res=new_submission(cid,status='approved')
    sid=res['new_submission_id']
    change=client.patch(f'/api/campaigns/{cid}/submissions/{sid}',json={'public_views':180000,'eligible_views':150000})
    assert change.status_code==200,change.text
    info=change.json()
    assert info['confirmed_earnings_usd']=='45.00'
    assert info['approved_eligible_views']==150000
    historical=client.get(f'/api/campaigns/{cid}/view-history/{sid}')
    assert historical.status_code==200
    assert [x['eligible_views'] for x in historical.json()]==[120000,150000]
    client.patch(f'/api/campaigns/{cid}/submissions/{sid}',json={'status':'rejected'})
    assert client.get('/api/campaigns/'+cid).json()['confirmed_earnings_usd']=='0.00'


def test_cap_applies_campaign_wide_and_advance_explained():
    cid=new_campaign(payout_cap_usd='60.00')['id']
    new_submission(cid,status='approved',public_views=500000,eligible_views=500000)
    out=new_submission(cid,status='approved',public_views=500000,eligible_views=500000)
    assert out['confirmed_earnings_usd']=='60.00'
    assert out['submissions'][0]['estimated_usd']=='150.00' # before cap, label makes that explicit
    paid=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'75','paid_on':'2026-11-23'}).json()
    assert paid['outstanding_usd']=='0.00'
    assert paid['advance_usd']=='15.00'


def test_pending_and_rejected_not_counted_as_confirmed():
    cid=new_campaign()['id']
    new_submission(cid,status='rejected',public_views=100000,eligible_views=100000)
    out=new_submission(cid,status='submitted',public_views=200000,eligible_views=200000)
    assert out['confirmed_earnings_usd']=='0.00'
    assert out['potential_total_usd']=='60.00'
    assert out['tracked_eligible_views']==200000
    assert out['pending_eligible_views']==200000


def test_duration_preference_warning_not_prevent_save():
    cid=new_campaign()['id']
    out=new_submission(cid,duration_sec=90)
    assert out['submissions'][0]['duration_within_preference'] is False
    sid=out['new_submission_id']
    fixed=client.patch(f'/api/campaigns/{cid}/submissions/{sid}',json={'duration_sec':30}).json()
    assert fixed['submissions'][0]['duration_within_preference'] is True


def test_validate_invalid_records_and_cross_campaign_ids():
    cid=new_campaign()['id']
    other=new_campaign(title='Another')['id']
    bad=client.post('/api/campaigns/'+cid+'/submissions',json={'title':'Invalid','platform':'Instagram','public_views':500,'eligible_views':600})
    assert bad.status_code==422
    missing=client.post('/api/campaigns',json={'title':'Oops','brand':'Demo','requirement_type':'logo','rpm_usd':'200','min_duration_sec':60,'max_duration_sec':10})
    assert missing.status_code==422
    sid=new_submission(cid)['new_submission_id']
    update=client.patch(f'/api/campaigns/{other}/submissions/{sid}',json={'status':'approved'})
    assert update.status_code==404
    bad_payment=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':0,'paid_on':'2026-11-23'})
    assert bad_payment.status_code==422
    bad_money=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'1.005','paid_on':'2026-11-23'})
    assert bad_money.status_code==422
    bad_date=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'1','paid_on':'not a date'})
    assert bad_date.status_code==422
    missing_clip=client.post('/api/campaigns/'+cid+'/submissions',json={'title':'Missing export','platform':'Instagram','clip_id':'nothere'})
    assert missing_clip.status_code==422


def test_campaign_updates_and_payout_recomputed():
    cid=new_campaign()['id']
    new_submission(cid,status='approved',public_views=200000,eligible_views=200000)
    patch=client.patch('/api/campaigns/'+cid,json={'status':'paused','rpm_usd':'400.00','min_duration_sec':12,'max_duration_sec':55})
    assert patch.status_code==200,patch.text
    assert patch.json()['status']=='paused'
    assert patch.json()['confirmed_earnings_usd']=='80.00'
    assert patch.json()['max_duration_sec']==55
    assert client.patch('/api/campaigns/'+cid,json={'min_duration_sec':60}).status_code==422


def test_currency_rounding_and_no_float_drift():
    assert campaigns.payout_cents(17,30000)==1
    assert campaigns.payout_cents(1,30000)==0
    assert campaigns.dollars_to_cents('120.01')==12001
    assert campaigns.usd(12001)=='120.01'
    assert campaigns.dollars_to_cents(Decimal('0.01'))==1
    with pytest.raises(ValueError):campaigns.dollars_to_cents('12.345')


def test_multiple_campaigns_isolated():
    a=new_campaign(title='A')['id'];b=new_campaign(title='B')['id']
    new_submission(a,status='approved',public_views=100000,eligible_views=100000)
    new_submission(b,status='submitted',public_views=100000,eligible_views=100000)
    statuses={c['id']:c['confirmed_earnings_usd'] for c in client.get('/api/campaigns').json()}
    assert statuses[a]=='30.00'
    assert statuses[b]=='0.00'


def test_void_payment_keeps_audit_trail_and_recalculates_outstanding():
    cid=new_campaign()['id']
    new_submission(cid,status='approved')
    result=client.post('/api/campaigns/'+cid+'/payments',json={'amount_usd':'20','paid_on':'2026-11-23'})
    pid=result.json()['payments'][0]['id']
    bad=client.post(f'/api/campaigns/{cid}/payments/{pid}/void',json={'reason':'x'})
    assert bad.status_code==422
    done=client.post(f'/api/campaigns/{cid}/payments/{pid}/void',json={'reason':'Entered wrong amount'})
    assert done.status_code==200,done.text
    out=done.json()
    assert out['settled_usd']=='0.00'
    assert out['outstanding_usd']=='36.00'
    assert out['payments'][0]['void_reason']=='Entered wrong amount'
    assert out['payments'][0]['voided_at'] is not None
    assert client.post(f'/api/campaigns/{cid}/payments/{pid}/void',json={'reason':'again'}).status_code==422


def test_campaign_uses_real_library_clip_reference():
    from pathlib import Path
    cid=new_campaign()['id']
    with web.connect() as db:
        db.execute("INSERT INTO projects(id,name,filename,duration,width,height,has_audio) VALUES(?,?,?,?,?,?,?)", ('project001','demo','/tmp/demo.mp4',10,1280,720,1))
        db.execute("INSERT INTO clips(id,project_id,start,end,layout,filename) VALUES(?,?,?,?,?,?)", ('clip001','project001',1,5,'Original','/tmp/clip.mp4'))
    resp=new_submission(cid,clip_id='clip001')
    assert resp['submissions'][0]['clip_id']=='clip001'


def test_input_does_not_allow_unsafe_links_or_blank_titles():
    cid=new_campaign()['id']
    link=client.post(f'/api/campaigns/{cid}/submissions',json={'title':'test','platform':'Instagram','post_url':'javascript:alert(1)'})
    assert link.status_code==422
    blank=client.post('/api/campaigns',json={'title':'   ','brand':'Demo','requirement_type':'logo','rpm_usd':'100'})
    assert blank.status_code==422


def test_export_business_report_as_csv():
    cid=new_campaign(source_platform='Spade')['id']
    new_submission(cid,status='approved',public_views=100000,eligible_views=100000)
    out=client.get('/api/campaign-reports/summary.csv')
    assert out.status_code==200
    assert 'text/csv' in out.headers['content-type']
    assert 'REPLAYD_campaigns_summary.csv' in out.headers['content-disposition']
    assert 'Spade' in out.text
    assert '30.00' in out.text
    assert 'Confirmed USD' in out.text


def test_starlet_marketplace_source_supported():
    created=new_campaign(source_platform='Starlet')
    assert created['source_platform']=='Starlet'
    assert any(x['source_platform']=='Starlet' for x in client.get('/api/campaigns').json())


@pytest.mark.parametrize('marketplace', ['Whop','Content Rewards','CLIPPING','Clipster','Spade','Starlet','Vyro','Clipur','Discord','Direct','Other'])
def test_verified_marketplace_sources_supported_by_api(marketplace):
    campaign=new_campaign(source_platform=marketplace)
    assert campaign['source_platform']==marketplace
    changed=client.patch('/api/campaigns/'+campaign['id'],json={'source_platform':'Direct'})
    assert changed.status_code==200,changed.text

