import logging
import base64
import pyotp
import hashlib
from pathlib import Path
from minicli import run, cli
from aiozmq import rpc
from peewee_aio import Manager
from .models import Account, AccountStatus, IntegrityError
from .schemas import load_account, dump_account, ValidationError
from .password import verify_password


logger = logging.getLogger('microfarm_accounts')


class TokenFactory:

    def __init__(self, digits=8, digest=hashlib.sha256, interval=60*60):
        self.digits = digits
        self.digest = digest
        self.interval = interval

    def __call__(self, key: str, name: str):
        return pyotp.TOTP(
            key,
            name=name,
            digits=self.digits,
            digest=self.digest,
            interval=self.interval
        )


class AccountService(rpc.AttrHandler):

    def __init__(self, manager: Manager, token_factory: TokenFactory):
        self.manager = manager
        self.token_factory = token_factory

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
                except IntegrityError as err:
                    return {"err": str(err)}

        totp = self.token_factory(
            base64.b32encode(account.salter),
            account.email
        )
        token = totp.now()
        return {'otp': token}

    @rpc.method
    async def request_account_token(self, email: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(email=email)
                except Account.DoesNotExist:
                    return {'err': 'Account does not exist.'}

        totp = self.token_factory(
            base64.b32encode(account.salter),
            account.email
        )
        token = totp.now()
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
                    return {'err': 'Account cannot be activated.'}

                totp = self.token_factory(
                    base64.b32encode(account.salter),
                    account.email
                )
                if not totp.verify(otp):
                    return {'err': 'Invalid token'}

                account.status = AccountStatus.active
                await account.save()
        return dump_account(account)

    @rpc.method
    async def verify_credentials(self, email: str, password: str) -> dict:
        async with self.manager:
            async with self.manager.connection():
                try:
                    account = await Account.get(
                        email=email,
                        status=AccountStatus.active
                    )
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

    token_factory = TokenFactory()
    service = AccountService(manager, token_factory)
    server = await rpc.serve_rpc(service, bind=settings['rpc']['bind'])
    print(f" [x] Account Service ({settings['rpc']['bind']})")
    await server.wait_closed()


if __name__ == '__main__':
    run()
