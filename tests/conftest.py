import asyncio
import pytest
import pytest_asyncio
from aiozmq import rpc
from peewee_aio import Manager
from microfarm_accounts.models import Account
from microfarm_accounts.service import AccountService, TokenFactory


@pytest_asyncio.fixture(scope="function")
async def db_manager(tmpdir_factory):
    path = tmpdir_factory.mktemp("databases").join("test.db")
    db = f"aiosqlite:///{path}"
    manager = Manager(db)
    manager.register(Account)

    async with manager:
        async with manager.connection():
            await Account.create_table()

    return manager


@pytest_asyncio.fixture(scope="function")
async def service(db_manager):
    token_factory = TokenFactory()
    service = AccountService(db_manager, token_factory)
    server = await rpc.serve_rpc(service, bind="inproc://test")
    yield server
    server.close()
    await server.wait_closed()


@pytest_asyncio.fixture(scope="function")
async def client():
    client = await rpc.connect_rpc(connect="inproc://test", timeout=0.5)
    try:
        yield client.call
    finally:
        client.close()
