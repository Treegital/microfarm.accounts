from marshmallow.decorators import post_load
from marshmallow.fields import Email, Enum
from marshmallow_peewee import ModelSchema
from marshmallow.exceptions import ValidationError
from .models import Account, AccountStatus
from .password import hash_password


class AccountSchema(ModelSchema):

    class Meta:
        model = Account
        exclude = ('salter',)
        load_only = ('password',)
        dump_only = ('id', 'status')

    email = Email(required=True)
    status = Enum(AccountStatus, by_value=True)

    @post_load
    def hasher(self, data, **kwargs):
        data['password'] = hash_password(data['password'])
        return data


account = AccountSchema()
load_account = account.load
dump_account = account.dump
