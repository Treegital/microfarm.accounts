import asyncio
from minicli import run, cli
from aiozmq import rpc
from models import manager, Account, AccountStatus


class AccountService(rpc.AttrHandler):

    def __init__(self, manager):
        self.manager = manager

    @rpc.method
    async def create_account(self, data: dict) -> bool:
        async with self.manager:
            async with self.manager.connection():
                account = await Account.create(**data)
                token = account.totp.now()
        return {'otp': token}

    @rpc.method
    async def request_account_token(self, email: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                account = await Account.get(email=email)
                token = account.totp.now()
        return {'otp': token}

    @rpc.method
    async def verify_account(self, email: str, otp: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                account = await Account.get(
                    email=email,
                    status=AccountStatus.pending
                )
        if account is None:
            return {'err': 'Invalid token'}

        if not account.totp.verify(otp):
            return {'err': 'Invalid token'}

        account.status = AccountStatus.active
        await account.save()
        return True

    @rpc.method
    async def verify_credentials(self, email: str, password: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                account = await Account.get(email=email)
        if account is None:
            return None
        if account.password == password:
            return {'email': account.email}
        return None

    @rpc.method
    async def get_account(self, email: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                account = await Account.get(email=email)
        return {'email': account.email}


@cli
async def serve(host: str = "127.0.0.1", port: int = 5556):
    async with manager:
        async with manager.connection():
            await Account.create_table()

    service = AccountService(manager)
    server = await rpc.serve_rpc(service, bind=f'tcp://{host}:{port}')
    await server.wait_closed()


if __name__ == '__main__':
    run()
