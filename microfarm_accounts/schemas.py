from marshmallow.decorators import post_load
from marshmallow.fields import Email
from marshmallow_peewee import ModelSchema
from marshmallow.exceptions import ValidationError
from .models import Account
from .password import hash_password


class AccountSchema(ModelSchema):

    class Meta:
        model = Account

    email = Email()

    @post_load
    def hasher(self, data, **kwargs):
        data['password'] = hash_password(data['password'])
        return data


load_account = AccountSchema().load
dump_account = AccountSchema(exclude=('password', 'salter')).dump
