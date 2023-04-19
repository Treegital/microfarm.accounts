import peewee
import secrets
import short_id
from functools import cached_property
from enum import Enum
from datetime import datetime
from peewee_aio import AIOModel
from peewee import IntegrityError


class EnumField(peewee.CharField):

    def __init__(self, choices, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.choices = choices

    def db_value(self, value):
        if value is None:
            return None
        return value.value

    def python_value(self, value):
        if value is None and self.null:
            return value
        return self.choices(value)


def creation_date():
    return datetime.utcnow()


def uniqueid_factory() -> str:
    unique_id: str = short_id.generate_short_id()
    return unique_id


def salt_generator(size: int):
    def generate_salt():
        return secrets.token_bytes(size)
    return generate_salt


class AccountStatus(str, Enum):
    pending = 'pending'
    active = 'active'
    disabled = 'disabled'


class Account(AIOModel):

    class Meta:
        table_name = 'accounts'

    id = peewee.CharField(primary_key=True, default=uniqueid_factory)
    email = peewee.CharField(unique=True)
    name = peewee.CharField()
    salter = peewee.BlobField(default=salt_generator(24))
    password = peewee.CharField()
    status = EnumField(AccountStatus, default=AccountStatus.pending)
    creation_date = peewee.DateTimeField(default=creation_date)
