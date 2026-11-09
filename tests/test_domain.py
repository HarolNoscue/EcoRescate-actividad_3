from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import json
import pytest
from fastapi.testclient import TestClient
from command_service.domain import Offer, BusinessError
from command_service.sqlite_adapter import SQLiteOfferRepository
from command_service.api import create_app as command_app
from query_service.projector import ProjectionStore
from query_service.api import create_app as query_app


def future(hours=2):
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def sample_offer(quantity=10):
    return {"provider":"Panadería Andina", "title":"Pan integral fresco", "category":"Panadería",
            "zone":"Zona Centro", "quantity": quantity, "expires_at":future().isoformat()}


def test_domain_rejects_expired_and_excess():
    offer=Offer(str(uuid4()),"Tienda","Pan","Comida","Centro",10,10,future(),1)
    with pytest.raises(BusinessError, match="inventario"):
        offer.reserve(11, datetime.now(timezone.utc))
    offer.reserve(7, datetime.now(timezone.utc))
    assert offer.available_quantity==3 and offer.version==2
    offer.release(7)
    assert offer.available_quantity==10
    expired=Offer(str(uuid4()),"Tienda","Pan","Comida","Centro",2,2,future(-1))
    with pytest.raises(BusinessError, match="venció"):
        expired.reserve(1, datetime.now(timezone.utc))


def test_api_and_cqrs_idempotent(tmp_path):
    write=TestClient(command_app(str(tmp_path/'write.db')))
    read=TestClient(query_app(str(tmp_path/'read.db')))
    response=write.post('/offers',json=sample_offer(5)); assert response.status_code==201
    offer=response.json()
    reserve=write.post(f'/offers/{offer["id"]}/claims',json={'organization':'Fundación Luz','quantity':3})
    assert reserve.status_code==201
    assert write.post(f'/offers/{offer["id"]}/claims',json={'organization':'Otra ONG','quantity':3}).status_code==409
    repo=SQLiteOfferRepository(str(tmp_path/'write.db'))
    store=ProjectionStore(str(tmp_path/'read.db'))
    events=[json.loads(row['payload']) for row in repo.pending_outbox()]
    for e in events:
        assert store.apply(e)
        assert not store.apply(e)   # redelivery no duplica lectura
    assert read.get('/metrics').json()['reserved_units']==3
    assert read.get('/offers').json()[0]['available_quantity']==2
    claimid=reserve.json()['id']
    assert write.post(f'/claims/{claimid}/cancel').status_code==200
    assert write.post(f'/claims/{claimid}/cancel').status_code==409
    last=json.loads(repo.pending_outbox()[-1]['payload'])
    assert store.apply(last)
    assert read.get('/metrics').json()['reserved_units']==0
    assert read.get('/offers').json()[0]['available_quantity']==5


def test_concurrent_claims_only_one_succeeds(tmp_path):
    repo=SQLiteOfferRepository(str(tmp_path/'race.db'))
    offer=Offer(str(uuid4()),"Panadería","Cajas","Panadería","Centro",4,4,future())
    repo.create(offer)

    def compete(i):
        try:
            repo.claim(offer.id, f'Organización {i}', 3, datetime.now(timezone.utc))
            return 'ok'
        except BusinessError as e:
            return e.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(compete, (1,2)))
    assert sorted(results)==['INSUFFICIENT_STOCK','ok']
    import sqlite3
    with sqlite3.connect(repo.path) as db:
        assert db.execute('SELECT available_quantity FROM offers').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM claims').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]==2


def test_reject_invalid_date_and_input(tmp_path):
    client=TestClient(command_app(str(tmp_path/'api.db')))
    invalid=sample_offer(); invalid['expires_at']=future(-4).isoformat()
    assert client.post('/offers',json=invalid).status_code==422
    invalid=sample_offer(); invalid['quantity']=-10
    assert client.post('/offers',json=invalid).status_code==422


def test_out_of_order_read_model_keeps_latest(tmp_path):
    repo=SQLiteOfferRepository(str(tmp_path/'a.db'))
    offer=Offer(str(uuid4()),"Tienda","Bananas","Frutas","Centro",3,3,future())
    repo.create(offer)
    repo.claim(offer.id,'Organización B',1, datetime.now(timezone.utc))
    items=[json.loads(o['payload']) for o in repo.pending_outbox()]
    proj=ProjectionStore(str(tmp_path/'b.db'))
    assert proj.apply(items[1]); assert proj.apply(items[0])
    assert proj.list_offers()[0]['version']==2
    assert proj.list_offers()[0]['available_quantity']==2
