import sys
import asyncio
import logging
from pathlib import Path
from minicli import run, cli
from aiozmq import rpc
from .models import Account, AccountStatus, IntegrityError
from .schemas import load_account, dump_account, ValidationError
from .password import verify_password


logger = logging.getLogger('microfarm_accounts')


class AccountService(rpc.AttrHandler):

    def __init__(self, manager):
        self.manager = manager

    @rpc.method
    async def create_account(self, data: dict) -> dict:
        logger.info('receiving account creation request.')
        try:
            account = load_account(data)
        except ValidationError as err:
            return err.normalized_messages()
        async with self.manager as manager:
            async with manager.connection():
                try:
                    await account.save(force_insert=True)
                    token = account.totp.now()
                except IntegrityError as err:
                    return {"err": str(err)}
        return {'otp': token}

    @rpc.method
    async def request_account_token(self, email: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(email=email)
                except Account.DoesNotExist:
                    return {'err': 'Account does not exist.'}
                token = account.totp.now()
        return {'otp': token}

    @rpc.method
    async def verify_account(self, email: str, otp: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(
                        email=email,
                        status=AccountStatus.pending
                    )
                except Account.DoesNotExist:
                    return {'err': 'Account does not exist.'}

                if not account.totp.verify(otp):
                    return {'err': 'Invalid token'}

                account.status = AccountStatus.active
                await account.save()
        return dump_account(account)

    @rpc.method
    async def verify_credentials(self, email: str, password: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(email=email)
                except Account.DoesNotExist:
                    return {'err': 'Account does not exist.'}
        if verify_password(account.password, password):
            return dump_account(account)
        return {'err': 'Credentials failed.'}

    @rpc.method
    async def get_account(self, email: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(email=email)
                except Account.DoesNotExist:
                    return {'err': 'Account does not exist.'}
        return dump_account(account)


@cli
async def serve(config: Path) -> None:
    import tomli
    import logging.config
    from peewee_aio import Manager

    assert config.is_file()
    with config.open("rb") as f:
        settings = tomli.load(f)

    if logconf := settings.get('logging'):
        logging.config.dictConfigClass(logconf).configure()

    manager = Manager(settings['database']['url'])
    manager.register(Account)

    async with manager:
        async with manager.connection():
            await Account.create_table()

    service = AccountService(manager)
    server = await rpc.serve_rpc(service, bind=settings['rpc']['bind'])
    print(f" [x] Account Service ({settings['rpc']['bind']})")
    await server.wait_closed()


if __name__ == '__main__':
    run()
