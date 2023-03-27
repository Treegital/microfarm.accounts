import pytest
from microfarm_accounts.models import Account
from freezegun import freeze_time


pytestmark = pytest.mark.asyncio


class TestEmptyDatabase:

    async def test_request_token(self, service, client):
        response = await client.request_account_token("test@test.com")
        assert response == {'err': 'Account does not exist.'}

    async def test_verify_account(self, service, client):
        response = await client.verify_account("test@test.com", "ABC")
        assert response == {'err': 'Account cannot be activated.'}

    async def test_verify_credentials(self, service, client):
        response = await client.verify_credentials("test@test.com", "ABC")
        assert response == {'err': 'Account does not exist.'}

    async def test_get_account(self, service, client):
        response = await client.verify_credentials("test@test.com", "pwd")
        assert response == {'err': 'Account does not exist.'}


class TestFailingCreateAccount:

    async def test_create_account_bad_data(self, service, client):
        response = await client.create_account({})
        assert response == {
            'email': ('Missing data for required field.',),
            'password': ('Missing data for required field.',)
        }

        response = await client.create_account({'password': 'test'})
        assert response == {
            'email': ('Missing data for required field.',),
        }

        response = await client.create_account({
            'email': 'test',
            'password': 'test'
        })
        assert response == {
            'email': ('Not a valid email address.',)
        }

        response = await client.create_account({
            'id': 'test',
            'email': 'test@test.com',
            'password': 'pw'
        })
        assert response == {
            'id': ('Unknown field.',)
        }

        response = await client.create_account({
            'salter': b'bytes',
            'status': 'test',
            'email': 'test@test.com',
            'password': 'pw'
        })
        assert response == {
            'salter': ('Unknown field.',),
            'status': ('Unknown field.',)
        }

    async def test_create_account_duplicate(self, service, client):
        response = await client.create_account({
            'email': 'test@test.com',
            'password': 'pw'
        })
        assert tuple(response.keys()) == ('otp',)

        response = await client.create_account({
            'email': 'test@test.com',
            'password': 'pw'
        })
        assert response == {
            'err': 'UNIQUE constraint failed: accounts.email'
        }


class TestAccountToken:

    async def test_token_idempotency(self, db_manager, service, client):

        with freeze_time("2023-03-25 13:00:01"):
            response1 = await client.create_account({
                'email': 'test@test.com',
                'password': 'pw'
            })
            response2 = await client.create_account({
                'email': 'test2@test.com',
                'password': 'pw'
            })

        token1 = response1['otp']
        token2 = response2['otp']
        assert token1 != token2

        with freeze_time("2023-03-25 13:12:11"):
            response = await client.request_account_token(
                email="test@test.com"
            )
        assert response['otp'] == token1

        with freeze_time("2023-03-25 14:30:00"):
            response = await client.request_account_token(
                email="test@test.com"
            )
        assert response['otp'] != token1

    async def test_token_verify_once(self, service, client):

        with freeze_time("2023-03-25 13:00:01"):
            response = await client.create_account({
                'email': 'test@test.com',
                'password': 'pw'
            })
        token = response['otp']

        with freeze_time("2023-03-25 13:12:11"):
            response = await client.verify_account(
                email="test@test.com",
                otp=token
            )
        uid = response.pop('id')
        assert len(uid) == 12
        assert response == {
            'creation_date': '2023-03-25T13:00:01',
            'email': 'test@test.com',
            'status': 'active'
        }

        with freeze_time("2023-03-25 13:12:20"):
            response = await client.verify_account(
                email="test@test.com",
                otp=token
            )
        assert response == {'err': 'Account cannot be activated.'}


class TestCredentials:

    async def test_credentials_not_activated(self, service, client):
        await client.create_account({
                'email': 'test@test.com',
                'password': 'pw'
        })
        response = await client.verify_credentials("test@test.com", "pw")
        assert response == {'err': 'Account does not exist.'}

    async def test_credentials_activated(self, service, client):
        with freeze_time("2023-03-27 10:27:53"):
            response = await client.create_account({
                'email': 'test@test.com',
                'password': 'pw'
            })
            await client.verify_account(
                email="test@test.com",
                otp=response['otp']
            )
        response = await client.verify_credentials("test@test.com", "pw")
        uid = response.pop('id')
        assert len(uid) == 12
        assert response == {
            'creation_date': '2023-03-27T10:27:53',
            'email': 'test@test.com',
            'status': 'active'
        }
