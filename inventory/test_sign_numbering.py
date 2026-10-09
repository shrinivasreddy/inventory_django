import json
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, Client
from .models import Project, TabRecord

class SignNumberingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('numbering', password='test-password')
        self.project = Project.objects.create(name='Numbering', code='numbering')
        self.project.members.add(self.user)
        self.client.force_login(self.user)

    def save_row(self, **values):
        row = {'ST_ID':'A','LATITUDE':'38.1234561','LONGITUDE':'-121.1234561', **values}
        return self.client.post('/api/sign/records', json.dumps({'row':row}), content_type='application/json')

    def test_generation_matching_precision_and_manual_overrides(self):
        first = self.save_row()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()['record']['POLE_ID'], 'P1')
        self.assertEqual(first.json()['record']['SIGN'], 'S1')
        second = self.save_row(LATITUDE='38.1234562')
        self.assertEqual(second.json()['record']['SIGN'], 'S2')
        self.assertEqual(second.json()['record']['POLE_ID'], 'P1')
        self.assertEqual(self.save_row(POLE_ID='P1', SIGN='S8').status_code, 200)
        self.assertEqual(self.save_row().json()['record']['SIGN'], 'S9')
        moved = self.save_row(LATITUDE='39', POLE_ID='P1')
        self.assertEqual(moved.json()['record']['SIGN'], 'S10')
        self.assertEqual(self.save_row(LATITUDE='40').json()['record']['POLE_ID'], 'P2')
        self.assertEqual(self.save_row(LATITUDE='41', POLE_ID='p1', SIGN='s8').status_code, 200)
        self.assertEqual(self.save_row(LONGITUDE='-122', POLE_ID='p1', SIGN='s8').status_code, 200)
        duplicate = self.save_row(LATITUDE='38.1234562', POLE_ID='p1', SIGN='s8')
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn('already exist', duplicate.json()['error'])
        self.assertIn('same latitude and longitude', duplicate.json()['error'])

    def test_edit_allows_same_ids_at_different_coordinates(self):
        first = self.save_row(POLE_ID='P2', SIGN='S1').json()['record']
        second = self.save_row(LATITUDE='39', POLE_ID='P2', SIGN='S1').json()['record']
        url = '/api/sign/records/' + str(second['ID'])
        response = self.client.put(url, json.dumps({'row':second}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        second['LATITUDE'] = first['LATITUDE']
        response = self.client.put(url, json.dumps({'row':second}), content_type='application/json')
        self.assertEqual(response.status_code, 400, response.content)
        second['LONGITUDE'] = '-122'
        response = self.client.put(url, json.dumps({'row':second}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_edit_duplicate_and_deletion_gap(self):
        first = self.save_row(POLE_ID='P5', SIGN='S1').json()['record']
        second = self.save_row(POLE_ID='P5', SIGN='S5').json()['record']
        self.client.delete('/api/sign/records/' + str(first['ID']))
        self.assertEqual(self.save_row().json()['record']['SIGN'], 'S6')
        second['SIGN'] = 'S6'
        response = self.client.put('/api/sign/records/' + str(second['ID']), json.dumps({'row':second}), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_suggestion_and_project_scope(self):
        self.save_row(POLE_ID='P3', SIGN='S7')
        response = self.client.get('/api/sign/id-suggestion', {'LATITUDE':'38.1234562','LONGITUDE':'-121.1234561'})
        self.assertEqual(response.json(), {'POLE_ID':'P3','SIGN':'S8'})
        self.assertEqual(self.client.get('/api/sign/id-suggestion', {'LATITUDE':'40','LONGITUDE':'-120'}).json(), {'POLE_ID':'','SIGN':''})
        other = Project.objects.create(name='Other', code='other-numbering')
        other.members.add(self.user)
        session = self.client.session
        session['inventory_project_id'] = other.pk
        session.save()
        self.assertEqual(self.save_row(POLE_ID='P3', SIGN='S7').status_code, 200)

class ConcurrentSignNumberingTests(TransactionTestCase):
    def test_simultaneous_saves_allocate_distinct_ids(self):
        user = get_user_model().objects.create_user('concurrent-numbering')
        project = Project.objects.create(name='Concurrent', code='concurrent')
        project.members.add(user)
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(user)
        def save(client):
            close_old_connections()
            try:
                response = client.post('/api/sign/records', json.dumps({'row':{'ST_ID':'A','LATITUDE':'38','LONGITUDE':'-121'}}), content_type='application/json')
                return response.status_code, response.json()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, clients))
        self.assertEqual([r[0] for r in results], [200, 200], results)
        self.assertEqual({r[1]['record']['SIGN'] for r in results}, {'S1','S2'})
        self.assertEqual({r[1]['record']['POLE_ID'] for r in results}, {'P1'})
